"""Smoke-test the Kenbun MCP server over stdio.

Environment- and path-driven: no secrets or absolute user paths. Reads config
from the process environment first, then the repo-local .env, then localhost
defaults.
"""

import json
import os
import subprocess

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def load_dotenv(path):
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip().strip('"').strip("'")
    return values


_dotenv = load_dotenv(os.path.join(REPO_ROOT, ".env"))


def cfg(key, default=""):
    return os.environ.get(key) or _dotenv.get(key, default)


env = os.environ.copy()
env["PYTHONPATH"] = os.pathsep.join(
    [
        os.path.join(REPO_ROOT, "core"),
        os.path.join(REPO_ROOT, "core", "tools"),
        REPO_ROOT,
    ]
)
env["CHROMA_HOST"] = cfg("CHROMA_HOST", "127.0.0.1")
env["CHROMA_PORT"] = cfg("CHROMA_PORT", "8000")
env["LM_STUDIO_PORT"] = cfg("LM_STUDIO_PORT", "1234")
env["PC_IP_ADDRESS"] = cfg("PC_IP_ADDRESS", "127.0.0.1")
gemini_key = cfg("GEMINI_API_KEY")
if gemini_key:
    env["GEMINI_API_KEY"] = gemini_key

venv_python = os.path.join(REPO_ROOT, "core", ".venv", "bin", "python3")
server_entry = os.path.join(REPO_ROOT, "core", "tools", "infrastructure", "server.py")

p = subprocess.Popen(
    [venv_python, "-u", server_entry],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=env,
    text=True,
)

init_msg = json.dumps(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        },
    }
) + "\n"
p.stdin.write(init_msg)
p.stdin.flush()

try:
    stdout_line = p.stdout.readline()
    print("STDOUT:", stdout_line)
except Exception as e:
    print("Error reading stdout:", e)

p.terminate()
