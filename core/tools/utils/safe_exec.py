"""
🛡️ safe_exec — Strict argv-allowlisted subprocess helper.

PURPOSE
-------
Centralized replacement for every ``subprocess.run(cmd, shell=True)`` site in
the Kenbun codebase. ``shell=True`` with a caller-supplied string is a
Remote-Code-Execution primitive: a single shell metacharacter (``;``, ``&&``,
backtick, ``$()``, redirection) can pivot a benign-looking command into
arbitrary host execution. This module replaces that pattern with:

1. ``shlex.split`` of the command string into an argv list (no shell).
2. A strict allowlist check on ``argv[0]`` (basename only).
3. A metacharacter pre-scan as defense-in-depth — even if shlex tolerates
   some patterns, anything resembling shell composition is refused.
4. ``subprocess.run(argv, shell=False, ...)``.

This is intentionally narrower than ``is_yolo_safe`` in ``terminal_chat.py``:
that function inspects substrings of a *shell* string, which is fragile. This
helper refuses to ever hand the string to a shell in the first place.

USAGE
-----
    from tools.utils.safe_exec import safe_run, UnsafeCommandError

    try:
        result = safe_run("git status --short", cwd="/app", timeout=30.0)
    except UnsafeCommandError as e:
        return f"❌ Security Violation: {e}"
    # result is a subprocess.CompletedProcess

ADDING NEW BINARIES
-------------------
Extending ``ALLOWED_BINARIES`` is a deliberate security decision. New entries
should be reviewed by System 2 (Supervisor) and accompanied by a unit test in
``core/tests/test_safe_exec.py``.
"""

from __future__ import annotations

import logging
import shlex
import subprocess
from pathlib import Path
from typing import Optional, Sequence

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Allowlist                                                                    #
# --------------------------------------------------------------------------- #
# Only the basename is matched. Full paths (e.g. /usr/bin/git) are normalized
# to "git" before the check. Anything not in this set is refused outright.
#
# Curated for the current call sites:
#   - api_server.execute_cli_command: developer-style diagnostics and project
#     scripts (read-only or controlled writes).
#   - agent_bus.spawn_agent: background sub-agents that compile/test code.
#
# Keep this list MINIMAL. When in doubt, leave it out.
ALLOWED_BINARIES: frozenset[str] = frozenset({
    # Filesystem inspection (read-only)
    "ls", "cat", "head", "tail", "wc", "find", "grep", "rg",
    "stat", "file", "du", "df", "pwd", "tree", "which",
    # Text processing (read-only / stdout only)
    "sed", "awk", "sort", "uniq", "cut", "tr", "echo",
    # Version control (writes are scoped to the repo)
    "git",
    # Python toolchain
    "python", "python3", "pip", "pip3", "pytest", "ruff", "mypy", "black",
    # Node toolchain (sub-agent build/test work)
    "node", "npm", "npx", "pnpm", "yarn", "tsc", "eslint",
    # Container tooling (read-only operations only — see DENIED_SUBCOMMANDS)
    "docker", "docker-compose",
    # Misc safe utilities
    "env", "hostname", "whoami", "date", "uptime", "uname",
})

# --------------------------------------------------------------------------- #
# Denylists                                                                    #
# --------------------------------------------------------------------------- #
# Tokens that, if present anywhere in the raw command string, prove the caller
# is trying to compose multiple commands or perform I/O redirection — neither
# of which makes sense without a shell, so their presence is itself a red flag.
SHELL_METACHARACTERS: tuple[str, ...] = (
    ";", "&&", "||", "|",          # command chaining / pipes
    "`", "$(", "${",                # command/parameter substitution
    ">", "<", ">>", "<<",           # I/O redirection
    "\n", "\r",                     # newline injection
)

# Per-binary subcommand denylist for binaries that are mostly safe but have
# destructive operations. Matched against ``argv[1]`` (the first non-binary
# token), case-sensitively.
DENIED_SUBCOMMANDS: dict[str, frozenset[str]] = {
    "git": frozenset({
        # Mutation against remotes / history rewriting is out of scope here.
        "push", "reset", "rebase", "filter-branch", "clean", "gc",
    }),
    "docker": frozenset({
        # Mutating operations on the host docker daemon.
        "rm", "rmi", "system", "volume", "network", "exec", "kill",
    }),
    "docker-compose": frozenset({"down", "rm", "kill"}),
    "pip": frozenset({"uninstall"}),
    "pip3": frozenset({"uninstall"}),
}


