import sys
import os
from pathlib import Path

# Load .env file manually
env_path = Path(".env")
if env_path.exists():
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                # Remove quotes if present
                val = val.strip().strip("'\"")
                os.environ[key.strip()] = val

sys.path.insert(0, str(Path("core").resolve()))

from tools.infrastructure.planka import planka_get_structure
print(planka_get_structure())
