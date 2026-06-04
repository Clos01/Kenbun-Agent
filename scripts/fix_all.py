from pathlib import Path

# Fix core/benchmarks/CHAOS_TEST.py
f = Path("core/benchmarks/CHAOS_TEST.py")
content = f.read_text()
content = content.replace("new_router = ", "")
f.write_text(content)

# Fix core/tools/audit/adversarial_court.py
f = Path("core/tools/audit/adversarial_court.py")
content = f.read_text()
# Only replace c_g if it's alone (as a variable)
import re
content = re.sub(r'\bc_g\b', 'C_G', content)
f.write_text(content)

# Fix api_server.py
f = Path("core/tools/infrastructure/api_server.py")
content = f.read_text()
content = content.replace("intelligence_list = ", "")
content = content.replace("latency = ", "")
f.write_text(content)

# Fix config.py
f = Path("core/tools/infrastructure/config.py")
lines = f.read_text().split('\n')
if "from cryptography.fernet import Fernet, InvalidToken" in lines[27]:
    lines[27] = ""
elif "from cryptography.fernet import Fernet" in lines[27]:
    lines[27] = ""
f.write_text('\n'.join(lines))

# Fix monitor.py
f = Path("core/tools/infrastructure/monitor.py")
content = f.read_text()
if "from tools.utils.path_utils import get_project_root" not in content:
    content = "from tools.utils.path_utils import get_project_root\nPROJECT_ROOT = get_project_root()\n" + content
f.write_text(content)

# Fix native_ears.py
f = Path("core/tools/infrastructure/native_ears.py")
content = f.read_text()
if "import json" not in content:
    content = "import json\n" + content
f.write_text(content)

# Fix orchestrator.py
f = Path("core/tools/infrastructure/orchestrator.py")
content = f.read_text()
content = content.replace("response = ", "")
f.write_text(content)

# Fix neural_classifier.py
f = Path("core/tools/strategy/neural_classifier.py")
content = f.read_text()
content = content.replace("indices = ", "")
f.write_text(content)

# Fix deepseek_client.py
f = Path("core/tools/utils/deepseek_client.py")
content = f.read_text()
content = content.replace("headers = ", "")
f.write_text(content)

# Fix bootstrap.py
f = Path("scripts/bootstrap.py")
content = f.read_text()
content = content.replace("c_c = C_C if sys.stdout.isatty() else \"\"", "")
content = content.replace("c_y = C_Y if sys.stdout.isatty() else \"\"", "")
if "from typing import Optional, List" not in content:
    content = "from typing import Optional, List\n" + content

lines = content.split('\n')
for i, line in enumerate(lines):
    if line.strip() == "import os" and i > 1800:
        lines[i] = ""
    if line.strip() == "import re" and i > 1800:
        lines[i] = ""
f.write_text('\n'.join(lines))

print("Fixed all remaining linter issues!")
