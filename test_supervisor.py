import sys
import asyncio
from pathlib import Path
import os

# Ensure we can import from core
sys.path.insert(0, '/Users/carlosrivas/Dev/Kenbun/core')

from tools.audit.supervisor_agent import run_supervisor_audit

async def main():
    print("Starting manual supervisor audit test...")
    try:
        res = await run_supervisor_audit(
            user_proposal="Test the supervisor.",
            code_snippet="def foo(): pass",
            memory_context="",
            tech_key=""
        )
        print("Result:", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
