import sys
import os
import asyncio
from pathlib import Path

# Add core to path
sys.path.append("/Users/carlosrivas/Dev/Kenbun/core")
sys.path.append("/Users/carlosrivas/Dev/Kenbun/core/tools")

from tools.infrastructure.server import consult_supervisor

with open("/Users/carlosrivas/Dev/Kenbun/core/tools/infrastructure/server.py", "r") as f:
    code = f.read()

print("Calling supervisor...", flush=True)
result = consult_supervisor(
    user_proposal="Please review and clean up this MCP server code. Suggest improvements for readability, error handling, and performance.",
    code_snippet=code,
    iterative_mode=True
)
print("Supervisor Result:")
print(result)
