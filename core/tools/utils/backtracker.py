"""
Agentic Backtracker — File checkpoint/restore for preventing doom loops.

When the AI gets stuck trying fix after fix, the system can:
1. Revert to a known-good checkpoint
2. Tell the AI: "Approaches A and B failed. Try something completely different."

This prevents the "spaghetti code" spiral where each fix makes things worse.
"""
import os
import json
import shutil
from datetime import datetime
from pathlib import Path


# --- CONFIGURATION ---
CHECKPOINT_DIR = Path.home() / ".kenbun" / "checkpoints"
MAX_CHECKPOINTS_PER_FILE = 10
METADATA_FILE = "checkpoints_index.json"

# Immutable allowed roots loaded once at module startup to prevent configuration poisoning
ALLOWED_ROOTS = []
try:
    from tools.infrastructure.config import settings
    if settings and hasattr(settings, "PROJECT_ROOT"):
        ALLOWED_ROOTS.append(os.path.realpath(str(settings.PROJECT_ROOT)))
except Exception:
    pass

try:
    from tools.utils.path_utils import get_project_root
    if get_project_root:
        ALLOWED_ROOTS.append(os.path.realpath(str(get_project_root())))
except Exception:
    pass

# Filter and clean roots to enforce absolute least privilege boundaries
_cleaned = []
for r in ALLOWED_ROOTS:
    try:
        r_abs = os.path.realpath(r)
        if r_abs not in ("/", "/Users", "/home", "/private", "/var", "/etc", "/tmp"):
            _cleaned.append(r_abs)
    except Exception:
        pass
ALLOWED_ROOTS = list(set(_cleaned))

if not ALLOWED_ROOTS:
    # Strictly bound to CWD under fail-closed principles
    ALLOWED_ROOTS.append(os.path.realpath(os.getcwd()))


def _ensure_checkpoint_dir():
    """Create the checkpoint directory if it doesn't exist."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


def _validate_path(file_path: str) -> Path:
    """
    Validate that the input path is strictly within the allowed secure workspace boundaries.
    Uses canonicalized absolute paths and os.path.commonpath whitelist validation to block breakouts.
    """
    if not file_path:
        raise ValueError("Path is empty or not specified.")

    # 1. Load active project root deterministically (Fail-closed)
    try:
        from tools.infrastructure.config import settings
        project_root = settings.PROJECT_ROOT.resolve()
    except Exception:
        try:
            from tools.utils.path_utils import get_project_root
            project_root = get_project_root().resolve()
        except Exception:
            raise ValueError("Fail-Closed: Workspace configuration load failed.")

    # 2. Strict anchor validation to prevent system-level root configurations
    if project_root.parent == project_root or str(project_root).lower().rstrip("/\\") in (
        "", "/", "c:", "d:", "c:\\", "d:\\", "/users", "/home", "/private", "/var", "/etc", "/tmp"
    ):
        raise ValueError("Security Violation: Project root is anchored at an unsafe system directory.")

    # 3. Resolve target path completely to check boundaries
    try:
        path = Path(file_path).resolve()
    except Exception:
        raise ValueError("Security Violation: The requested path is invalid.")

    # 4. Enforce strict containment check
    is_safe = False
    try:
        if hasattr(path, "is_relative_to"):
            if path.is_relative_to(project_root):
                is_safe = True
        else:
            path.relative_to(project_root)
            is_safe = True
    except (ValueError, RuntimeError):
        pass
            
    if not is_safe:
        raise ValueError("Security Violation: The requested path is outside secure workspace boundaries.")
    
    return path



def _load_index() -> dict:
    """Load the checkpoint index."""
    index_path = CHECKPOINT_DIR / METADATA_FILE
    if index_path.exists():
        try:
            return json.loads(index_path.read_text())
        except Exception:
            return {"checkpoints": []}
    return {"checkpoints": []}


def _save_index(index: dict):
    """Save the checkpoint index."""
    index_path = CHECKPOINT_DIR / METADATA_FILE
    index_path.write_text(json.dumps(index, indent=2))


def _make_checkpoint_filename(file_path: str, label: str) -> str:
    """Generate a unique checkpoint filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(file_path).name
    safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
    return f"{timestamp}_{safe_label}_{base}"


