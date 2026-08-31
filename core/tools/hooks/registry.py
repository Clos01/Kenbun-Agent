"""DSH-05 (hooks half) -- load a ``hooks.json`` and fire command hooks at a point.

``hooks.json`` shape (both DSH dialects; Claude Code's is a superset):

    {
      "PreToolUse":  [ { "matcher": "bash|shell", "hooks": [ { "type": "command",
                          "command": "python3 check.py", "timeout": 30 } ] } ],
      "Stop":        [ { "hooks": [ { "type": "command", "command": "notify.sh" } ] } ]
    }

Only ``type == "command"`` hooks run. ``http`` / ``mcp_tool`` / ``prompt`` /
``agent`` handlers are parsed-and-skipped with a warning (the DSH contract).

``fire(point, query, payload)`` runs every matching hook and folds the outcomes:
a ``block`` / ``deny`` stops the action with the first reason; ``continue: false``
sets ``stop_requested``; ``additionalContext`` / ``systemMessage`` are collected;
``updatedInput`` from the last hook that set one wins. Every invocation emits a
``hook/invoked`` + ``hook/result`` pair on the ``kenbun.hooks`` logger, paired by
a short ``handlerId`` (the DSH "every run is traceable" tie-in). Payloads are
never logged -- only the point, matcher, decision, exit code and duration.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.hooks.protocol import (
    CommandHook,
    HookOutput,
    MatcherGroup,
    matcher_diagnostic,
    matches_matcher,
    run_hook,
)

logger = logging.getLogger("kenbun.hooks")

_SKIPPED_TYPES = ("http", "mcp_tool", "prompt", "agent")


@dataclass
class FiredResult:
    """The folded outcome of firing all hooks at one point."""
    blocked: bool = False
    reason: Optional[str] = None
    stop_requested: bool = False
    stop_reason: Optional[str] = None
    added_context: List[str] = field(default_factory=list)
    system_messages: List[str] = field(default_factory=list)
    updated_input: Optional[Dict[str, Any]] = None
    ran: int = 0

    @property
    def context_blob(self) -> str:
        return "\n\n".join(self.added_context)


class HookRegistry:
    """Points -> matcher groups, loaded from a ``hooks.json``. Immutable after
    ``load``; build a new one to reconfigure."""

    def __init__(self, points: Optional[Dict[str, List[MatcherGroup]]] = None,
                 *, mode: str = "claude-code") -> None:
        self._points: Dict[str, List[MatcherGroup]] = points or {}
        self._mode = mode

    # ---------------------------------------------------------------- loading
    @classmethod
    def load(cls, path: str | Path, *, mode: str = "claude-code") -> "HookRegistry":
        p = Path(path).expanduser()
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls({}, mode=mode)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("hooks: could not read %s (%s) -- no hooks will run", p, type(e).__name__)
            return cls({}, mode=mode)
        if not isinstance(raw, dict):
            logger.warning("hooks: %s is not a JSON object -- no hooks will run", p)
            return cls({}, mode=mode)

        points: Dict[str, List[MatcherGroup]] = {}
        for point, groups in raw.items():
            if not isinstance(groups, list):
                continue
            parsed_groups: List[MatcherGroup] = []
            for g in groups:
                if not isinstance(g, dict):
                    continue
                matcher = g.get("matcher")
                if not (matcher is None or isinstance(matcher, str)):
                    matcher = None
                diag = matcher_diagnostic(matcher, mode)
                if diag:
                    logger.warning("hooks: %s at %s -- group skipped", diag, point)
                    continue
                cmds: List[CommandHook] = []
                for h in g.get("hooks", []) or []:
                    if not isinstance(h, dict):
                        continue
                    htype = h.get("type", "command")
                    if htype in _SKIPPED_TYPES:
                        logger.warning("hooks: skipping %r handler at %s (only 'command' runs)", htype, point)
                        continue
                    cmd = h.get("command")
                    if not isinstance(cmd, str) or not cmd.strip():
                        continue
                    to = h.get("timeout")
                    cmds.append(CommandHook(command=cmd, timeout_s=float(to) if isinstance(to, (int, float)) else None))
                if cmds:
                    parsed_groups.append(MatcherGroup(hooks=cmds, matcher=matcher))
            if parsed_groups:
                points[str(point)] = parsed_groups
        return cls(points, mode=mode)

    # ---------------------------------------------------------------- query
    def points(self) -> List[str]:
        return sorted(self._points)

    def has_hooks(self, point: str) -> bool:
        return bool(self._points.get(point))

    # ---------------------------------------------------------------- fire
    def fire(
        self,
        point: str,
        query: str,
        payload: Dict[str, Any],
        *,
        cwd: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> FiredResult:
        """Run every hook whose matcher selects ``query`` at ``point``. ``query``
        is what the matcher sees (a tool name, a prompt, ...); ``payload`` is the
        JSON handed to each hook on stdin. A hook that returns block/deny
        short-circuits the remaining hooks. Never raises."""
        result = FiredResult()
        groups = self._points.get(point)
        if not groups:
            return result
        sid = session_id or "-"

        for group in groups:
            if not matches_matcher(group.matcher, query, self._mode):
                continue
            for hook in group.hooks:
                handler_id = uuid.uuid4().hex[:12]
                logger.info("hook/invoked point=%s handler=%s session=%s matcher=%r",
                            point, handler_id, sid, group.matcher)
                started = time.monotonic()
                out = run_hook(hook, dict(payload), cwd=cwd, expected_event=point)
                dur_ms = round((time.monotonic() - started) * 1000, 1)
                result.ran += 1
                self._fold(result, out)
                decision = out.decision or ("stop" if out.stop_requested else "pass")
                log = logger.warning if (out.blocks or out.exit_code not in (0, 2, None)) else logger.info
                log("hook/result point=%s handler=%s session=%s decision=%s exit=%s dur_ms=%s",
                    point, handler_id, sid, decision, out.exit_code, dur_ms)
                if out.blocks:
                    return result   # a block short-circuits the rest
        return result

    @staticmethod
    def _fold(result: FiredResult, out: HookOutput) -> None:
        if out.blocks and not result.blocked:
            result.blocked = True
            result.reason = out.reason or "blocked by hook"
        if out.stop_requested:
            result.stop_requested = True
            result.stop_reason = result.stop_reason or out.stop_reason
        if out.additional_context:
            result.added_context.append(out.additional_context)
        if out.system_message:
            result.system_messages.append(out.system_message)
        if out.updated_input is not None:
            result.updated_input = out.updated_input


_DEFAULT: Optional[HookRegistry] = None


def default_registry() -> HookRegistry:
    """The process-wide registry, loaded once from ``KENBUN_HOOKS_FILE`` or
    ``~/.claude/hooks.json`` (Claude Code's own config file)."""
    global _DEFAULT
    if _DEFAULT is None:
        import os
        path = os.getenv("KENBUN_HOOKS_FILE") or str(Path.home() / ".claude" / "hooks.json")
        _DEFAULT = HookRegistry.load(path)
        if _DEFAULT.points():
            logger.info("hooks: loaded points %s from %s", _DEFAULT.points(), path)
    return _DEFAULT
