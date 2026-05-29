"""Shared pytest fixtures."""
import sys
from tools.infrastructure.config import settings
ROOT = settings.PROJECT_ROOT
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))