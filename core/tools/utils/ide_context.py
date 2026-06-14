"""
ide_context.py — AI IDE Context Detection for Kenbun Orchestrate

Detects which AI IDE is calling Kenbun so the orchestrate pipeline can
dynamically skip redundant external AI calls (e.g. Gemini) when the
calling IDE is already a capable AI (e.g. Claude Code / Antigravity).

Priority order:
  1. KENBUN_CALLER_IDE env var  (explicit, most reliable)
  2. Auto-detection from process environment (heuristic)
  3. Default: 'local'

Usage:
    from tools.utils.ide_context import is_claude_ide, uses_external_review, get_caller_ide

    if uses_external_review():
        # Call Gemini / external AI for review
    else:
        # Caller IS the AI — use local supervisor only
"""
import os
import sys

# ── Known IDE keys ──────────────────────────────────────────────────────────
KNOWN_IDES = {
    "claude":    "Claude Code / Antigravity",
    "cursor":    "Cursor",
    "vscode":    "VS Code + Copilot / GitHub Copilot",
    "windsurf":  "Windsurf (Codeium)",
    "jetbrains": "JetBrains AI Assistant",
    "local":     "Local CLI / No IDE",
}

# IDEs that have their own capable AI — Gemini review step is redundant
_SELF_SUFFICIENT_IDES = {"claude", "cursor", "windsurf"}


def get_caller_ide() -> str:
    """
    Returns the lowercase IDE key for the caller.

    Priority:
    1. settings.KENBUN_CALLER_IDE (loaded from .env by pydantic-settings — most reliable)
    2. KENBUN_CALLER_IDE raw os.environ (explicit shell export)
    3. Auto-detection heuristics from process environment
    4. Default: 'local'
    """
    # 1. Read from pydantic settings (handles .env file discovery correctly)
    try:
        from tools.infrastructure.config import settings as _settings
        settings_val = getattr(_settings, "KENBUN_CALLER_IDE", "").strip().lower()
        if settings_val in KNOWN_IDES:
            return settings_val
    except Exception:
        pass  # Fall through to os.environ

    # 2. Raw env override (in case shell-exported directly)
    explicit = os.environ.get("KENBUN_CALLER_IDE", "").strip().lower()
    if explicit in KNOWN_IDES:
        return explicit

    # 3. Heuristic auto-detection
    #    Claude Code / Antigravity injects ANTHROPIC_API_KEY into the MCP
    #    subprocess environment. Cursor injects CURSOR_SESSION.
    if os.environ.get("CURSOR_SESSION"):
        return "cursor"

    if os.environ.get("WINDSURF_SESSION") or os.environ.get("CODEIUM_SESSION"):
        return "windsurf"

    # Anthropic key present without any of the above = likely Claude Code
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude"

    return "local"


def get_caller_ide_label() -> str:
    """Human-readable IDE name for logging."""
    key = get_caller_ide()
    return KNOWN_IDES.get(key, f"Unknown ({key})")


def is_claude_ide() -> bool:
    """True when Kenbun is being called from Claude Code / Antigravity."""
    return get_caller_ide() == "claude"


def uses_external_review() -> bool:
    """
    True when the calling IDE does NOT have its own capable AI model,
    meaning Kenbun should call an external review service (e.g. Gemini).

    False when the IDE already IS the AI (Claude, Cursor, Windsurf) —
    calling Gemini would be redundant, slower, and waste budget.
    """
    return get_caller_ide() not in _SELF_SUFFICIENT_IDES


def log_ide_context() -> str:
    """Returns a formatted string for orchestrate pipeline headers."""
    key  = get_caller_ide()
    label = get_caller_ide_label()
    explicit = bool(os.environ.get("KENBUN_CALLER_IDE", "").strip())
    source = "env var" if explicit else "auto-detected"
    external = uses_external_review()
    review_mode = "Gemini external review" if external else "IDE-native intelligence (no Gemini)"
    return (
        f"🖥️  Caller IDE : {label} ({key}) [{source}]\n"
        f"🔮  Review mode: {review_mode}"
    )
