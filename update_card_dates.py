import sys
import os
from pathlib import Path

env_path = Path(".env")
if env_path.exists():
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip("'\"")

sys.path.insert(0, str(Path("core").resolve()))

from tools.infrastructure.planka import _planka_request

updates = [
    ("1821315083481908970", "2026-07-25T23:59:59.000Z", "Scope + access checklist (gate)"),
    ("1822885120789448159", "2026-07-28T23:59:59.000Z", "Phase 2 — Kickoff: scope, SOW & pricing (gate)"),
    ("1821315083280582374", "2026-08-04T23:59:59.000Z", "Latency audit: map pipeline & measure hops"),
    ("1822886003782714858", "2026-08-11T23:59:59.000Z", "Phase 2 — Post-call evals & benchmarking (Kenbun)")
]

for card_id, due_date, name in updates:
    print(f"Updating card '{name}' ({card_id}) with due date {due_date}...")
    try:
        res = _planka_request(f"/api/cards/{card_id}", "PATCH", {"dueDate": due_date})
        print("Success:", res.get("item", {}).get("dueDate"))
    except Exception as e:
        print(f"Error updating {name}: {e}")
