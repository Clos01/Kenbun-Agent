import re
from pathlib import Path

# Fix core/tools/audit/adversarial_court.py
f = Path("core/tools/audit/adversarial_court.py")
content = f.read_text()
content = content.replace("C_G", '""')
f.write_text(content)

# Fix config.py
f = Path("core/tools/infrastructure/config.py")
content = f.read_text()
if "from cryptography.fernet import Fernet\n" in content:
    content = content.replace("from cryptography.fernet import Fernet\n", "", 1) # remove the redefined one
if "InvalidToken" not in content and "from cryptography.fernet import Fernet, InvalidToken" not in content:
    content = "from cryptography.fernet import Fernet, InvalidToken\n" + content
f.write_text(content)

# Fix orchestrator.py
f = Path("core/tools/infrastructure/orchestrator.py")
content = f.read_text()
content = re.sub(r'^\s*response\s*=\s*', '', content, flags=re.MULTILINE)
f.write_text(content)

# Fix neural_classifier.py
f = Path("core/tools/strategy/neural_classifier.py")
content = f.read_text()
content = content.replace("leaf_self", "self")
content = content.replace("leaf_indices", "indices")
f.write_text(content)

# Fix bootstrap.py
f = Path("scripts/bootstrap.py")
lines = f.read_text().split('\n')
for i in range(len(lines)):
    if "c_c =" in lines[i]:
        lines[i] = ""
    if "c_y =" in lines[i]:
        lines[i] = ""
    if "import os" in lines[i] and i > 1800:
        lines[i] = ""
    if "import re" in lines[i] and i > 1800:
        lines[i] = ""
f.write_text('\n'.join(lines))

print("Fixed round 2!")
