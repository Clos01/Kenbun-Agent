import sys
import json
from pathlib import Path

# Add core to sys.path so we can import the tools
sys.path.insert(0, str(Path("core").resolve()))

from tools.infrastructure.server import consult_supervisor

# Load the route file
route_path = Path("dashboard/src/app/api_proxy/[...slug]/route.ts").resolve()
with open(route_path, "r", encoding="utf-8") as f:
    code = f.read()

proposal = "Review the API proxy route handler code changes in dashboard/src/app/api_proxy/[...slug]/route.ts for correctness, log injection mitigations, and header strictness compliance with Milestone 1 requirements."

try:
    print("Calling consult_supervisor...")
    result_str = consult_supervisor(proposal, code, False)
    print("=== SUPERVISOR RESULT ===")
    print(result_str)
except Exception as e:
    print(f"Error executing supervisor: {e}")
    sys.exit(1)
