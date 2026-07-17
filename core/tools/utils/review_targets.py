"""Materialize the actual code under review for the code_review / bug_fix pipelines.

Historically the code_review pipeline fed its reviewers (Gemini + the System 2
supervisor) only a *repo map* — file paths and bare function/class signatures —
whenever the caller passed just a ``project_path``. The adversarial court then
correctly complained it had "no implementation to judge" and rubber-stamped
APPROVED on zero evidence.

``load_review_target`` closes that gap: given whatever the caller supplied, it
returns a string of real source (or a real diff) for the reviewers to read.

Resolution order (first non-empty wins):
    1. an explicit ``code_snippet`` (caller already gave us the code)
    2. explicit ``file_path`` — one path or a comma/newline-separated list
    3. file paths mentioned in the ``task`` text that exist in the repo
    4. the working-tree diff against HEAD (``git diff HEAD``)

All file reads are confined to ``project_path`` so a crafted task string can't
make the reviewer slurp arbitrary files off disk.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

MAX_PER_FILE = 8000      # chars kept from any single file
MAX_TOTAL = 24000        # chars across the whole bundle
_PATH_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./\\-]*\.[A-Za-z0-9]{1,6}")


def _project_root(project_path: str) -> Path:
    root = Path(project_path or ".").expanduser()
    try:
        return root.resolve()
    except Exception:
        return root


def _safe_read(path: Path, root: Path) -> str | None:
    """Read ``path`` only if it resolves to a real file inside ``root``."""
    try:
        resolved = path.resolve()
        # Containment check: refuse anything that escapes the project root.
        resolved.relative_to(root)
    except (ValueError, OSError):
        return None
    if not resolved.is_file():
        return None
    try:
        text = resolved.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    if len(text) > MAX_PER_FILE:
        text = text[:MAX_PER_FILE] + f"\n\n... [truncated, {len(text) - MAX_PER_FILE} more chars] ..."
    rel = resolved.relative_to(root)
    return f"# ==== {rel} ====\n{text}"


def _split_paths(raw: str) -> list[str]:
    parts: list[str] = []
    for chunk in raw.replace(",", "\n").splitlines():
        chunk = chunk.strip().strip("`'\"")
        if chunk:
            parts.append(chunk)
    return parts


def _resolve_candidate(candidate: str, root: Path) -> Path | None:
    p = Path(candidate)
    if not p.is_absolute():
        p = root / candidate
    return p


def _bundle(blocks: list[str]) -> str:
    out: list[str] = []
    total = 0
    for block in blocks:
        if not block:
            continue
        if total + len(block) > MAX_TOTAL:
            out.append("\n\n... [review bundle truncated for context budget] ...")
            break
        out.append(block)
        total += len(block)
    return "\n\n".join(out)


def _git_diff(root: Path) -> str:
    """Return `git diff HEAD` for the repo, or '' if unavailable/empty."""
    try:
        res = subprocess.run(
            ["git", "-C", str(root), "diff", "HEAD"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    diff = (res.stdout or "").strip()
    if not diff:
        return ""
    if len(diff) > MAX_TOTAL:
        diff = diff[:MAX_TOTAL] + "\n\n... [diff truncated for context budget] ..."
    return f"# ==== working-tree diff (git diff HEAD) ====\n{diff}"


def load_review_target(
    project_path: str = "",
    file_path: str = "",
    code_snippet: str = "",
    task: str = "",
) -> str:
    """Return actual code/diff for reviewers. Never raises — worst case returns ''."""
    # 1. Caller already handed us the code.
    if code_snippet and code_snippet.strip():
        return code_snippet

    root = _project_root(project_path)
    blocks: list[str] = []
    seen: set[str] = set()

    def _add(candidate: str) -> None:
        resolved = _resolve_candidate(candidate, root)
        if resolved is None:
            return
        key = str(resolved)
        if key in seen:
            return
        block = _safe_read(resolved, root)
        if block:
            seen.add(key)
            blocks.append(block)

    # 2. Explicit file_path(s).
    if file_path and file_path.strip():
        for candidate in _split_paths(file_path):
            _add(candidate)

    # 3. File paths named in the task text (only ones that actually exist).
    if not blocks and task:
        for candidate in _PATH_RE.findall(task):
            _add(candidate)

    if blocks:
        return _bundle(blocks)

    # 4. Fall back to the working-tree diff — the natural target of
    #    "review our recent modifications".
    return _git_diff(root)
