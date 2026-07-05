import sys
from pathlib import Path
sys.path.insert(0, str(Path("core").resolve()))

from tools.infrastructure.planka import planka_get_structure
print(planka_get_structure())
