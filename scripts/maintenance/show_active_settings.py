"""Print the currently active PRIMARY_LLM_URL and CHROMA_HOST from KenbunSettings.

Run from the repo root:
    python show_active_settings.py
"""
import sys
from pathlib import Path

# KenbunSettings lives in core/tools/infrastructure/config.py and imports
# `from tools.utils.path_utils import ...`, so `core/` must be on sys.path.
CORE_DIR = Path(__file__).resolve().parent / "core"
sys.path.insert(0, str(CORE_DIR))

from tools.infrastructure.config import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()
    print(f"PRIMARY_LLM_URL = {settings.PRIMARY_LLM_URL!r}")
    print(f"CHROMA_HOST     = {settings.CHROMA_HOST!r}")


if __name__ == "__main__":
    main()
