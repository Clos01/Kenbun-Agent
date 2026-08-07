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
from typing import Tuple, Union
from tools.utils.telemetry import log_tool_performance
from tools.infrastructure.topology_manager import log_swarm_event
from tools.audit.calibration import calibration, categorize

from tools.infrastructure.config import settings

# Identifier for this rung in the calibration store.
TIER_NAME = "guardrail_2c"

_SECURE_ROOT = Path(settings.PROJECT_ROOT).resolve().absolute()


# Configuration
# settings.OLLAMA_URL already points at the /api/generate endpoint; only append it
# when missing so we never build a doubled ".../api/generate/api/generate" (404 ->
# silent audit fallback, which auto-approved everything).
_ollama_base = settings.OLLAMA_URL.rstrip("/")
LOCAL_LLM_URL = _ollama_base if _ollama_base.endswith("/api/generate") else f"{_ollama_base}/api/generate"
# Must be a model actually installed in the local Ollama (was "llama3", which is not
# pulled -> every audit 404'd and fell back to approve). Overridable via env.
import os as _os
OLLAMA_MODEL = _os.getenv("GUARDRAIL_OLLAMA_MODEL", "llama3.2:3b")
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
        """Performs a fast System 2c audit (Heuristics + local LLM).

        Verdict semantics:
          - "rejected": authoritative. Deterministic pattern hits and local-model
            rejections both fail closed, and neither needs calibration to be
            trusted — a wrong rejection costs an escalation, not a breach.
          - "approved": only returned when this rung has been *shown* to agree
            with the tier above it in this category (see tools/audit/calibration).
          - "escalate": the rung has an opinion but has not earned the right to
            end the review here. The caller must run a stronger audit.
        """
        start_time = time.time()
        category = categorize(task_context, code_snippet)

        # --- 1. DETERMINISTIC SAFETY LAYER ---
        network_patterns = ["http", "requests.", "urllib", "aiohttp", "socket"]
        obfuscation_patterns = ["base64.b64decode", "binascii.unhexlify", "eval(", "exec("]
        # Substring matching, EXCEPT for dotfile references. Plain `".env" in code`
        # also fires on `os.environ` — so reading a secret from the environment,
        # which is the correct thing to do, was a critical deterministic rejection.
        # It also meant the 'secrets' category could never calibrate: every correct
        # example was rejected. Require a non-word, non-dot character before `.env`.
        breach_patterns = ["os.system(", "subprocess.", "shutil.", "open('/etc/", "rm -rf"]
        breach_regexes = [r"(?<![\w.])\.env\b"]

        has_network = any(p in code_snippet for p in network_patterns)
        has_obfuscation = any(p in code_snippet for p in obfuscation_patterns)
        matched_breaches = [p for p in breach_patterns if p in code_snippet]
        matched_breaches += [r for r in breach_regexes if re.search(r, code_snippet)]
        has_breach = bool(matched_breaches)

        if (has_network and has_obfuscation) or has_breach:
            found_crit = []
            if has_network and has_obfuscation:
                found_crit.extend([p for p in network_patterns if p in code_snippet])
                found_crit.extend([p for p in obfuscation_patterns if p in code_snippet])
            found_crit.extend(matched_breaches)

            result = {
                "status": "rejected",
                "risk_level": "critical",
                "category": category,
                # Deterministic hits are not appealable: there is no argument to
                # weigh, only a pattern that is present or absent.
                "appealable": False,
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
                    audit_result["category"] = category
                    audit_result["appealable"] = True

                    # --- CALIBRATION GATE ---
                    # A 3B model approving code written by a frontier model is only
                    # meaningful where it has demonstrably agreed with the tier
                    # above. Elsewhere its approval becomes an escalation.
                    if str(audit_result.get("status", "")).strip().lower() in ("approved", "approve", "safe"):
                        gate = calibration.may_autoapprove(TIER_NAME, category)
                        audit_result["calibration"] = gate.as_dict()
                        if not gate.trusted:
                            audit_result["status"] = "escalate"
                            audit_result["local_opinion"] = "approved"
                            audit_result["critique"] = (
                                f"[UNCALIBRATED] System 2c leans APPROVED but may not close the "
                                f"review in category '{category}': {gate.reason}. "
                                f"Escalate to System 2 (court / cloud audit). "
                                f"Local reasoning: {audit_result.get('critique', 'n/a')}"
                            )

                    log_tool_performance("guardrail_audit", True, time.time() - start_time)
                    log_swarm_event("DECISION", {
                        "tool": "guardrail_agent",
                        "confidence": 0.8,
                        "result": audit_result.get("status", "unknown").upper(),
                        "logic": audit_result.get("critique", "LLM Audit"),
                        "output": audit_result.get("critique", "LLM Audit")
                    })
                    return audit_result
        except Exception:
            log_tool_performance("guardrail_audit", False, time.time() - start_time)

        # A dead audit is not a passing audit. This used to return "approved",
        # which meant a 404 against Ollama silently rubber-stamped every snippet
        # that reached it. "escalate" costs an extra tier; auto-approve costs a
        # breach.
        fallback_result = {
            "status": "escalate",
            "risk_level": "unknown",
            "category": category,
            "appealable": False,
            "critique": (
                "System 2c could not complete the audit (local model unreachable or "
                "unparseable response). No verdict was formed — escalate to System 2. "
                "This is NOT an approval."
            ),
        }
        log_swarm_event("DECISION", {
            "tool": "guardrail_agent",
            "confidence": 0.0,
            "result": "ESCALATE",
            "logic": "Audit unavailable — fail-open removed",
            "output": fallback_result["critique"]
        })
        return fallback_result

# Singleton Instance
guardrail_agent = GuardrailAgent()

# Functional wrapper for backwards compatibility
def run_guardrail_audit(code_snippet: str, task_context: str = ""):
    return guardrail_agent.run_audit(code_snippet, task_context)
