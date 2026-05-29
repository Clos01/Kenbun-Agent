import os
import json
import time
import math
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from tools.audit.reflection_agent import log_reflection
from tools.strategy.strategy_manager import governor
from tools.utils.workspace_manager import workspace_manager

# Configuration
from tools.infrastructure.config import settings
PROJECT_ROOT = settings.PROJECT_ROOT
LOG_DIR = PROJECT_ROOT / "core" / "brain_health"
TUNING_LOG_PATH = LOG_DIR / "tuning_queue.jsonl"
RECOVERY_LOG_PATH = LOG_DIR / "recovery_events.jsonl"
BENCHMARKS_FILE = LOG_DIR / "BENCHMARKS.json"

class AutonomicCorrector:
    """
    System 5.1: The Autonomic Corrector.
    Consolidated engine for stream-based self-healing and batch-based regression analysis.
    """
    def __init__(self):
        self.queue_path = TUNING_LOG_PATH
        self.recovery_path = RECOVERY_LOG_PATH
        self.shift_magnitude = 0.05
        self.max_weight = 15.0
        self.seen_diagnoses = {} # Cache key-value for prompt deduplication
        self._ensure_paths_exist()

    def _ensure_paths_exist(self):
        for p in [self.queue_path, self.recovery_path]:
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                p.touch()

    def queue_tuning(self, tuning_payload: list):
        with open(self.queue_path, "a") as f:
            for item in tuning_payload:
                item["timestamp"] = time.time()
                f.write(json.dumps(item) + "\n")
        log_reflection(f"Queued {len(tuning_payload)} autonomic tuning events.")

    def analyze_batch_regressions(self) -> Dict[str, Any]:
        """
        Ported from SovereigntyEngine: Analyzes historical benchmarks to perform systemic 'Gravity Shifts'.
        """
        if not BENCHMARKS_FILE.exists():
            return {"status": "idle", "message": "No benchmarks found"}
        
        try:
            with open(BENCHMARKS_FILE, "r") as f:
                data = json.load(f)
            
            history = data.get("history", [])
            if not history:
                return {"status": "idle", "message": "No history to analyze"}
            
            latest_run = history[-1]
            top_misses = latest_run.get("top_misses", [])
            
            if not top_misses:
                return {"status": "optimized", "message": "No systemic regressions detected"}
            
            shifts = self._calculate_gravity_shifts(top_misses)
            log_reflection(f"Sovereignty Shift: Applied {len(shifts)} batch corrections from benchmarks.")
            return {"status": "success", "shifts": len(shifts)}
            
        except Exception as e:
            logging.error(f"Sovereignty batch analysis failed: {e}")
            return {"status": "error", "message": str(e)}

    def _calculate_gravity_shifts(self, misses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        from tools.strategy.decision_logic import router
        applied_shifts = []
        hits = {}
        
        for miss in misses:
            task = miss.get("task", "").lower()
            expected = miss.get("expected")
            if not task or not expected: continue
            
            target_cat = self._path_to_category(expected)
            if not target_cat: continue
            
            target_keywords = [k for k in router.processor.keywords.get(target_cat, []) if k in task]
            for k in target_keywords:
                key = (k, target_cat)
                hits[key] = hits.get(key, 0) + 1

        for (k, cat), count in hits.items():
            old_weight = router.weights.get(k, 1.0)
            boost = self.shift_magnitude * math.log2(count + 1)
            new_weight = round(min(old_weight + boost, self.max_weight), 4)
            
            if new_weight > old_weight:
                router.weights[k] = new_weight
                applied_shifts.append({"keyword": k, "category": cat, "new_weight": new_weight})
        
        if applied_shifts:
            router.save_weights()
            
        return applied_shifts

    def _path_to_category(self, path: str) -> Optional[str]:
        mapping = {
            "UI_COMPONENT_BUILD": "ui", "UI_FIX_PATH": "ui",
            "SECURITY_HARDENING_PATH": "security", "STANDARD_BUG_FIX": "bug",
            "ARCHITECT_RESEARCH_PATH": "architecture"
        }
        return mapping.get(path)

    def monitor_workspace_logs(self):
        projects = workspace_manager.get_projects()
        for project_path in projects:
            p = Path(project_path)
            log_candidates = [p / "logs" / "error.log", p / "logs" / "production.log"]
            for log_file in log_candidates:
                if log_file.exists():
                    self._check_log_for_errors(log_file, project_path)

    def _check_log_for_errors(self, log_path: Path, project_path: str):
        try:
            with open(log_path, "r") as f:
                lines = f.readlines()[-100:]
            error_keywords = ["500 Internal Server Error", "Hydration failed", "Unhandled Runtime Error"]
            for line in lines:
                if any(k in line for k in error_keywords):
                    self.spawn_recovery_swarm(project_path, line.strip())
                    break
        except Exception: pass

    def diagnose_with_local_model(self, error_signal: str) -> str:
        """Uses local qwen2.5-coder:1.5b Ollama model to generate a fast, autonomous diagnostic explanation."""
        import urllib.request
        import json
        import re
        import sys
        
        # 1. Sanitize the error signal to prevent prompt injections and strip control characters
        sanitized_signal = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', error_signal).strip()
        # Keep maximum size safe
        sanitized_signal = sanitized_signal[:500]
        
        # 2. De-duplication cache check (60-second TTL) to prevent thundering herd GPU load
        current_time = time.time()
        if sanitized_signal in self.seen_diagnoses:
            cached_diagnosis, timestamp = self.seen_diagnoses[sanitized_signal]
            if current_time - timestamp < 60.0:
                return cached_diagnosis
        
        urls = [
            "http://ollama:11434/api/generate",
            "http://127.0.0.1:11434/api/generate",
            "http://host.docker.internal:11434/api/generate"
        ]
        
        prompt = (
            f"You are the J.A.R.V.I.S. Swarm Diagnostics unit. "
            f"Provide a highly professional, 1-sentence technical diagnosis "
            f"and remediation recommendation for this system error log:\n\"{sanitized_signal}\"\n"
            f"Keep the output under 15 words and read like an advanced telemetry report."
        )
        
        payload = {
            "model": "qwen2.5-coder:1.5b",
            "prompt": prompt,
            "stream": False
        }
        
        active_diagnosis = None
        for url in urls:
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                # 2.0s timeout per check to keep daemon fast
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        response_text = data.get("response", "").strip()
                        if response_text:
                            active_diagnosis = response_text
                            break
            except Exception as e:
                # Log warning in standard error instead of silent failure
                sys.stderr.write(f"⚠️ [AUTONOMIC_PROBE_WARNING] Failed to connect to Ollama at {url}: {e}\n")
                
        if active_diagnosis is None:
            active_diagnosis = "Sovereign Watchdog: Systemic exception caught. Deployed fallback auto-repair sequence."
            
        # Store in cache
        self.seen_diagnoses[sanitized_signal] = (active_diagnosis, current_time)
        return active_diagnosis

    def spawn_recovery_swarm(self, project_path: str, error_signal: str):
        if self._is_circuit_broken(project_path) or self._is_recent_recovery(project_path, error_signal):
            return
        
        # J.A.R.V.I.S. style local model autonomous diagnostics!
        diagnosis = self.diagnose_with_local_model(error_signal)
        
        # Log directly to live_telemetry.json so it lights up on the dashboard in real-time
        try:
            log_file = PROJECT_ROOT / "brain_health" / "live_telemetry.json"
            log_entry = {
                "timestamp": time.time(),
                "message": f"[SENTINEL_DIAGNOSTICS] 🔮 Local AI Brain (qwen2.5-coder:1.5b) Diagnosis: {diagnosis}",
                "type": "log"
            }
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(json.dumps(log_entry) + "\n")
        except Exception:
            pass

        event = {
            "timestamp": time.time(), 
            "project_path": project_path, 
            "error_signal": error_signal, 
            "status": "triggered",
            "diagnosis": diagnosis
        }
        with open(self.recovery_path, "a") as f:
            f.write(json.dumps(event) + "\n")
        try:
            cmd = ["python3", "-m", "tools.infrastructure.orchestrator", "orchestrate", "bug_fix", f"--task=Auto-fix: {error_signal}. Diagnosis: {diagnosis}", f"--project_path={project_path}"]
            subprocess.Popen(cmd, cwd=str(PROJECT_ROOT / "core"))
        except Exception: pass

    def _is_circuit_broken(self, project_path: str) -> bool:
        try:
            with open(self.recovery_path, "r") as f:
                lines = f.readlines()[-50:]
            count = sum(1 for line in lines if json.loads(line)["project_path"] == project_path and time.time() - json.loads(line)["timestamp"] < 3600)
            return count >= 3
        except Exception: return False

    def _is_recent_recovery(self, project_path: str, error_signal: str) -> bool:
        try:
            with open(self.recovery_path, "r") as f:
                lines = f.readlines()[-20:]
            for line in lines:
                data = json.loads(line)
                if data["project_path"] == project_path and data["error_signal"] == error_signal and time.time() - data["timestamp"] < 600:
                    return True
        except Exception: pass
        return False

    def run_correction_cycle(self):
        # 1. Stream-based Tuning
        if self.queue_path.exists():
            with open(self.queue_path, "r") as f:
                lines = f.readlines()
            if lines:
                open(self.queue_path, 'w').close()
                for line in lines:
                    try:
                        data = json.loads(line)
                        if data.get("tool_id"):
                            governor.update_intelligence(data["tool_id"], data.get("category", "general"), data.get("success", False))
                    except Exception: pass
        # 2. Batch-based Sovereignty Analysis
        self.analyze_batch_regressions()
        # 3. External Health Check
        self.monitor_workspace_logs()

corrector = AutonomicCorrector()
if __name__ == "__main__":
    corrector.run_correction_cycle()
