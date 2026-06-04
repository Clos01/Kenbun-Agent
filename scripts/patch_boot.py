from pathlib import Path

boot = Path("scripts/bootstrap.py")
b_text = boot.read_text()
if "from typing import Optional, List" not in b_text:
    b_text = "from typing import Optional, List\n" + b_text
    
lines = b_text.split("\n")
for i, line in enumerate(lines):
    if "import prompt_toolkit" in line:
        lines[i] = line + "  # noqa: F401"
    if line.strip() == "import os" and i > 1800:
        lines[i] = line + "  # noqa: F811"
    if line.strip() == "import re" and i > 1800:
        lines[i] = line + "  # noqa: F811"

boot.write_text("\n".join(lines))
