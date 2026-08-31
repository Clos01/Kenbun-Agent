"""DSH-05 (hooks half) -- a Python port of DeepSeek-Harness's ``hook-protocol``.

One shared vocabulary for command hooks: what a hook can do and what happens
when it runs. A hook is ``{command, timeout_s?}`` inside a matcher group
``{matcher?, hooks: [...]}`` under a hook point (``PreToolUse``, ``Stop``, ...).

Outcome decode (both DSH dialects, faithfully):
  * exit 2                -> block, stderr is the reason the model sees
  * exit 0 + JSON stdout  -> structured: continue / stopReason / systemMessage,
                             top-level decision (approve|block),
                             hookSpecificOutput.{permissionDecision (allow|deny|
                             ask), additionalContext, updatedInput}
  * any other exit        -> non-blocking failure (logged, the action proceeds)

Matcher: absent / ``''`` / ``'*'`` match all; a pure ``[A-Za-z0-9_|]+`` pattern
is pipe-alternation exact-match (Claude-literal); anything else is an unanchored
regex; an invalid regex never throws -- it just does not match.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("kenbun.hooks")

_BLOCKING_EXIT = 2
_CLAUDE_LITERAL = re.compile(r"^[A-Za-z0-9_|]+$")


# --------------------------------------------------------------------- matcher
def _is_match_all(matcher: Optional[str]) -> bool:
    return matcher is None or matcher == "" or matcher == "*"


def _compile(pattern: str) -> Optional["re.Pattern[str]"]:
    try:
        return re.compile(pattern)
    except re.error:
        return None


def matches_matcher(matcher: Optional[str], query: str, mode: str = "claude-code") -> bool:
    """True if ``matcher`` selects ``query``. ``mode`` is ``claude-code`` (word+
    pipe patterns are literal alternation) or ``codex`` (always regex)."""
    if _is_match_all(matcher):
        return True
    assert matcher is not None
    if mode == "claude-code" and _CLAUDE_LITERAL.match(matcher):
        return query in matcher.split("|")
    rx = _compile(matcher)
    return bool(rx.search(query)) if rx else False


def matcher_diagnostic(matcher: Optional[str], mode: str = "claude-code") -> Optional[str]:
    """``None`` if the matcher is valid, else a stable diagnostic string."""
    if _is_match_all(matcher):
        return None
    assert matcher is not None
    if mode == "claude-code" and _CLAUDE_LITERAL.match(matcher):
        return None
    return None if _compile(matcher) else f"invalid {mode} regex matcher {matcher!r}"


# --------------------------------------------------------------------- config
@dataclass(frozen=True)
class CommandHook:
    command: str
    timeout_s: Optional[float] = None


@dataclass(frozen=True)
class MatcherGroup:
    hooks: List[CommandHook]
    matcher: Optional[str] = None


# --------------------------------------------------------------------- outcome
@dataclass
class HookOutput:
    exit_code: Optional[int]
    stdout: str = ""
    stderr: str = ""
    decision: Optional[str] = None          # approve|block|allow|deny|ask
    reason: Optional[str] = None
    should_continue: Optional[bool] = None  # `continue` in the wire schema
    stop_reason: Optional[str] = None
    system_message: Optional[str] = None
    additional_context: Optional[str] = None
    updated_input: Optional[Dict[str, Any]] = None
    hook_event_name: Optional[str] = None

    @property
    def blocks(self) -> bool:
        return self.decision in ("block", "deny")

    @property
    def stop_requested(self) -> bool:
        return self.should_continue is False


def _s(d: Dict[str, Any], k: str) -> Optional[str]:
    v = d.get(k)
    return v if isinstance(v, str) else None


def _b(d: Dict[str, Any], k: str) -> Optional[bool]:
    v = d.get(k)
    return v if isinstance(v, bool) else None


def _obj(v: Any) -> Optional[Dict[str, Any]]:
    return v if isinstance(v, dict) else None


def parse_hook_output(
    exit_code: Optional[int],
    stdout: str,
    stderr: str,
    expected_event: Optional[str] = None,
) -> HookOutput:
    """Total decode of a hook process's outcome -- malformed JSON stays plain
    stdout, a spawn failure (``exit_code is None``) is a non-blocking error."""
    out = HookOutput(exit_code=exit_code, stdout=(stdout or "").strip(), stderr=(stderr or "").strip())

    if exit_code == _BLOCKING_EXIT:
        out.decision = "block"
        if out.stderr:
            out.reason = out.stderr
        return out

    if exit_code == 0 and out.stdout.startswith("{"):
        try:
            parsed = _obj(json.loads(out.stdout))
        except json.JSONDecodeError:
            parsed = None
        if parsed:
            _apply_structured(out, parsed, expected_event)
    return out


def _apply_structured(out: HookOutput, p: Dict[str, Any], expected_event: Optional[str]) -> None:
    if (c := _b(p, "continue")) is not None:
        out.should_continue = c
    if (sr := _s(p, "stopReason")) is not None:
        out.stop_reason = sr
    if (sm := _s(p, "systemMessage")) is not None:
        out.system_message = sm

    top = _s(p, "decision")
    if top in ("approve", "block"):
        out.decision = top
    if (tr := _s(p, "reason")) is not None:
        out.reason = tr

    hso = _obj(p.get("hookSpecificOutput"))
    if not hso:
        return
    ev = _s(hso, "hookEventName")
    if ev is not None:
        out.hook_event_name = ev
    if expected_event is not None and ev != expected_event:
        return   # a mismatched/absent discriminator can't touch the firing event
    perm = _s(hso, "permissionDecision")
    if perm in ("allow", "deny", "ask"):
        out.decision = perm
    if (pr := _s(hso, "permissionDecisionReason")) is not None:
        out.reason = pr
    if (ac := _s(hso, "additionalContext")) is not None:
        out.additional_context = ac
    if (ui := _obj(hso.get("updatedInput"))) is not None:
        out.updated_input = ui


# --------------------------------------------------------------------- runner
_DEFAULT_TIMEOUT_S = 600.0
_STDERR_CAP = 4000


def run_hook(hook: CommandHook, payload: Dict[str, Any], *,
             cwd: Optional[str] = None, expected_event: Optional[str] = None) -> HookOutput:
    """Run ``hook.command`` as a shell line with the JSON ``payload`` on stdin.

    Hook commands are *operator-configured, trusted* config (like a git hook),
    not model input -- so this is ``shell=True`` deliberately and does NOT use
    the model-command allowlist. Parent-process secrets are scrubbed from the
    child env (``safe_exec.scrubbed_env``). Never raises: a spawn failure or a
    timeout decodes to a non-blocking error outcome (the action proceeds)."""
    import subprocess

    from tools.utils.safe_exec import scrubbed_env

    stdin = json.dumps(payload)
    timeout = hook.timeout_s or _DEFAULT_TIMEOUT_S
    try:
        cp = subprocess.run(
            hook.command, shell=True, input=stdin, text=True,
            capture_output=True, cwd=cwd, timeout=timeout, env=scrubbed_env(),
        )
    except subprocess.TimeoutExpired:
        logger.warning("hook timed out after %.0fs", timeout)
        return parse_hook_output(None, "", f"hook timed out after {timeout:.0f}s", expected_event)
    except Exception as e:  # noqa: BLE001 -- a hook that cannot run must not crash the turn
        logger.warning("hook could not run (%s)", type(e).__name__)
        return parse_hook_output(None, "", f"hook infrastructure error: {type(e).__name__}", expected_event)

    return parse_hook_output(
        cp.returncode, cp.stdout or "", (cp.stderr or "")[:_STDERR_CAP], expected_event,
    )
