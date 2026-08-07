import sys
import os
from pathlib import Path

env_path = Path(".env")
if env_path.exists():
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip("'\"")

sys.path.insert(0, str(Path("core").resolve()))

from tools.infrastructure.planka import planka_get_board

print(planka_get_board("1821314980880844507"))
