"""
ide_context.py — AI IDE & Platform Context Detection for Kenbun Orchestrate

Detects which AI IDE / Platform is calling Kenbun so the orchestrate pipeline can
dynamically skip redundant external AI calls (e.g. Gemini) when the
calling platform is already a self-sufficient AI (e.g. Antigravity 2.0 / Claude).

Priority order:
  1. KENBUN_CALLER_IDE raw os.environ (explicit process override — highest precedence)
  2. Auto-detection from process environment heuristics (ANTIGRAVITY_APP, CURSOR_SESSION, etc.)
  3. settings.KENBUN_CALLER_IDE (loaded from .env file by pydantic-settings)
  4. Default: 'local'

Usage:
    from tools.utils.ide_context import is_antigravity_ide, is_claude_ide, get_ide_capabilities

    if is_antigravity_ide():
        # Partner Kenbun tools with Antigravity 2.0 primitives (/goal, /grill-me, /browser, /schedule)
"""
import os
import sys
from typing import Any, Dict

# ── Known IDE & Platform keys ──────────────────────────────────────────────
KNOWN_IDES = {
    "antigravity": "Google Antigravity 2.0 / IDE",
    "claude":      "Claude Desktop / Claude Code",
    "cursor":      "Cursor",
    "vscode":      "VS Code + Copilot / GitHub Copilot",
    "windsurf":    "Windsurf (Codeium)",
    "jetbrains":   "JetBrains AI Assistant",
    "local":       "Local CLI / No IDE",
}

# Platforms with native frontier AI models — external Gemini review step is redundant
_SELF_SUFFICIENT_IDES = {"antigravity", "claude", "cursor", "windsurf"}

# Platform-specific Slash Commands & Primitives
PLATFORM_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "antigravity": {
        "platform_name": "Google Antigravity 2.0",
        "slash_commands": ["/goal", "/grill-me", "/schedule", "/browser"],
        "shortcuts": {
            "conversation_picker": "⌘K / Ctrl+K",
            "file_search": "⌘P / Ctrl+P",
            "focus_input": "⌘L / Ctrl+L",
            "new_conversation": "⌘N / Ctrl+N",
            "prev_next_chat": "⌥ Up/Down / Alt+Up/Down",
        },
        "modes": ["Local Mode", "New Worktree Mode"],
        "auxiliary_surfaces": ["Subagents", "Background Tasks", "Artifacts", "Files Changed", "Terminals"],
        "kenbun_synergy": [
            "consult_supervisor",
            "audit_guardrail",
            "save_to_hivemind",
            "planka_management",
            "autofix_linter",
        ],
    },
    "claude": {
        "platform_name": "Claude Desktop / Claude Code",
        "slash_commands": ["/compact", "/clear", "/bug"],
        "shortcuts": {
            "conversation_picker": "⌘K",
            "focus_input": "⌘L",
        },
        "modes": ["Standard Session"],
        "auxiliary_surfaces": ["Artifacts", "Terminal Output"],
        "kenbun_synergy": [
            "consult_supervisor",
            "audit_guardrail",
            "save_to_hivemind",
            "planka_management",
        ],
    },
    "cursor": {
        "platform_name": "Cursor AI",
        "slash_commands": ["/edit", "/generate"],
        "modes": ["Inline Edit", "Composer"],
        "kenbun_synergy": ["consult_supervisor", "save_to_hivemind"],
    },
    "local": {
        "platform_name": "Local Terminal / CLI",
        "slash_commands": [],
        "modes": ["Direct CLI Execution"],
        "kenbun_synergy": ["orchestrate", "consult_supervisor", "save_to_hivemind"],
    },
}


def get_caller_ide() -> str:
    """
    Returns the lowercase IDE key for the caller.

    Priority:
    1. KENBUN_CALLER_IDE raw os.environ (explicit shell/process export)
    2. Auto-detection heuristics from active process environment (ANTIGRAVITY_APP, CURSOR_SESSION, etc.)
    3. settings.KENBUN_CALLER_IDE (loaded from .env file by pydantic-settings)
    4. Default: 'local'
    """
    # 1. Explicit raw env override
    explicit = os.environ.get("KENBUN_CALLER_IDE", "").strip().lower()
    if explicit in KNOWN_IDES:
        return explicit

    # 2. Heuristic auto-detection from process environment
    if any(
        os.environ.get(env_var)
        for env_var in (
            "ANTIGRAVITY_APP",
            "ANTIGRAVITY_IDE",
            "ANTIGRAVITY_WORKSPACE",
            "GEMINI_CLI",
            "AGY_SESSION",
        )
    ):
        return "antigravity"

    if os.environ.get("CURSOR_SESSION"):
        return "cursor"

    if os.environ.get("WINDSURF_SESSION") or os.environ.get("CODEIUM_SESSION"):
        return "windsurf"

    # 3. Read from settings if explicitly specified in configuration
    try:
        from tools.infrastructure.config import settings as _settings
        settings_val = getattr(_settings, "KENBUN_CALLER_IDE", "").strip().lower()
        if settings_val in KNOWN_IDES:
            return settings_val
    except Exception:
        pass

    # Anthropic API key present without Antigravity/Cursor/Windsurf = likely Claude
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude"

    if "antigravity" in sys.executable.lower() or "gemini" in sys.executable.lower():
        return "antigravity"

    return "local"


def get_caller_ide_label() -> str:
    """Human-readable IDE / platform name for logging."""
    key = get_caller_ide()
    return KNOWN_IDES.get(key, f"Unknown ({key})")


def is_antigravity_ide() -> bool:
    """True when Kenbun is being called from Google Antigravity 2.0 / Antigravity IDE."""
    return get_caller_ide() == "antigravity"


def is_claude_ide() -> bool:
    """True when Kenbun is being called from Claude Desktop / Claude Code."""
    return get_caller_ide() == "claude"


def uses_external_review() -> bool:
    """
    True when the calling IDE does NOT have its own capable AI model,
    meaning Kenbun should call an external review service (e.g. Gemini).
    """
    return get_caller_ide() not in _SELF_SUFFICIENT_IDES


def get_ide_capabilities(ide_key: str = None) -> Dict[str, Any]:
    """
    Returns the capabilities (slash commands, navigation, modes, tool synergy)
    for the active or specified platform.
    """
    target = (ide_key or get_caller_ide()).lower()
    return PLATFORM_CAPABILITIES.get(target, PLATFORM_CAPABILITIES.get("local", {}))


def log_ide_context() -> str:
    """Returns a formatted string for orchestrate pipeline headers."""
    key = get_caller_ide()
    label = get_caller_ide_label()
    explicit = bool(os.environ.get("KENBUN_CALLER_IDE", "").strip())
    source = "env var" if explicit else "auto-detected"
    external = uses_external_review()
    review_mode = "Gemini external review" if external else "Platform-native intelligence"
    
    caps = get_ide_capabilities(key)
    slash_cmds = ", ".join(caps.get("slash_commands", [])) or "None"

    return (
        f"🖥️  Caller Platform : {label} ({key}) [{source}]\n"
        f"🔮  Review Mode     : {review_mode}\n"
        f"⚡  Slash Commands   : {slash_cmds}"
    )
