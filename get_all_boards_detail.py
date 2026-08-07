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

boards = [
    ("NeverMiss Board", "1821314980880844507"),
    ("CRG Board", "1814746129032546126"),
    ("Take-Home Assessment", "1816489052271019820"),
    ("Main Board", "1803497714239931407")
]

for name, board_id in boards:
    print(f"\n=======================================================")
    print(f"📌 BOARD: {name} (ID: {board_id})")
    print(f"=======================================================")
    try:
        details = planka_get_board(board_id)
        print(details)
    except Exception as e:
        print(f"Error fetching board {name}: {e}")
