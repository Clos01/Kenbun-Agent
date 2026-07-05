import sys
import io
import time
import threading
from pathlib import Path
from core.tools.infrastructure.config import settings
from datetime import datetime
from core.tools.utils.path_utils import get_project_root

class ProtocolShield(io.TextIOBase):
    def write(self, s):
        sys.stderr.write(s)
        return len(s)
    def flush(self):
        sys.stderr.flush()

def setup_stdout_redirection():
    if not sys.stdout.isatty():
        import builtins
        _original_print = builtins.print
        def _stderr_print(*args, **kwargs):
            if 'file' not in kwargs or kwargs['file'] is sys.stdout:
                kwargs['file'] = sys.stderr
            _original_print(*args, **kwargs)
        builtins.print = _stderr_print

def _tail_mcp_debug_log():
    log_path = Path(settings.PROJECT_ROOT) / "mcp_debug.log"
    for _ in range(15):
        if log_path.exists():
            break
        time.sleep(1)
    if not log_path.exists():
        return
    
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                if "[TERMCHAT]" in line:
                    sys.stderr.write(line)
                    sys.stderr.flush()
    except Exception as e:
        sys.stderr.write(f"DEBUG: Log tailer daemon error: {e}\n")
        sys.stderr.flush()

def start_log_tailer_daemon():
    _tail_thread = threading.Thread(target=_tail_mcp_debug_log, daemon=True)
    _tail_thread.start()

import contextlib

@contextlib.contextmanager
def silence_stdout():
    """Redirects stdout to stderr temporarily to protect the MCP protocol."""
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old_stdout

def debug_log(msg: str):
    log_file = get_project_root() / "mcp_debug.log"
    with open(log_file, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    sys.stderr.write(msg + "\n")