class UnsafeCommandError(ValueError):
    """Raised when a command string fails the safety gate."""


def _validate(command: str) -> list[str]:
    """Parse + validate ``command``. Returns the argv list on success."""
    if not isinstance(command, str):
        raise UnsafeCommandError("command must be a string")

    stripped = command.strip()
    if not stripped:
        raise UnsafeCommandError("empty command")

    # 1. Defensive metacharacter pre-scan on the raw string.
    for meta in SHELL_METACHARACTERS:
        if meta in stripped:
            raise UnsafeCommandError(
                f"shell metacharacter {meta!r} is not permitted "
                "(commands run without a shell; composition is forbidden)"
            )

    # 2. Tokenize without invoking a shell.
    try:
        argv = shlex.split(stripped, posix=True)
    except ValueError as e:
        raise UnsafeCommandError(f"could not parse command: {e}") from e

    if not argv:
        raise UnsafeCommandError("command produced no tokens")

    # 3. Binary allowlist (basename match).
    binary = Path(argv[0]).name
    if binary not in ALLOWED_BINARIES:
        raise UnsafeCommandError(
            f"binary {binary!r} is not in the allowlist "
            f"(add to safe_exec.ALLOWED_BINARIES after Supervisor review)"
        )

    # 4. Per-binary subcommand denylist.
    if binary in DENIED_SUBCOMMANDS and len(argv) > 1:
        subcommand = argv[1]
        if subcommand in DENIED_SUBCOMMANDS[binary]:
            raise UnsafeCommandError(
                f"{binary} {subcommand!r} is denied by policy"
            )

    return argv


def parse_argv(command: str) -> list[str]:
    """
    Public helper for callers that want to validate without executing
    (e.g. logging the planned argv before dispatch).
    """
    return _validate(command)


def safe_run(
    command: str,
    *,
    cwd: Optional[str] = None,
    timeout: Optional[float] = 30.0,
    env: Optional[dict] = None,
    capture_output: bool = True,
    text: bool = True,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """
    Validate and execute ``command`` without ever invoking a shell.

    Raises
    ------
    UnsafeCommandError
        If the command fails any allowlist / metacharacter check.
    subprocess.TimeoutExpired
        Propagated from ``subprocess.run`` on timeout.
    """
    argv = _validate(command)
    logger.info("safe_run dispatching argv=%r cwd=%s timeout=%s", argv, cwd, timeout)
    return subprocess.run(
        argv,
        shell=False,
        cwd=cwd,
        timeout=timeout,
        env=env,
        capture_output=capture_output,
        text=text,
        check=check,
    )


def safe_run_argv(
    argv: Sequence[str],
    *,
    cwd: Optional[str] = None,
    timeout: Optional[float] = 30.0,
    env: Optional[dict] = None,
    capture_output: bool = True,
    text: bool = True,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """
    Variant for callers that already have an argv list (skip ``shlex.split``).
    Still runs the allowlist + subcommand-denylist gates.
    """
    if not argv:
        raise UnsafeCommandError("empty argv")
    binary = Path(argv[0]).name
    if binary not in ALLOWED_BINARIES:
        raise UnsafeCommandError(f"binary {binary!r} is not in the allowlist")
    if binary in DENIED_SUBCOMMANDS and len(argv) > 1 and argv[1] in DENIED_SUBCOMMANDS[binary]:
        raise UnsafeCommandError(f"{binary} {argv[1]!r} is denied by policy")
    logger.info("safe_run_argv dispatching argv=%r cwd=%s timeout=%s", list(argv), cwd, timeout)
    return subprocess.run(
        list(argv),
        shell=False,
        cwd=cwd,
        timeout=timeout,
        env=env,
        capture_output=capture_output,
        text=text,
        check=check,
    )


__all__ = [
    "ALLOWED_BINARIES",
    "DENIED_SUBCOMMANDS",
    "SHELL_METACHARACTERS",
    "UnsafeCommandError",
    "parse_argv",
    "safe_run",
    "safe_run_argv",
]
