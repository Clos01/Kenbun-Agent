"""The shell capability -- Service Definition (DSH-02).

A *seam* has three roles (docs/deepseek-harness-study.md, chunk 7): this module
is the **Definition** -- the provider-neutral interface. `provider_local.py` /
`provider_e2b.py` are **Providers**. Anything that runs a command via
`shell.run(...)` is a **Consumer**.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class ShellResult:
    """Outcome of one shell command, identical in shape whichever provider ran it."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    blocked: bool = False
    provider: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.blocked


# Conventional exit codes the definition assigns when there is no real child exit.
EXIT_BLOCKED = 126   # command rejected by the allowlist before it ran
EXIT_TIMEOUT = 124   # child killed after exceeding the timeout


_SAFE_BINARY = re.compile(r"^[A-Za-z0-9_.\-]+$")


def redact_command(command: str) -> str:
    """A log-safe label for a command.

    Command *arguments* routinely carry secrets/PII (`curl -H 'Authorization:
    Bearer ...'`, `psql 'password=...'`, keys as flags), and the first token is
    not reliably "just the binary" -- the POSIX `NAME=value cmd ...` idiom puts
    an assignment there. `safe_run` scrubs the child *environment*, not the
    command string, so this returns the binary name ONLY when the first token is
    a bare identifier (leaf of a path, no `=`, no shell-unsafe chars); anything
    else is fully redacted. Nothing that can carry a value ever reaches a log.
    """
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    if not parts:
        return "<empty>"
    head = parts[0].rsplit("/", 1)[-1]
    if "=" in parts[0] or not _SAFE_BINARY.match(head):
        return f"<redacted command, {len(parts)} token(s)>"
    extra = len(parts) - 1
    return head if extra == 0 else f"{head} [+{extra} arg(s) redacted]"


@runtime_checkable
class ShellProvider(Protocol):
    """Runs a validated command *somewhere* and returns a `ShellResult`.

    A provider decides *where* (local subprocess, E2B sandbox, remote host). It
    does not decide *whether* a command is allowed -- allowlist enforcement lives
    in the provider's call into `safe_exec`, and every provider must apply it, so
    swapping providers never widens what the model can run.

    Deliberately no `env` parameter. The child always runs under `safe_run`'s
    secret-scrubbed copy of the ambient environment; a caller-supplied env dict
    is an injection surface (LD_PRELOAD, PATH hijack, reintroducing scrubbed
    vars) and the seam is the choke point that must not open it. A future slice
    adds a narrow `env_extra` that is merged onto the scrubbed base with
    dangerous keys denied.
    """

    name: str

    def run(
        self,
        command: str,
        *,
        cwd: Optional[str] = None,
        timeout: Optional[float] = 30.0,
    ) -> ShellResult:
        ...
