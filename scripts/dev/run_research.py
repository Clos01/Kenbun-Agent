import subprocess
import json
import os
import sys

env = os.environ.copy()
env["PYTHONPATH"] = "/path/to/Kenbun/core:/path/to/Kenbun/core/tools:/path/to/Kenbun"
p = subprocess.Popen(
    ["/path/to/Kenbun/core/.venv/bin/python3", "-u", "/path/to/Kenbun/core/tools/infrastructure/server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=env,
    text=True
)

init_req = '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0.0"}}}\n'
p.stdin.write(init_req)
p.stdin.flush()
p.stdout.readline() # drop init response

req = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "research_with_gemini",
        "arguments": {
            "query": "Better way to allow Tailscale network traffic to Docker Desktop containers on Windows 11 without manually adding Windows Defender Firewall rules for each port.",
            "tech_key": "docker"
        }
    }
}
p.stdin.write(json.dumps(req) + "\n")
p.stdin.flush()

import select
r, _, _ = select.select([p.stdout], [], [], 60.0)
if r:
    print(p.stdout.readline())
else:
    print("TIMEOUT")
p.terminate()
