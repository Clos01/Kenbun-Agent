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


def _ensure_checkpoint_dir():
    """Create the checkpoint directory if it doesn't exist."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


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

    source = Path(file_path)
    if not source.exists():
        return f"❌ File not found: {file_path}"
    if not source.is_file():
        return f"❌ Not a file: {file_path}"

    # Generate checkpoint filename and copy
    cp_filename = _make_checkpoint_filename(file_path, label)
    cp_path = CHECKPOINT_DIR / cp_filename
    shutil.copy2(source, cp_path)

    # Update index
    index = _load_index()
    entry = {
        "id": cp_filename,
        "original_path": str(source.resolve()),
        "checkpoint_path": str(cp_path),
        "label": label,
        "timestamp": datetime.now().isoformat(),
        "size_bytes": source.stat().st_size,
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
        f"**Size:** {source.stat().st_size:,} bytes\n\n"
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
    index = _load_index()

    target = str(Path(file_path).resolve())

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
        return f"❌ Checkpoint file missing: {cp_path}"

    # Restore
    shutil.copy2(cp_path, target)

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
        target = str(Path(file_path).resolve())
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
