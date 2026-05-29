import os
import time
import fcntl
from contextlib import contextmanager
from pathlib import Path
from tools.infrastructure.config import settings

class IOLock:
    """
    Atomic File-System Lock to prevent concurrent write collisions in Parallel Swarms.
    """
    def __init__(self, lock_dir: str = None):
        if lock_dir is None:
            # Default to brain_health/locks
            self.lock_dir = settings.PROJECT_ROOT / "brain_health" / "locks"
        else:
            self.lock_dir = Path(lock_dir)
        
        self.lock_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def atomic_write(self, file_path: str):
        """
        Context manager for safe, locked file writes.
        """
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        lock_file_path = self.lock_dir / f"{Path(file_path).name}.lock"
        
        with open(lock_file_path, "w") as lock_file:
            try:
                # Exclusive lock, non-blocking (wait for it)
                fcntl.flock(lock_file, fcntl.LOCK_EX)
                print(f"🔒 LOCK ACQUIRED: {file_path}")
                yield
            finally:
                print(f"🔓 LOCK RELEASED: {file_path}")
                fcntl.flock(lock_file, fcntl.LOCK_UN)

# Global Instance
io_lock = IOLock()
