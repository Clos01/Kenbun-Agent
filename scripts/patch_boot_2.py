from pathlib import Path

boot = Path("scripts/bootstrap.py")
b_text = boot.read_text()
    
lines = b_text.split("\n")
for i, line in enumerate(lines):
    if line.strip().startswith("import os") and i > 1800:
        lines[i] = ""
    if line.strip().startswith("import re") and i > 1800:
        lines[i] = ""

boot.write_text("\n".join(lines))
