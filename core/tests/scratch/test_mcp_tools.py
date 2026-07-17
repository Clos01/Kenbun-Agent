import subprocess
import json
import os

env = os.environ.copy()
env['PYTHONPATH'] = "~/Dev/Kenbun/core:~/Dev/Kenbun/core/tools:~/Dev/Kenbun"

p = subprocess.Popen(
    ["~/Dev/Kenbun/core/.venv/bin/python3", "-u", "~/Dev/Kenbun/core/tools/infrastructure/server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=env,
    text=True
)

init_msg = '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}\n'
p.stdin.write(init_msg)
p.stdin.flush()
print("Init response:", p.stdout.readline().strip())

initialized_msg = '{"jsonrpc": "2.0", "method": "notifications/initialized"}\n'
p.stdin.write(initialized_msg)
p.stdin.flush()

list_tools_msg = '{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}\n'
p.stdin.write(list_tools_msg)
p.stdin.flush()
print("Tools list:", p.stdout.readline().strip())

p.terminate()
