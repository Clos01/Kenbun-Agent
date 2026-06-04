from pathlib import Path

# Fix neural_classifier.py imports via string replace since autoflake is annoying
nc = Path("core/tools/strategy/neural_classifier.py")
nctext = nc.read_text()
nctext = nctext.replace("import os\n", "")
nctext = nctext.replace("import json\n", "")
nctext = nctext.replace("from pathlib import Path\n", "")
nctext = nctext.replace("from typing import Dict, List, Any, Optional\n", "from typing import Dict, List, Any\n")
nctext = nctext.replace("from sklearn.model_selection import train_test_split\n", "")
nc.write_text(nctext)

# Fix bootstrap.py specific lines
boot = Path("scripts/bootstrap.py")
lines = boot.read_text().split("\n")

for i, line in enumerate(lines):
    # F841 at 550
    if i == 549 and "c_m = c_c = c_y = c_r =" in line: # line 550 is index 549
        lines[i] = line.replace(" c_c =", "")
    # F841 at 610
    if i == 609 and "c_m = c_c = c_y = c_r =" in line:
        lines[i] = line.replace(" c_c =", "")
    # F841 at 1684
    if i == 1683 and "c_m = c_g = c_c = c_y =" in line:
        lines[i] = line.replace(" c_y =", "")
    # F811 at 1879
    if i == 1878 and "import os" in line:
        lines[i] = ""
    # F811 at 1897
    if i == 1896 and "import re" in line:
        lines[i] = ""

boot.write_text("\n".join(lines))
print("Fixed finally.")
