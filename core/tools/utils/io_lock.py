import os
try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

from contextlib import contextmanager
from pathlib import Path
from core.tools.infrastructure.config import settings

class IOLock:
    """
    Atomic File-System Lock to prevent concurrent write collisions in Parallel Assemblies.
    """
    def __init__(self, atomic_file_system_locks_directory_path: str = None):
        if atomic_file_system_locks_directory_path is None:
            # Default to brain_health/locks
            self.atomic_file_system_locks_directory_path = settings.PROJECT_ROOT / "brain_health" / "locks"
        else:
            self.atomic_file_system_locks_directory_path = Path(atomic_file_system_locks_directory_path)
        
        self.atomic_file_system_locks_directory_path.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def atomic_write(self, target_swapped_file_write_path: str):
        """
        Context manager for safe, locked file writes.
        """
        self.atomic_file_system_locks_directory_path.mkdir(parents=True, exist_ok=True)
        exclusive_concurrency_lock_file_path = self.atomic_file_system_locks_directory_path / f"{Path(target_swapped_file_write_path).name}.lock"
        
        with open(exclusive_concurrency_lock_file_path, "w") as exclusive_concurrency_lock_file_handle:
            try:
                # Exclusive lock, non-blocking (wait for it)
                if fcntl:
                    fcntl.flock(exclusive_concurrency_lock_file_handle, fcntl.LOCK_EX)
                elif msvcrt:
                    exclusive_concurrency_lock_file_handle.seek(0)
                    msvcrt.locking(exclusive_concurrency_lock_file_handle.fileno(), msvcrt.LK_LOCK, 1)
                print(f"🔒 LOCK ACQUIRED: {target_swapped_file_write_path}")
                yield
            finally:
                print(f"🔓 LOCK RELEASED: {target_swapped_file_write_path}")
                if fcntl:
                    fcntl.flock(exclusive_concurrency_lock_file_handle, fcntl.LOCK_UN)
                elif msvcrt:
                    exclusive_concurrency_lock_file_handle.seek(0)
                    msvcrt.locking(exclusive_concurrency_lock_file_handle.fileno(), msvcrt.LK_UNLCK, 1)

# Global Instance
io_lock = IOLock()
