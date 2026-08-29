import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path("~/Dev/Kenbun/core").resolve()))

from tools.infrastructure.server import consult_supervisor

files_to_audit = {
    "core/tools/memory/postgres_client.py": "~/Dev/Kenbun/core/tools/memory/postgres_client.py",
    "core/tools/strategy/strategy_manager.py": "~/Dev/Kenbun/core/tools/strategy/strategy_manager.py",
    "core/tools/utils/bayesian.py": "~/Dev/Kenbun/core/tools/utils/bayesian.py"
}

for name, path in files_to_audit.items():
    print(f"\n========================================\nAUDITING: {name}\n========================================")
    content = Path(path).read_text()
    proposal = f"Audit the recent changes in {name} that add tracking of success_count and failure_count to the Bayesian weight tuning logic, ensuring robustness, proper connection cleanup, and SQL injection safety."
    try:
        res = consult_supervisor(proposal, content, iterative_mode=False)
        print(res)
    except Exception as e:
        print(f"Error auditing {name}: {e}")
