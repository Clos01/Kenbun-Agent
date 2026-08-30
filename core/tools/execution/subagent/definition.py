"""The subagent capability -- Service Definition (DSH-04).

Kenbun has three ways to hand work to a child today, none behind a shared
interface: `claude_code_agent.dispatch` (external Claude Code CLI),
`delegate_task` -> `spawn_swarm` (in-process Queen+workers, the one that 429s on
Gemini), and `orchestrate` pipelines. This is the **Definition** -- one shape for
"run this task somewhere and tell me what happened". Providers wrap each of the
existing paths; consumers call `subagent.run(...)`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

_SECRET_RE = re.compile(
    r"sk-[A-Za-z0-9]{8,}"
    r"|ghp_[A-Za-z0-9]{8,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|bearer\s+[A-Za-z0-9._\-]{12,}"
    r"|(?:api[_-]?key|token|secret|password)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SubagentResult:
    """Outcome of one delegated task, identical in shape whichever provider ran it."""

    task_label: str          # a redacted, truncated label -- safe to log/persist
    ok: bool
    output: str
    provider: str = ""
    duration_seconds: float = 0.0
    error: Optional[str] = None
    meta: dict = field(default_factory=dict)


def task_label(task: str, limit: int = 80) -> str:
    """A log-safe handle for a task string: obvious secrets redacted, truncated.

    Task text is free-form and routinely pasted with tokens/paths in it. The raw
    task still goes to the provider; only this label is safe for an audit line."""
    redacted = _SECRET_RE.sub("<redacted>", task or "")
    redacted = " ".join(redacted.split())
    return redacted[:limit] + ("..." if len(redacted) > limit else "")


@runtime_checkable
class SubagentProvider(Protocol):
    """Runs a task in a child agent/process and returns a `SubagentResult`.

    A provider decides *how* the child runs (external Claude Code, in-process
    swarm, Codex, a headless `kenbun` CLI). It receives only the task and a
    context string -- no tool handles, no env dict, no callables -- so switching
    providers can never widen a child's authority beyond what that provider
    itself grants.

    Provider contract for the free-form inputs:
      * `task` / `context` are untrusted free text. A provider that puts them in
        a shell command, SQL, or an eval-like context MUST escape/parameterise
        them; the seam does not (it cannot know the provider's execution model).
      * `cwd`, when given, must be an existing directory the provider may run in.
        A provider must not shell-interpolate it -- pass it to `subprocess`'s
        `cwd=` / a `Path`, never into a command string.
    """

    name: str

    def run(
        self,
        task: str,
        *,
        context: str = "",
        cwd: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> SubagentResult:
        ...
