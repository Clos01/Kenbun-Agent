"""DSH-05 (hooks half) -- the command-hook wire protocol.

Covers the matcher dialects, the total outcome decoder, the subprocess runner
(stdin delivery, exit-2 blocking, timeout, secret-env scrub) and the registry
(loading a hooks.json, matcher selection, block short-circuit, context folding).

Run with:  pytest core/tests/test_hook_protocol.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_CORE = Path(__file__).resolve().parent.parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from tools.hooks import (  # noqa: E402
    CommandHook,
    HookRegistry,
    matcher_diagnostic,
    matches_matcher,
    parse_hook_output,
    run_hook,
)


# --------------------------------------------------------------------- matcher
@pytest.mark.parametrize("matcher", [None, "", "*"])
def test_match_all_sentinels(matcher):
    assert matches_matcher(matcher, "anything") is True
    assert matcher_diagnostic(matcher) is None


def test_claude_literal_is_exact_not_substring():
    assert matches_matcher("Bash", "Bash") is True
    assert matches_matcher("Bash", "Bashful") is False


def test_claude_literal_pipe_is_alternation():
    assert matches_matcher("Bash|Edit|Write", "Edit") is True
    assert matches_matcher("Bash|Edit|Write", "Read") is False


def test_non_literal_pattern_is_regex_even_in_claude_mode():
    # contains '.' and '*' -> not [A-Za-z0-9_|]+ -> regex, unanchored
    assert matches_matcher("Notebook.*", "NotebookEdit") is True
    assert matches_matcher("^mcp__", "mcp__foo__bar") is True
    assert matches_matcher("^mcp__", "not_mcp__foo") is False


def test_codex_mode_always_regex():
    # 'Bash' is literal in claude-code, plain regex in codex (search, not fullmatch)
    assert matches_matcher("Bash", "Bashful", mode="claude-code") is False
    assert matches_matcher("Bash", "Bashful", mode="codex") is True


def test_invalid_regex_never_raises_just_fails():
    assert matches_matcher("(unclosed", "anything") is False
    assert "invalid" in (matcher_diagnostic("(unclosed") or "")


# ------------------------------------------------------------------ parse: exit 2
def test_exit_2_blocks_with_stderr_reason():
    out = parse_hook_output(2, "", "policy: no network calls")
    assert out.blocks is True
    assert out.decision == "block"
    assert out.reason == "policy: no network calls"


def test_exit_2_without_stderr_still_blocks():
    out = parse_hook_output(2, "", "")
    assert out.blocks is True
    assert out.reason is None


# ----------------------------------------------------- parse: exit 0 structured
def test_top_level_decision_approve():
    out = parse_hook_output(0, json.dumps({"decision": "approve"}), "")
    assert out.decision == "approve"
    assert out.blocks is False


def test_top_level_decision_block_with_reason():
    out = parse_hook_output(0, json.dumps({"decision": "block", "reason": "nope"}), "")
    assert out.blocks is True
    assert out.reason == "nope"


def test_continue_false_requests_stop():
    out = parse_hook_output(0, json.dumps({"continue": False, "stopReason": "budget spent"}), "")
    assert out.stop_requested is True
    assert out.stop_reason == "budget spent"
    assert out.blocks is False


def test_hook_specific_permission_deny_blocks():
    payload = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                      "permissionDecision": "deny",
                                      "permissionDecisionReason": "path escapes repo"}}
    out = parse_hook_output(0, json.dumps(payload), "", expected_event="PreToolUse")
    assert out.blocks is True
    assert out.reason == "path escapes repo"


def test_hook_specific_additional_context_and_updated_input():
    payload = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                      "additionalContext": "repo is in a detached HEAD",
                                      "updatedInput": {"command": "git status"}}}
    out = parse_hook_output(0, json.dumps(payload), "", expected_event="PreToolUse")
    assert out.additional_context == "repo is in a detached HEAD"
    assert out.updated_input == {"command": "git status"}


def test_hook_specific_output_ignored_on_event_mismatch():
    payload = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                      "permissionDecision": "deny"}}
    out = parse_hook_output(0, json.dumps(payload), "", expected_event="PreToolUse")
    assert out.blocks is False


def test_malformed_json_stays_plain_stdout():
    out = parse_hook_output(0, "{not valid json", "")
    assert out.decision is None
    assert out.stdout == "{not valid json"


def test_other_exit_code_is_non_blocking():
    out = parse_hook_output(1, "whatever", "some warning")
    assert out.blocks is False
    assert out.decision is None


def test_spawn_failure_exit_none_is_non_blocking():
    out = parse_hook_output(None, "", "hook infrastructure error: FileNotFoundError")
    assert out.blocks is False
    assert out.exit_code is None


# --------------------------------------------------------------------- run_hook
def test_run_hook_delivers_payload_on_stdin():
    # `cat` echoes stdin to stdout; exit 0 + non-{ stdout stays plain, but we can
    # still read it back off .stdout
    out = run_hook(CommandHook(command="cat"), {"tool": "Bash", "n": 1})
    assert json.loads(out.stdout) == {"tool": "Bash", "n": 1}
    assert out.exit_code == 0


def test_run_hook_exit_2_blocks():
    out = run_hook(CommandHook(command="echo 'refused' >&2; exit 2"), {})
    assert out.blocks is True
    assert "refused" in (out.reason or "")


def test_run_hook_structured_stdout_is_parsed():
    cmd = """python3 -c 'import json,sys; sys.stdin.read(); print(json.dumps({"decision":"approve"}))'"""
    out = run_hook(CommandHook(command=cmd), {"x": 1})
    assert out.decision == "approve"


def test_run_hook_timeout_is_non_blocking_error():
    out = run_hook(CommandHook(command="sleep 5", timeout_s=0.2), {})
    assert out.exit_code is None
    assert out.blocks is False
    assert "timed out" in (out.stderr or "")


def test_run_hook_scrubs_secret_env(monkeypatch):
    monkeypatch.setenv("MY_API_TOKEN", "leaked-value")
    monkeypatch.setenv("PLAIN_SETTING", "kept-value")
    out = run_hook(CommandHook(command='echo "[${MY_API_TOKEN}][${PLAIN_SETTING}]"'), {})
    assert out.stdout == "[][kept-value]"


# -------------------------------------------------------------------- registry
_HOOKS_JSON = {
    "PreToolUse": [
        {"matcher": "Bash|shell",
         "hooks": [{"type": "command", "command": "echo blocked >&2; exit 2"}]},
        {"matcher": "Edit",
         "hooks": [{"type": "command",
                    "command": """python3 -c 'import json,sys;sys.stdin.read();print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"be careful"}}))'"""}]},
    ],
    "PostToolUse": [
        {"matcher": "Bash",
         "hooks": [{"type": "command",
                    "command": """python3 -c 'import json,sys;sys.stdin.read();print(json.dumps({"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"audit verified"}}))'"""}]},
    ],
    "Stop": [
        {"hooks": [
            {"type": "http", "url": "https://example.test/hook"},          # skipped
            {"type": "command", "command": "echo done"},
        ]},
    ],
}


@pytest.fixture()
def registry(tmp_path) -> HookRegistry:
    p = tmp_path / "hooks.json"
    p.write_text(json.dumps(_HOOKS_JSON), encoding="utf-8")
    return HookRegistry.load(p)


def test_load_parses_points_and_skips_non_command(registry):
    assert registry.points() == ["PostToolUse", "PreToolUse", "Stop"]
    # the http handler was dropped, the command one kept
    stop_groups = registry._points["Stop"]
    assert len(stop_groups) == 1
    assert [h.command for h in stop_groups[0].hooks] == ["echo done"]


def test_load_missing_file_is_empty():
    reg = HookRegistry.load("/no/such/hooks.json")
    assert reg.points() == []
    assert reg.fire("PreToolUse", "Bash", {}).ran == 0


def test_fire_matching_matcher_blocks_and_short_circuits(registry):
    res = registry.fire("PreToolUse", "Bash", {"tool_name": "Bash"})
    assert res.blocked is True
    assert "blocked" in (res.reason or "")
    assert res.ran == 1   # stopped before the Edit group


def test_fire_non_matching_matcher_runs_nothing(registry):
    res = registry.fire("PreToolUse", "Write", {})
    assert res.ran == 0
    assert res.blocked is False


def test_fire_folds_additional_context(registry):
    res = registry.fire("PreToolUse", "Edit", {})
    assert res.blocked is False
    assert res.context_blob == "be careful"


def test_fire_post_tool_use_folds_context(registry):
    res = registry.fire("PostToolUse", "Bash", {"exit_code": 0, "tool_response": "ok"})
    assert res.blocked is False
    assert res.context_blob == "audit verified"


def test_fire_unknown_point_is_noop(registry):
    assert registry.fire("NopePoint", "Bash", {}).ran == 0