def save_checkpoint(file_path: str, label: str = "auto") -> str:
    """
    Snapshot a file's current state before making changes.

    Use this before attempting a risky fix. If the fix fails,
    you can restore_checkpoint() to revert.

    Args:
        file_path: Absolute path to the file to snapshot
        label: A descriptive label (e.g., "before_refactor", "working_state")

    Returns:
        Confirmation with the checkpoint ID.
    """
    _ensure_checkpoint_dir()

    try:
        source = _validate_path(file_path)
    except ValueError:
        return "❌ Security Violation: The requested path is outside secure workspace boundaries."

    # Open source file securely using file descriptor to prevent TOCTOU symlink swaps
    fd = None
    try:
        fd = os.open(str(source), os.O_RDONLY | os.O_NOFOLLOW)
        # Perform atomic fstat on the open file descriptor to prevent DoS via special file streams
        stat_info = os.fstat(fd)
        import stat
        if not stat.S_ISREG(stat_info.st_mode):
            os.close(fd)
            fd = None
            return "❌ Security Violation: Only regular files are allowed."
            
        # Block hard-links to prevent shared file corruption / modifications
        if stat_info.st_nlink > 1:
            os.close(fd)
            fd = None
            return "❌ Security Violation: Hard-linked files are forbidden."

        # Perform safe resource constraint checks
        if stat_info.st_size > 10 * 1024 * 1024:  # 10 MB Limit
            os.close(fd)
            fd = None
            return "❌ Security Violation: File size exceeds safe limits."

        # Once wrapped, os.fdopen owns the fd. Set fd to None so we don't manual-close in except.
        wrapped_fd = fd
        fd = None
        with os.fdopen(wrapped_fd, 'rb') as f:
            content = f.read()
    except Exception:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
        return "❌ Failed to perform safe file operations."

    # Generate checkpoint filename and write safely
    cp_filename = _make_checkpoint_filename(file_path, label)
    cp_path = CHECKPOINT_DIR / cp_filename
    try:
        cp_path.write_bytes(content)
    except Exception:
        return "❌ Failed to perform safe file operations."

    # Update index
    index = _load_index()
    entry = {
        "id": cp_filename,
        "original_path": str(source.resolve()),
        "checkpoint_path": str(cp_path),
        "label": label,
        "timestamp": datetime.now().isoformat(),
        "size_bytes": len(content),
    }
    index["checkpoints"].append(entry)

    # Prune: keep only MAX per file
    file_checkpoints = [
        c for c in index["checkpoints"]
        if c["original_path"] == str(source.resolve())
    ]
    if len(file_checkpoints) > MAX_CHECKPOINTS_PER_FILE:
        # Remove oldest
        oldest = file_checkpoints[0]
        index["checkpoints"].remove(oldest)
        old_path = Path(oldest["checkpoint_path"])
        if old_path.exists():
            old_path.unlink()

    _save_index(index)

    return (
        f"## 🔄 Checkpoint Saved\n\n"
        f"**File:** `{source.name}`\n"
        f"**Label:** `{label}`\n"
        f"**ID:** `{cp_filename}`\n"
        f"**Size:** {len(content):,} bytes\n\n"
        f"Use `restore_checkpoint(\"{file_path}\", \"{label}\")` to revert."
    )


def restore_checkpoint(file_path: str, label: str = "") -> str:
    """
    Revert a file to a previous checkpoint.

    If no label is provided, reverts to the most recent checkpoint for that file.

    Args:
        file_path: The original file path to restore
        label: Optional — specific checkpoint label. If empty, uses the latest.

    Returns:
        Confirmation or error message.
    """
    _ensure_checkpoint_dir()

    try:
        target_path = _validate_path(file_path)
    except ValueError:
        return "❌ Security Violation: The requested path is outside secure workspace boundaries."

    index = _load_index()
    target = str(target_path)

    # Find matching checkpoints for this file
    file_checkpoints = [
        c for c in index["checkpoints"]
        if c["original_path"] == target
    ]

    if not file_checkpoints:
        return f"❌ No checkpoints found for: {file_path}"

    # Find the right checkpoint
    if label:
        matches = [c for c in file_checkpoints if c["label"] == label]
        if not matches:
            available = [c["label"] for c in file_checkpoints]
            return f"❌ No checkpoint with label '{label}'. Available: {available}"
        checkpoint = matches[-1]  # Latest with that label
    else:
        checkpoint = file_checkpoints[-1]  # Most recent

    # Verify checkpoint file exists
    cp_path = Path(checkpoint["checkpoint_path"])
    if not cp_path.exists():
        return "❌ Failed to perform safe file operations."

    # Read checkpoint file securely
    try:
        content = cp_path.read_bytes()
    except Exception:
        return "❌ Failed to perform safe file operations."

    # Restore to target securely using file descriptor (with O_NOFOLLOW to prevent symlink TOCTOU)
    fd = None
    try:
        # Open WITHOUT O_TRUNC to prevent premature data truncation of hard-links
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o644)
        stat_info = os.fstat(fd)
        import stat
        if not stat.S_ISREG(stat_info.st_mode):
            os.close(fd)
            fd = None
            return "❌ Security Violation: Only regular files are allowed."

        # Block hard-links to prevent shared file corruption
        if stat_info.st_nlink > 1:
            os.close(fd)
            fd = None
            return "❌ Security Violation: Hard-linked files are forbidden."

        # Truncate atomically now that the file descriptor is verified safe
        os.ftruncate(fd, 0)

        wrapped_fd = fd
        fd = None
        with os.fdopen(wrapped_fd, 'wb') as f:
            f.write(content)
    except Exception:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
        return "❌ Failed to perform safe file operations."

    return (
        f"## 🔄 Checkpoint Restored\n\n"
        f"**File:** `{Path(file_path).name}`\n"
        f"**Reverted to:** `{checkpoint['label']}` ({checkpoint['timestamp']})\n"
        f"**Size:** {checkpoint['size_bytes']:,} bytes\n\n"
        f"The file has been restored to its checkpointed state."
    )


def list_checkpoints(file_path: str = "") -> str:
    """
    List all saved checkpoints, optionally filtered by file.

    Args:
        file_path: Optional — filter to show only checkpoints for this file.

    Returns:
        A formatted list of all checkpoints.
    """
    _ensure_checkpoint_dir()
    index = _load_index()

    checkpoints = index.get("checkpoints", [])

    if file_path:
        try:
            target_path = _validate_path(file_path)
            target = str(target_path)
        except ValueError:
            return "❌ Security Violation: The requested path is outside secure workspace boundaries."
        checkpoints = [c for c in checkpoints if c["original_path"] == target]

    if not checkpoints:
        scope = f" for `{Path(file_path).name}`" if file_path else ""
        return f"## 🔄 Checkpoints\n\nNo checkpoints found{scope}."

    output = [f"## 🔄 Checkpoints ({len(checkpoints)} total)\n"]

    for cp in checkpoints:
        file_name = Path(cp["original_path"]).name
        exists = "✅" if Path(cp["checkpoint_path"]).exists() else "❌ missing"
        output.append(
            f"- **`{cp['label']}`** — `{file_name}` "
            f"({cp['timestamp'][:16]}) [{cp['size_bytes']:,}B] {exists}"
        )

    return "\n".join(output)
