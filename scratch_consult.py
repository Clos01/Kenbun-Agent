import sys
import json
from pathlib import Path

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

from tools.infrastructure.server import consult_supervisor

proposal = """We should not use Penpot right away because it is too heavy for a local rig already running LLMs. Instead, we should embed tldraw or Excalidraw directly into the Next.js Observatory dashboard as a lightweight React component. We can write a simple Kenbun tool that extracts the canvas elements as JSON, letting the user say: 'Kenbun, look at the wireframe on my dashboard and build that React component using the Limestone palette.' Should we add 'Explore Excalidraw Integration' to the Planka board?"""

print("Calling supervisor...")
result = consult_supervisor(user_proposal=proposal)
print("SUPERVISOR RESPONSE:")
print(result)
