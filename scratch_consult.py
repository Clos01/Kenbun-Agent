import sys
from pathlib import Path
import asyncio

# Setup environment
env_path = Path(".env")
if env_path.exists():
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "=" in line:
                import os
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip("'\"")

sys.path.insert(0, str(Path("core").resolve()))

from tools.audit.supervisor_agent import ask_supervisor

proposal = """Please review and rewrite this estimate disclaimer to sound highly professional, legally protective for a flooring company, and clear for the client. The goal is to set firm expectations that the contractor is not liable for free subfloor replacement if the demolition uncovers or causes severe delamination of the plywood. Make it polished."""

code = """Material Requirements: This is a Labor-Only quote. You will need to supply approximately 1,400 sq ft of LVP material to account for standard 10% waste and cuts.

Subfloor Disclaimer: Because the existing floor is engineered hardwood glued or nailed to plywood, ripping it up carries a risk of damaging or delaminating the plywood subfloor beneath it. This estimate covers standard prep and removal. If the plywood is heavily damaged during demolition and requires extensive patching, leveling, or partial replacement before the new LVP can be laid, that additional subfloor repair will be discussed and quoted on-site."""

print("Calling supervisor...")
result = asyncio.run(ask_supervisor(user_proposal=proposal, code_snippet=code, iterative_mode=True))
print("SUPERVISOR RESPONSE:")
print(result)
