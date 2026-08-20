import sys
from pathlib import Path

# Add core to sys.path so we can import the tools
sys.path.insert(0, str(Path("core").resolve()))

from tools.infrastructure.server import ingest_file_to_hivemind

files = [
    "STRUCTURE.md",
    "KENBUN.md",
    "docs/OBSERVATORY.md",
    "docs/SVE.md",
    "docs/MODELS.md",
    "docs/SCHEDULING.md",
    "docs/HONCHO.md",
    "POST_MORTEM.md"
]

for f in files:
    filepath = str(Path(f).resolve())
    print(f"Ingesting {f}...")
    try:
        res = ingest_file_to_hivemind(filepath, "architecture,core,system-map")
        print(f"Result: {res}")
    except Exception as e:
        print(f"Error for {f}: {e}")

