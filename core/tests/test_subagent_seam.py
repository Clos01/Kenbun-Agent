"""DSH-04 slice 1 -- the subagent capability seam.

One interface (`subagent.run`), the three delegation paths become swappable
providers behind it, swapping is a revertible effect, and a provider that reports
itself unavailable (the Gemini-429 case) is no longer a dead end -- the seam
walks the other providers.
"""
import inspect

import pytest

from tools.execution.subagent import register_subagent_provider, subagent
from tools.execution.subagent.definition import SubagentResult, task_label

_BUILTIN = "in-process-swarm"


class FakeProvider:
    def __init__(self, name: str, *, ok: bool = True, unavailable: bool = False,
                 output: str = "done"):
        self.name = name
        self._ok = ok
        self._unavailable = unavailable
        self._output = output
        self.calls: list[str] = []

    def run(self, task, *, context="", cwd=None, timeout=None) -> SubagentResult:
        self.calls.append(task)
        return SubagentResult(
            task_label=task_label(task), ok=self._ok, output=self._output,
            provider=self.name, error=None if self._ok else "boom",
            meta={"unavailable": self._unavailable},
        )


@pytest.fixture(autouse=True)
def _reset_subagent():
    for n in subagent.providers():
        if n != _BUILTIN:
            subagent._providers.pop(n, None)
    subagent._active = _BUILTIN
    yield
    for n in subagent.providers():
        if n != _BUILTIN:
            subagent._providers.pop(n, None)
    subagent._active = _BUILTIN


# --------------------------------------------------------------- the interface
def test_default_provider_is_the_in_process_swarm():
    assert subagent.active() == _BUILTIN
    assert _BUILTIN in subagent.providers()


def test_seam_run_takes_no_authority_widening_params():
    params = set(inspect.signature(subagent.run).parameters)
    assert params == {"task", "context", "cwd", "timeout", "fallback"}
    assert "env" not in params and "tools" not in params


def test_task_label_redacts_secrets_and_truncates():
    lbl = task_label("deploy with api_key=sk-abcdef123456 and ghp_secrettoken12345", limit=200)
    assert "sk-abcdef123456" not in lbl
    assert "ghp_secrettoken12345" not in lbl
    assert "<redacted>" in lbl
    assert len(task_label("x" * 500)) <= 83


# ------------------------------------------------------------ provider swapping
def test_register_active_then_dispose_restores_builtin():
    fake = FakeProvider("fake")
    dispose = register_subagent_provider(fake, make_active=True)
    assert subagent.active() == "fake"

    res = subagent.run("do a thing")
    assert res.ok and res.provider == "fake"
    assert fake.calls == ["do a thing"]

    dispose()
    assert subagent.active() == _BUILTIN
    assert "fake" not in subagent.providers()


def test_dispose_is_idempotent():
    dispose = register_subagent_provider(FakeProvider("fake"), make_active=True)
    dispose()
    dispose()
    assert subagent.active() == _BUILTIN


def test_use_switches_and_restores():
    register_subagent_provider(FakeProvider("fake"), make_active=False)
    assert subagent.active() == _BUILTIN
    restore = subagent.use("fake")
    assert subagent.active() == "fake"
    restore()
    assert subagent.active() == _BUILTIN


def test_use_unknown_raises():
    with pytest.raises(KeyError):
        subagent.use("nope")


def test_run_rejects_a_non_positive_timeout():
    with pytest.raises(ValueError):
        subagent.run("x", timeout=0)
    with pytest.raises(ValueError):
        subagent.run("x", timeout=-5)


@pytest.mark.parametrize("s", [
    "Authorization: Bearer abcdef123456ghijk",
    "api_key=sk-live-deadbeef99",
    "API-KEY: mysupersecretvalue",
    "password = hunter2hunter2",
])
def test_task_label_redacts_every_secret_shape(s):
    out = task_label(s, limit=300)
    assert "<redacted>" in out
    assert "sk-live" not in out and "hunter2" not in out and "supersecret" not in out


# --------------------------------------------------- the fallback (429) story
def test_unavailable_active_provider_falls_through_to_a_working_one():
    dead = FakeProvider("dead", ok=False, unavailable=True)     # simulates Gemini 429
    alive = FakeProvider("alive", ok=True, output="handled it")
    register_subagent_provider(alive, make_active=False)
    register_subagent_provider(dead, make_active=True)

    res = subagent.run("summarize the repo")

    assert res.ok
    assert res.provider == "alive"
    assert res.output == "handled it"
    assert dead.calls == ["summarize the repo"]        # tried first
    assert alive.calls == ["summarize the repo"]       # then fell through


def test_a_real_failure_does_NOT_fall_through():
    """A provider that ran and genuinely failed (not 'unavailable') must not have
    the same task silently re-run elsewhere -- it may have had side effects."""
    broke = FakeProvider("broke", ok=False, unavailable=False)
    backup = FakeProvider("backup", ok=True)
    register_subagent_provider(backup, make_active=False)
    register_subagent_provider(broke, make_active=True)

    res = subagent.run("apply a migration")

    assert not res.ok
    assert res.provider == "broke"
    assert backup.calls == []                          # never touched


def test_fallback_can_be_disabled():
    dead = FakeProvider("dead", ok=False, unavailable=True)
    alive = FakeProvider("alive", ok=True)
    register_subagent_provider(alive, make_active=False)
    register_subagent_provider(dead, make_active=True)

    res = subagent.run("x", fallback=False)
    assert not res.ok and res.provider == "dead"
    assert alive.calls == []


def test_disposing_active_falls_back_to_builtin_not_insertion_order():
    a = FakeProvider("aaa")
    z = FakeProvider("zzz")
    register_subagent_provider(a, make_active=False)
    dispose_z = register_subagent_provider(z, make_active=True)
    assert subagent.active() == "zzz"
    dispose_z()
    assert subagent.active() == _BUILTIN
