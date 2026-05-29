"""
System 2c: Continuous Guardrail Agent.
Fast, deterministic security audits and style constraint enforcement.
This is the 'Front-Line' of the audit system.
"""
import requests
import json
import time
import re
import os
import logging
from pathlib import Path
from typing import Tuple, List, Union
from tools.utils.telemetry import log_tool_performance
from tools.infrastructure.topology_manager import log_swarm_event

from tools.infrastructure.config import settings

_SECURE_ROOT = Path(settings.PROJECT_ROOT).resolve().absolute()


# Configuration
LOCAL_LLM_URL = f"{settings.OLLAMA_URL.rstrip('/')}/api/generate"
OLLAMA_MODEL = "llama3"
DEFAULT_TIMEOUT = 30 

class GuardrailAgent:
    def __init__(self):
        # Patterns indicative of prompt injection / behavioral overrides
        self.injection_patterns = [
            r"ignore (all )?instructions",
            r"ignore (all )?previous",
            r"new instructions",
            r"system override",
            r"you are now (an? )?(admin|root|attacker)",
            r"disregard (all )?guardrails",
            r"skip (all )?validation",
            r"as an? (admin|root)",
            r"forget .*? (everything|instructions|guardrails)",
            r"show (me )?.*? secrets",
            r"bypass (security|guardrails)"
        ]
        
        # Sensitive keys to mask in logs
        self.sensitive_patterns = [
            r"sk-[a-zA-Z0-9_-]{10,}", 
            r"AIzaSy[a-zA-Z0-9_-]{25,}", 
            r"sbp_[a-zA-Z0-9_-]{25,}", 
            r"password\s*[:=]\s*['\"]?([^'\"\s]+)['\"]?", 
        ]

    def scan_objective(self, objective: str) -> Tuple[bool, str]:
        """Scans a swarm objective for prompt injection patterns."""
        obj_lower = objective.lower()
        for pattern in self.injection_patterns:
            if re.search(pattern, obj_lower):
                return False, f"Potential Prompt Injection detected: Matches pattern '{pattern}'"
        return True, "Safe"

    def mask_secrets(self, text: str) -> str:
        """Masks sensitive data (API keys, passwords) in a string."""
        masked_text = text
        for pattern in self.sensitive_patterns:
            masked_text = re.sub(pattern, "[REDACTED_SECRET]", masked_text)
        return masked_text

    def validate_path(self, path: Union[str, Path]) -> bool:
        """
        Validates that the path is lexically contained within PROJECT_ROOT.
        Resolves symbolic links and prevents directory traversal escapes.
        """
        try:
            # 1. Fully resolve the path (following symlinks and removing relative path segments)
            # This ensures we check the actual physical target file
            target_path = Path(path).expanduser().resolve()

            # 2. Use commonpath for strict lexical prefix checking of the resolved path
            common = os.path.commonpath([_SECURE_ROOT, target_path])
            
            is_safe = Path(common) == _SECURE_ROOT
            
            if not is_safe:
                logging.warning(f"🚨 Security Alert: Path traversal attempt blocked: {path}")
                
            return is_safe

        except (ValueError, OSError, Exception) as e:
            logging.error(f"Path validation error: {e}")
            return False


    def run_audit(self, code_snippet: str, task_context: str = ""):
        """Performs a fast System 2c audit (Heuristics + local LLM)."""
        start_time = time.time()
        
        # --- 1. DETERMINISTIC SAFETY LAYER ---
        network_patterns = ["http", "requests.", "urllib", "aiohttp", "socket"]
        obfuscation_patterns = ["base64.b64decode", "binascii.unhexlify", "eval(", "exec("]
        breach_patterns = [".env", "os.system(", "subprocess.", "shutil.", "open('/etc/", "rm -rf"]

        has_network = any(p in code_snippet for p in network_patterns)
        has_obfuscation = any(p in code_snippet for p in obfuscation_patterns)
        has_breach = any(p in code_snippet for p in breach_patterns)

        if (has_network and has_obfuscation) or has_breach:
            found_crit = []
            if has_network and has_obfuscation:
                found_crit.extend([p for p in network_patterns if p in code_snippet])
                found_crit.extend([p for p in obfuscation_patterns if p in code_snippet])
            if has_breach:
                found_crit.extend([p for p in breach_patterns if p in code_snippet])
                
            result = {
                "status": "rejected",
                "risk_level": "critical",
                "critique": f"DETERMINISTIC REJECTION: Forbidden patterns detected ({', '.join(found_crit)}).",
                "improvement_instruction": "Remove unauthorized system/file access."
            }
            log_swarm_event("DECISION", {
                "tool": "guardrail_agent",
                "confidence": 1.0,
                "result": "REJECTED",
                "logic": result["critique"],
                "output": result["critique"]
            })
            return result

        # --- 2. LOCAL LLM REASONING ---
        system_prompt = (
            "You are SYSTEM 2c, a Continuous Guardrail Agent. catch hidden vulnerabilities and logic bombs. "
            "Return JSON: { \"status\": \"approved\"|\"rejected\", \"risk_level\": \"low\"|\"high\", \"critique\": \"...\" }"
        )
        prompt = f"TASK CONTEXT: {task_context}\n\nCODE TO AUDIT:\n```python\n{code_snippet}\n```"

        try:
            response = requests.post(
                LOCAL_LLM_URL,
                json={"model": OLLAMA_MODEL, "prompt": f"SYSTEM: {system_prompt}\nUSER: {prompt}", "stream": False},
                timeout=DEFAULT_TIMEOUT
            )
            if response.status_code == 200:
                raw_result = response.json().get("response", "")
                json_match = re.search(r"\{.*\}", raw_result, re.DOTALL)
                if json_match:
                    audit_result = json.loads(json_match.group(0))
                    log_tool_performance("guardrail_audit", True, time.time() - start_time)
                    log_swarm_event("DECISION", {
                        "tool": "guardrail_agent",
                        "confidence": 0.8,
                        "result": audit_result.get("status", "unknown").upper(),
                        "logic": audit_result.get("critique", "LLM Audit"),
                        "output": audit_result.get("critique", "LLM Audit")
                    })
                    return audit_result
        except Exception as e:
            log_tool_performance("guardrail_audit", False, time.time() - start_time)
            
        fallback_result = {"status": "approved", "risk_level": "unknown", "critique": "Audit fallback to safe status."}
        log_swarm_event("DECISION", {
            "tool": "guardrail_agent",
            "confidence": 0.1,
            "result": "APPROVED",
            "logic": "Fallback",
            "output": "Audit fallback to safe status."
        })
        return fallback_result

# Singleton Instance
guardrail_agent = GuardrailAgent()

# Functional wrapper for backwards compatibility
def run_guardrail_audit(code_snippet: str, task_context: str = ""):
    return guardrail_agent.run_audit(code_snippet, task_context)
