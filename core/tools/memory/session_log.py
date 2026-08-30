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

Wiring the assertion into the live LLM call path is a later slice.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional

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
