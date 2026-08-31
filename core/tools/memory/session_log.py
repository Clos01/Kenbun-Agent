"""DSH-03 slice 1 -- the session event log as the single source of model context.

DeepSeek Harness holds one invariant here: **model-visible <=> logged**. Anything
the model is shown in a request must be reconstructable from an append-only event
log, and a runtime check asserts it (docs/deepseek-harness-study.md, [DSH-03]).

Kenbun today has two parallel stores -- `sessions_db` (SQLite) and
`chat_history_manager` (JSON file) -- and nothing ties either to what actually
reached the model. This slice adds, as standalone tested pieces:

  * `SessionEvent`                     -- one normalized append-only fact
  * `derive_model_messages(events)`    -- projects the event stream into the
                                          `[{role, content}, ...]` an LLM expects
  * `assert_model_visible_is_logged`   -- raises if a sent message is not in the log
  * `SessionLog`                       -- reads events off the existing sessions_db
                                          message table (no third store)

Slice 2 wires this into the live dashboard-chat LLM call. The *fix* is at the
write site -- ``chat.py`` now ``SessionLog.append``s the system prompt and the
composite user message as events before dispatching -- so the invariant holds by
construction. ``guard_model_dispatch`` is a pure **observe** check right before
the model call: if something is still missing (an upstream bug), it records a
``session_log_gap`` telemetry event and moves on. ``KENBUN_MODEL_LOG=strict``
makes it raise ``UnloggedModelInput`` (kind + session only, never content) --
for tests / CI.
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

logger = logging.getLogger("kenbun.session_log")

# Serialises the check-then-append in ``ensure_system_prompt_logged`` so two
# concurrent same-session chat turns in one process can't both append the
# system prompt. (Cross-process is a non-issue: one uvicorn worker owns chat.)
_ensure_lock = threading.Lock()

# Every event kind whose content can end up inside a model request. If a kind is
# not here, the projector drops it and the invariant ignores it.
MODEL_VISIBLE_KINDS = frozenset({
    "system_prompt",
    "user_message",
    "assistant_message",
    "tool_result",
    "context_injection",
})

_ROLE_BY_KIND = {
    "system_prompt": "system",
    "user_message": "user",
    "assistant_message": "assistant",
    "tool_result": "tool",
    "context_injection": "user",
}

_KIND_BY_ROLE = {
    "system": "system_prompt",
    "user": "user_message",
    "assistant": "assistant_message",
    "tool": "tool_result",
}


class UnloggedModelInput(AssertionError):
    """A message was sent to the model that no logged event accounts for."""


@dataclass(frozen=True)
class SessionEvent:
    """One append-only fact about a session. Never mutated after it is recorded."""

    seq: int
    kind: str
    role: str
    content: str
    tool_name: Optional[str] = None
    ts: str = ""
    meta: dict = field(default_factory=dict)

    def as_model_message(self) -> Optional[dict]:
        """The `{role, content}` this event contributes to a model request, or
        None if the event is not model-visible."""
        if self.kind not in MODEL_VISIBLE_KINDS:
            return None
        role = _ROLE_BY_KIND.get(self.kind, self.role or "user")
        msg = {"role": role, "content": self.content}
        if self.kind == "tool_result" and self.tool_name:
            msg["name"] = self.tool_name
        return msg


def derive_model_messages(events: Iterable[SessionEvent]) -> List[dict]:
    """Project the event stream, in `seq` order, into the model-message list.

    This is the ONLY sanctioned way to build model history: anything else risks
    showing the model something the log does not record."""
    ordered = sorted(events, key=lambda e: e.seq)
    out: List[dict] = []
    for ev in ordered:
        msg = ev.as_model_message()
        if msg is not None:
            out.append(msg)
    return out


def _norm(text: object) -> str:
    return (text if isinstance(text, str) else str(text or "")).strip()


def assert_model_visible_is_logged(
    sent_messages: Iterable[dict], events: Iterable[SessionEvent]
) -> None:
    """Raise `UnloggedModelInput` if any message in `sent_messages` (the exact
    list about to be handed to the LLM) is not accounted for by a logged event.

    Whitespace-insensitive on content; matches on (role, content) and, for tool
    messages, the tool name. Duplicate identical messages are allowed as long as
    the log has at least that many matching events."""
    from collections import Counter

    logged = Counter(
        (m["role"], _norm(m.get("content")), m.get("name"))
        for m in derive_model_messages(events)
    )
    for m in sent_messages:
        key = (m.get("role"), _norm(m.get("content")), m.get("name"))
        if logged[key] <= 0:
            raise UnloggedModelInput(
                f"message {key[0]!r} was sent to the model but no session event "
                f"records it: {key[1][:120]!r}"
            )
        logged[key] -= 1


def _strict() -> bool:
    return os.getenv("KENBUN_MODEL_LOG", "").strip().lower() == "strict"


def ensure_system_prompt_logged(session_id: str, system_prompt: str) -> None:
    """DSH-03 s2 write-site fix: append ``system_prompt`` as a ``system_prompt``
    event iff an identical one is not already in this session's log. The raw
    user directive is already logged by the caller; the composite 'history +
    directive' message the model sees is a *rendering* of events already in the
    log, so only the system prompt is genuinely unlogged. Dedup by content keeps
    the log from growing one system-prompt event per turn."""
    if not system_prompt or not system_prompt.strip():
        return
    want = _norm(system_prompt)
    try:
        with _ensure_lock:
            log = SessionLog(session_id)
            if any(_norm(e.content) == want
                   for e in log.events() if e.kind == "system_prompt"):
                return
            log.append("system_prompt", system_prompt)
    except Exception as e:  # noqa: BLE001 -- best-effort; the guard will notice a gap
        logger.debug("DSH-03: could not log system prompt for %s (%s)", session_id, type(e).__name__)


def guard_model_dispatch(
    session_id: str,
    system_prompt: str,
    *,
    strict: Optional[bool] = None,
) -> bool:
    """DSH-03 s2 -- observe-only check right before a model request. Returns
    ``True`` if ``system_prompt`` is covered by a logged event for
    ``session_id``. On a gap: records a ``session_log_gap`` telemetry event and
    returns ``False`` -- or, with ``strict`` / ``KENBUN_MODEL_LOG=strict``,
    raises :class:`UnloggedModelInput` carrying only the session id, never
    content. Never appends, never raises in the default mode."""
    if not system_prompt or not system_prompt.strip():
        return True
    enforce = _strict() if strict is None else strict
    try:
        logged = {_norm(e.content) for e in SessionLog(session_id).events() if _norm(e.content)}
    except Exception as e:  # noqa: BLE001 -- a read for a telemetry check must not break a chat turn
        logger.debug("guard_model_dispatch: session %s unreadable (%s)", session_id, type(e).__name__)
        return True   # can't check -> don't cry wolf, and never block the turn

    if _norm(system_prompt) in logged:
        return True

    if enforce:
        raise UnloggedModelInput(
            f"session {session_id}: the system prompt reached the model but was not "
            f"logged as an event"
        )
    logger.warning("DSH-03: session %s dispatched an unlogged system prompt to the model", session_id)
    _record_gap()
    return False


def _record_gap() -> None:
    # No session id / content in the trail -- it is read back through /resilience.
    try:
        from tools.strategy.resolver_events import record
        record("session_log_gap", capability="session_log", provider=None,
               detail="a system prompt reached the model without a logged event")
    except Exception:  # noqa: BLE001 -- telemetry is best-effort
        pass


class SessionLog:
    """Append-only view of one session, backed by the existing `sessions_db`
    message table. Reads project rows to `SessionEvent`; `append` records a new
    one. No second store is introduced by this slice."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    def events(self) -> List[SessionEvent]:
        from tools.utils.sessions_db import get_messages

        events: List[SessionEvent] = []
        for row in get_messages(self.session_id):
            role = row.get("role") or "user"
            kind = _KIND_BY_ROLE.get(role, "context_injection")
            events.append(SessionEvent(
                seq=int(row.get("id") or len(events)),
                kind=kind,
                role=role,
                content=row.get("content") or "",
                tool_name=row.get("tool_name"),
                ts=row.get("timestamp") or "",
            ))
        return events

    def append(
        self, kind: str, content: str, *, tool_name: Optional[str] = None
    ) -> None:
        from tools.utils.sessions_db import add_message

        role = _ROLE_BY_KIND.get(kind, "user")
        add_message(self.session_id, role, content, tool_name=tool_name)

    def model_messages(self) -> List[dict]:
        return derive_model_messages(self.events())
