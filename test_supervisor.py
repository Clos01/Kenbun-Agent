import sys
import os
import asyncio
from pathlib import Path

# Dynamic import root
project_root = str(Path(__file__).resolve().parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.tools.audit.adversarial_court import AdversarialCourt

async def main():
    code = """
def check_and_start_docker_swarm(project_root: Path):
    import subprocess, shutil, time
    docker_bin = shutil.which("docker")
    if not docker_bin: return
    try:
        res = subprocess.run([docker_bin, "ps", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=2)
        if "fastmcp_server" in res.stdout or "ollama_server" in res.stdout: return
    except Exception: return
    subprocess.run([docker_bin, "compose", "up", "-d"], cwd=str(project_root), check=True)
"""
    proposal = "I have refactored the codebase to use uv tool install, added check_and_start_docker_swarm hook, and silenced chroma telemetry. Are there security issues?"

    court = AdversarialCourt()
    try:
        result = await court.run_trial(proposal, code)
        print("RESULT:")
        print(result.get("judge_verdict"))
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
