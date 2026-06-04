from functools import lru_cache
import os
from pathlib import Path

@lru_cache(maxsize=1)
def get_project_root() -> Path:
    """Robustly find the project root starting from this file's location with caching."""
    # Priority 1: Explicit Environment Override
    if os.getenv("PROJECT_ROOT"):
        return Path(os.getenv("PROJECT_ROOT"))

    # Priority 2: Docker Container Standard Mount
    docker_path = Path("/app")
    if docker_path.exists() and (docker_path / "tools").exists():
        return docker_path

    # Priority 3: Traversal with Boundaries
    # This file is at core/tools/utils/path_utils.py, parent.parent.parent.parent is root
    current = Path(__file__).resolve().parent.parent.parent.parent
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists() or (parent / "core").exists():
            return parent
            
    return current
