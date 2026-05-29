import os
import json
import time
from pathlib import Path
from tools.infrastructure.sovereign_verifier import audit_code
from tools.infrastructure.config import settings
from tools.audit.reflection_agent import log_reflection

REGISTRY_PATH = settings.BRAIN_HEALTH_DIR / "sovereign_registry.json"

class SVEPulse:
    """
    System 5.1: The Sovereign Verification Pulse.
    Periodically scans the codebase for architectural drift and updates the status registry.
    """
    def __init__(self, root_dir: Path = None):
        self.root_dir = root_dir or settings.PROJECT_ROOT
        self.scan_dirs = [
            "tools/infrastructure", 
            "tools/strategy", 
            "tools/autonomic",
            "tools/audit",
            "tools/design",
            "tools/execution",
            "tools/memory",
            "tools/utils",
            "tools/craft",
            "tools/skills",
            "tools/scratch",
            "tests",
            "ingestion",
            "benchmarks",
            "training_data",
            "services",
            "scripts"
        ]

    def run_scan(self):
        """Performs a full architectural audit of core directories."""
        print("📡 SVE Pulse: Initiating architectural scan...")
        results = {"total_files": 0, "clean_files": 0, "breaches": []}
        
        for sub_dir in self.scan_dirs:
            target = self.root_dir / "core" / sub_dir
            if not target.exists(): continue
            
            for file_path in target.rglob("*.py"):
                results["total_files"] += 1
                try:
                    with open(file_path, "r") as f:
                        content = f.read()
                    
                    is_clean, breaches = audit_code(content)
                    if is_clean:
                        results["clean_files"] += 1
                    else:
                        for b in breaches:
                            b["file"] = str(file_path.relative_to(self.root_dir))
                            results["breaches"].append(b)
                            
                except Exception as e:
                    print(f"⚠️ Failed to audit {file_path}: {e}")

        self._save_results(results)
        self._broadcast_alerts(results)
        return results

    def _save_results(self, results):
        try:
            data = {}
            if REGISTRY_PATH.exists():
                with open(REGISTRY_PATH, "r") as f:
                    data = json.load(f)
            
            data["_system_pulse"] = {
                "timestamp": time.time(),
                "total_files": results["total_files"],
                "clean_files": results["clean_files"],
                "health_score": round((results["clean_files"] / results["total_files"] * 100), 1) if results["total_files"] > 0 else 100
            }
            
            # Store breaches for the dashboard
            data["_active_breaches"] = results["breaches"]
            
            with open(REGISTRY_PATH, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"❌ Failed to save pulse results: {e}")

    def _broadcast_alerts(self, results):
        if results["breaches"]:
            msg = f"🛡️ SVE Alert: Detected {len(results['breaches'])} architectural breaches in Core."
            log_reflection(msg, {"breaches": results["breaches"][:5]}) # Log top 5
        else:
            log_reflection("📡 SVE Pulse: Core infrastructure is 100% Sovereign.")

if __name__ == "__main__":
    pulse = SVEPulse()
    report = pulse.run_scan()
    print(f"Scan Complete: {report['clean_files']}/{report['total_files']} files clean.")
    if report["breaches"]:
        print(f"⚠️ Found {len(report['breaches'])} breaches.")
