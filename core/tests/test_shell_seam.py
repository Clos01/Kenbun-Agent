"""DSH-02 slice 1 -- the shell capability seam.

One interface (`shell.run`), swappable providers behind it, and swapping is a
revertible effect: register a provider / switch the active one, get a disposer,
call it, and the previous state is restored. Consumers never change.
"""
import pytest

from tools.execution.shell import register_shell_provider, shell
from tools.execution.shell.definition import (
    EXIT_BLOCKED,
    EXIT_TIMEOUT,
    ShellResult,
    redact_command,
)


class FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def run(self, command, *, cwd=None, timeout=30.0) -> ShellResult:
        self.calls.append(command)
        return ShellResult(command=command, exit_code=0, stdout="FAKE", stderr="",
                           provider=self.name)


@pytest.fixture(autouse=True)
def _reset_shell():
    """Every test starts with only the built-in local provider, active."""
    for name in shell.providers():
        if name != "local":
            shell._providers.pop(name, None)
    shell._active = "local"
    yield
    for name in shell.providers():
        if name != "local":
            shell._providers.pop(name, None)
    shell._active = "local"


# ---------------------------------------------------------------- the interface
def test_default_provider_runs_a_real_command():
    res = shell.run("echo hello-seam")
    assert res.ok
    assert res.exit_code == 0
    assert "hello-seam" in res.stdout
    assert res.provider == "local"


def test_allowlist_still_applies_through_the_seam():
    res = shell.run("rm -rf /tmp/whatever")          # rm is not on the allowlist
    assert res.blocked
    assert res.exit_code == EXIT_BLOCKED
    assert not res.ok


def test_metacharacters_are_blocked_through_the_seam():
    res = shell.run("echo a && echo b")
    assert res.blocked and not res.ok


def test_denied_subcommand_is_blocked_through_the_seam():
    res = shell.run("git push origin main")
    assert res.blocked and not res.ok


def test_timeout_is_reported_structurally():
    res = shell.run("python3 -c \"__import__('time').sleep(3)\"", timeout=0.4)
    assert res.timed_out
    assert res.exit_code == EXIT_TIMEOUT
    assert not res.ok


# ------------------------------------------------------------ provider swapping
def test_register_provider_active_then_dispose_restores_local():
    fake = FakeProvider()
    dispose = register_shell_provider(fake, make_active=True)

    assert shell.active() == "fake"
    assert shell.run("echo x").stdout == "FAKE"
    assert fake.calls == ["echo x"]

    dispose()

    assert shell.active() == "local"
    assert "x" in shell.run("echo x").stdout          # real echo again
    assert "fake" not in shell.providers()


def test_dispose_is_idempotent():
    dispose = register_shell_provider(FakeProvider(), make_active=True)
    dispose()
    dispose()                                          # must not raise
    assert shell.active() == "local"


def test_use_switches_an_already_registered_provider_and_restores():
    fake = FakeProvider()
    register_shell_provider(fake, make_active=False)   # registered but not active
    assert shell.active() == "local"

    restore = shell.use("fake")
    assert shell.active() == "fake"
    assert shell.run("echo y").stdout == "FAKE"

    restore()
    assert shell.active() == "local"


def test_use_unknown_provider_raises():
    with pytest.raises(KeyError):
        shell.use("nope")


def test_seam_run_has_no_env_parameter():
    """The env injection surface is deliberately closed at the seam (DSH-02 review)."""
    import inspect
    assert "env" not in inspect.signature(shell.run).parameters


def test_registering_without_make_active_keeps_local_serving():
    fake = FakeProvider()
    register_shell_provider(fake, make_active=False)
    assert shell.active() == "local"
    assert "z" in shell.run("echo z").stdout
    assert sorted(shell.providers()) == ["fake", "local"]


def test_disposing_a_non_active_provider_does_not_touch_the_active_one():
    fake = FakeProvider()
    dispose = register_shell_provider(fake, make_active=False)
    dispose()
    assert shell.active() == "local"
    assert "fake" not in shell.providers()


def test_disposing_the_active_provider_falls_back_deterministically_to_local():
    a = FakeProvider(); a.name = "aaa"
    b = FakeProvider(); b.name = "zzz"
    register_shell_provider(a, make_active=False)
    dispose_b = register_shell_provider(b, make_active=True)
    assert shell.active() == "zzz"
    dispose_b()
    # not "aaa" (insertion-order first) -- the built-in local is preferred
    assert shell.active() == "local"


def test_redact_command_keeps_only_the_binary():
    assert redact_command("curl -H 'Authorization: Bearer sk-secret'") == "curl [+2 arg(s) redacted]"
    assert redact_command("ls") == "ls"
    assert redact_command("/usr/bin/git status") == "git [+1 arg(s) redacted]"
    assert redact_command("") == "<empty>"


@pytest.mark.parametrize("cmd", [
    "GITHUB_TOKEN=ghp_secret git clone x",     # POSIX env-assignment prefix
    "AWS_SECRET_ACCESS_KEY=abc/def aws s3 ls",
    "'weird binary' --flag",
    "curl$(cat /etc/passwd)",
])
def test_redact_command_never_leaks_a_value_bearing_first_token(cmd):
    out = redact_command(cmd)
    assert "secret" not in out.lower()
    assert "ghp_" not in out
    assert "=" not in out
    assert out.startswith("<redacted command,")


# --------------------------------------------------- DSH-02 s2: real caller migrated
def test_execute_cli_command_routes_through_the_shell_seam(monkeypatch):
    """server_deps.execute_cli_command dispatches via shell.run, so swapping the
    active provider swaps what that tool executes -- with no code change."""
    from tools.execution.shell import shell
    from tools.infrastructure import server_deps

    seen = {}

    class Spy:
        name = "spy"

        def run(self, command, *, cwd=None, timeout=30.0):
            seen["command"] = command
            return ShellResult(command=command, exit_code=0, stdout="spied-ok",
                               stderr="", provider=self.name)

    dispose = shell.register_provider(Spy(), make_active=True)
    monkeypatch.setattr("scripts.terminal_chat.scrub_secrets", lambda s: s, raising=False)
    try:
        out = server_deps.execute_cli_command("git status --porcelain")
        assert seen["command"] == "git status --porcelain"
        assert "spied-ok" in out
    finally:
        dispose()


def test_execute_cli_command_maps_blocked_and_timeout(monkeypatch):
    from tools.execution.shell import shell
    from tools.execution.shell.definition import EXIT_BLOCKED, EXIT_TIMEOUT
    from tools.infrastructure import server_deps

    class Rejector:
        name = "rej"

        def __init__(self, kind):
            self.kind = kind

        def run(self, command, *, cwd=None, timeout=30.0):
            if self.kind == "blocked":
                return ShellResult(command=command, exit_code=EXIT_BLOCKED, stdout="",
                                   stderr="binary 'x' not allowed", blocked=True, provider=self.name)
            return ShellResult(command=command, exit_code=EXIT_TIMEOUT, stdout="",
                               stderr="", timed_out=True, provider=self.name)

    monkeypatch.setattr("scripts.terminal_chat.scrub_secrets", lambda s: s, raising=False)
    for kind, needle in (("blocked", "Security Violation"), ("timeout", "timed out")):
        dispose = shell.register_provider(Rejector(kind), make_active=True)
        try:
            assert needle in server_deps.execute_cli_command("x --y")
        finally:
            dispose()
