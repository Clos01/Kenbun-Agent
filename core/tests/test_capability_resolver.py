"""DSH-06 -- the shared CapabilityResolver machinery (extracted from
decomposition.py / senior_reviewer.py)."""
import logging
import threading

import pytest

from tools.strategy.capability_resolver import (
    CapabilityResolver,
    ResolverExhausted,
    _env_float,
    text_unavailable,
)

_LOG = logging.getLogger("test")


# ------------------------------------------------------------- text_unavailable
@pytest.mark.parametrize("val,unavailable", [
    ("a real answer", False),
    ("[]", False),
    ("", True),
    ("   ", True),
    (None, True),
    (123, True),
    ("❌ endpoint down", True),
    ("⚠️ rate limited", True),
    ("Error: nope", True),
    ("boom RESOURCE_EXHAUSTED boom", True),
    ("you hit the rate limit exceeded ceiling", True),
])
def test_text_unavailable(val, unavailable):
    assert text_unavailable(val) is unavailable


# ------------------------------------------------------------- _env_float
@pytest.mark.parametrize("env,expected", [
    (None, 300.0), ("45", 45.0), ("  90.5 ", 90.5),
    ("not-a-number", 300.0), ("0", 300.0), ("-10", 300.0),
])
def test_env_float(monkeypatch, env, expected):
    if env is None:
        monkeypatch.delenv("X_COOLDOWN", raising=False)
    else:
        monkeypatch.setenv("X_COOLDOWN", env)
    assert _env_float("X_COOLDOWN", 300.0, _LOG) == expected


# ------------------------------------------------------------- construction
def _cap(order=None, **kw):
    fns = {"a": lambda: "A", "b": lambda: "B", "c": lambda: "C"}
    return CapabilityResolver("testcap", fns, providers_env="X_PROVIDERS",
                              cooldown_env="X_COOLDOWN", default_order=order, **kw)


def test_default_order_is_insertion_order():
    assert _cap().resolver().names() == ["a", "b", "c"]
    assert _cap().primary == "a"


def test_explicit_default_order_is_a_subset():
    c = _cap(order=("c", "a"))
    assert c.resolver().names() == ["c", "a"]
    assert c.primary == "c"


def test_bad_default_order_name_raises():
    with pytest.raises(ValueError):
        _cap(order=("a", "nope"))


def test_empty_provider_map_raises():
    with pytest.raises(ValueError):
        CapabilityResolver("x", {}, providers_env="P", cooldown_env="C")


# ------------------------------------------------------------- env allowlist
def test_providers_env_narrows_and_reorders(monkeypatch):
    monkeypatch.setenv("X_PROVIDERS", "c , a")
    assert _cap().resolver().names() == ["c", "a"]


def test_providers_env_junk_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("X_PROVIDERS", "zzz, qqq")
    assert _cap().resolver().names() == ["a", "b", "c"]


def test_cooldown_env_feeds_the_resolver(monkeypatch):
    monkeypatch.setenv("X_COOLDOWN", "17")
    assert _cap().resolver()._cooldown_s == 17.0


# ------------------------------------------------------------- lazy singleton
def test_resolver_is_lazily_built_once():
    c = _cap()
    assert c.resolver() is c.resolver()


def test_reset_forces_a_rebuild():
    c = _cap()
    first = c.resolver()
    c.reset()
    assert c.resolver() is not first


def test_concurrent_first_touch_shares_one_instance():
    c = _cap()
    seen, barrier = [], threading.Barrier(12)

    def grab():
        barrier.wait()
        seen.append(c.resolver())

    ts = [threading.Thread(target=grab) for _ in range(12)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(seen) == 12 and all(r is seen[0] for r in seen)


# ------------------------------------------------------------- run + telemetry
def test_run_returns_primary_when_healthy():
    name, out = _cap().run(lambda p: p())
    assert (name, out) == ("a", "A")


def test_run_falls_through_and_records_a_failover(tmp_path, monkeypatch):
    from tools.infrastructure.config import settings
    from tools.strategy import resolver_events
    monkeypatch.setattr(settings, "BRAIN_HEALTH_DIR", tmp_path)

    fns = {
        "a": lambda: (_ for _ in ()).throw(RuntimeError("down")),
        "b": lambda: "B-served",
    }
    c = CapabilityResolver("failcap", fns, providers_env="P", cooldown_env="C")
    name, out = c.run(lambda p: p())
    assert (name, out) == ("b", "B-served")

    ev = resolver_events.recent(5)
    assert len(ev) == 1
    assert ev[0]["kind"] == "failover"
    assert ev[0]["capability"] == "failcap"
    assert ev[0]["provider"] == "b"


def test_run_records_exhausted_and_reraises(tmp_path, monkeypatch):
    from tools.infrastructure.config import settings
    from tools.strategy import resolver_events
    monkeypatch.setattr(settings, "BRAIN_HEALTH_DIR", tmp_path)

    fns = {"a": lambda: (_ for _ in ()).throw(RuntimeError("x")),
           "b": lambda: (_ for _ in ()).throw(RuntimeError("y"))}
    c = CapabilityResolver("deadcap", fns, providers_env="P", cooldown_env="C")
    with pytest.raises(ResolverExhausted):
        c.run(lambda p: p())
    assert [e["kind"] for e in resolver_events.recent(5)] == ["exhausted"]


def test_run_honours_is_unavailable():
    fns = {"a": lambda: "not usable", "b": lambda: "usable!"}
    c = CapabilityResolver("uc", fns, providers_env="P", cooldown_env="C")
    name, out = c.run(lambda p: p(), is_unavailable=lambda r: r == "not usable")
    assert (name, out) == ("b", "usable!")


def test_telemetry_failure_never_breaks_run(monkeypatch):
    """A broken resolver_events.record must not stop a live call."""
    import tools.strategy.resolver_events as re_mod
    monkeypatch.setattr(re_mod, "record",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk full")))
    fns = {"a": lambda: (_ for _ in ()).throw(RuntimeError("down")), "b": lambda: "ok"}
    c = CapabilityResolver("robust", fns, providers_env="P", cooldown_env="C")
    assert c.run(lambda p: p()) == ("b", "ok")
