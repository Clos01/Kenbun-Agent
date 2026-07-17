import subprocess
import time
import os
import signal

p = subprocess.Popen(
    ["~/Dev/Kenbun/core/.venv/bin/python3", "-u", "~/Dev/Kenbun/core/tools/infrastructure/server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

time.sleep(2)
p.send_signal(signal.SIGTERM)
p.wait()
print(f"Exit code: {p.returncode}")
