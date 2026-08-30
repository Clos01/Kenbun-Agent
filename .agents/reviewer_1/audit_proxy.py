import sys
from pathlib import Path

# Add core to sys.path
sys.path.insert(0, str(Path("~/Dev/Kenbun/core").resolve()))

from tools.infrastructure.server import consult_supervisor

proposal = "Review the Next.js API proxy route implementing tenant-id header parsing, routing allowlist, and SSRF prevention."

try:
    # Read the route.ts file contents
    route_path = Path("~/Dev/Kenbun/dashboard/src/app/api_proxy/[...slug]/route.ts")
    code = route_path.read_text(encoding="utf-8")
    
    print("Running Supervisor Audit on route.ts...")
    result = consult_supervisor(proposal, code, False)
    print("Audit Result:")
    print(result)
except Exception as e:
    print(f"Error during audit: {e}")
