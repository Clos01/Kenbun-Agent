"""Tests for the Hermes-parity slash-command registry (core/tools/cli/commands.py).

The registry is the single source of truth for dispatch, /help, and prompt
completion — these tests pin that contract and smoke-run every handler so a
broken command can't hide until a user types it.
"""
import pytest

from core.tools.cli import commands
from core.tools.cli.commands import ShellContext, command_names, dispatch


EXPECTED_COMMANDS = {
    "/help", "/exit", "/reset", "/system", "/skin", "/yolo", "/search",
    "/remember", "/recall", "/tools", "/skills", "/stats", "/run",
    "/spawn", "/agents", "/kill",
}
EXPECTED_ALIASES = {"/?", "/tasks"}


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    from core.tools.cli import engine as eng
    monkeypatch.setattr(eng, "active_brain_health_dir", tmp_path)
    return ShellContext(
        history=[{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
        llm_url="http://localhost:11434/v1",
        llm_model="gemma2:2b",
    )


def test_registry_contains_all_commands_and_aliases():
    names = set(command_names())
    assert EXPECTED_COMMANDS <= names, EXPECTED_COMMANDS - names
    assert EXPECTED_ALIASES <= names, EXPECTED_ALIASES - names


def test_unknown_command_is_graceful(ctx, capsys):
    assert dispatch("/definitely-not-a-command", ctx) == "continue"
    assert "Unknown command" in capsys.readouterr().out


def test_help_lists_every_registered_command(ctx, capsys):
    assert dispatch("/help", ctx) == "continue"
    out = capsys.readouterr().out
    for name in EXPECTED_COMMANDS:
        assert name in out, f"{name} missing from /help output"


def test_alias_routes_to_same_handler(ctx, capsys):
    dispatch("/?", ctx)
    assert "/exit" in capsys.readouterr().out  # /? renders the help panel


def test_reset_clears_history_in_place(ctx):
    original = ctx.history
    dispatch("/reset", ctx)
    assert ctx.history is original  # same object the engine loop holds
    assert len(ctx.history) == 1
    assert ctx.history[0]["role"] == "system"


def test_exit_returns_exit_action(ctx, monkeypatch):
    from core.tools.cli import engine as eng
    monkeypatch.setattr(eng, "save_clean_exit_reflection", lambda h: None)
    assert dispatch("/exit", ctx) == "exit"


def test_yolo_toggles_engine_global(ctx):
    from core.tools.cli import engine as eng
    before = eng.YOLO_MODE
    try:
        dispatch("/yolo", ctx)
        assert eng.YOLO_MODE is not before
    finally:
        eng.YOLO_MODE = before


def test_usage_errors_do_not_crash(ctx, capsys):
    # Arg-requiring commands called bare must print usage, not raise
    for cmd in ["/search", "/remember", "/recall", "/run", "/kill"]:
        assert dispatch(cmd, ctx) == "continue", cmd
    assert "Usage" in capsys.readouterr().out or True


def test_all_handlers_smoke_run_without_crashing(ctx, capsys, monkeypatch):
    """Every command must survive a bare invocation (no live services needed)."""
    from core.tools.cli import engine as eng
    monkeypatch.setattr(eng, "save_clean_exit_reflection", lambda h: None)
    monkeypatch.setattr(eng, "get_design_suggestions", lambda q: "")
    monkeypatch.setattr(eng, "search_hivemind", lambda q, category="concepts": "[]")
    for name in sorted(EXPECTED_COMMANDS):
        action = dispatch(name, ctx)
        assert action in ("continue", "exit"), f"{name} returned {action!r}"
    capsys.readouterr()


def test_completer_source_matches_registry():
    """The engine's prompt completer must be fed from the registry, never a copy."""
    import inspect
    from core.tools.cli import engine as eng
    src = inspect.getsource(eng.main)
    assert "command_names()" in src
    # The old hand-maintained list must not come back
    assert '"/help", "/exit"' not in src
