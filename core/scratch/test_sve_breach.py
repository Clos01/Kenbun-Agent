import sys
import os
from pathlib import Path
from tools.infrastructure.sovereign_decorators import sovereign_logic

@sovereign_logic(strict=True)
def poisoned_function():
    # This should breach multiple knots
    return os.getenv("DB_PASSWORD")

if __name__ == "__main__":
    try:
        poisoned_function()
    except Exception as e:
        print(f"✅ CAUGHT BREACH: {e}")
