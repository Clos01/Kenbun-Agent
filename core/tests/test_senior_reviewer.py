"""DSH-06 slice 3 -- the supervisor's local senior reviewer survives a provider outage.

Promise: kill the LM Studio box and consult_supervisor still gets a verdict --
from DeepSeek, then the default LLM gateway.
"""
import pytest

from tools.strategy import senior_reviewer
from tools.strategy.resolver import Resolver
from tools.strategy.senior_reviewer import ResolverExhausted, run_senior_review

_OK = '{"status": "APPROVED", "critique": "CLEAN"}'


def _resolver(*providers):
    r = Resolver(cooldown_s=100)
    for name, fn in providers:
        r.add(name, fn)
    return r


# --------------------------------------------------------------- happy path
def test_lmstudio_serves_when_healthy():
    r = _resolver(
        ("lmstudio", lambda sp, um, mt: _OK),
        ("deepseek", lambda sp, um, mt: pytest.fail("deepseek should not be reached")),
    )
    name, out = run_senior_review("sys", "code", resolver=r)
    assert name == "lmstudio"
    assert out == _OK


def test_args_pass_through_to_the_provider():
    seen = {}

    def lm(sp, um, mt):
        seen.update(sp=sp, um=um, mt=mt)
        return _OK

    run_senior_review("SYSTEM", "USERMSG", max_tokens=1234, resolver=_resolver(("lmstudio", lm)))
    assert seen == {"sp": "SYSTEM", "um": "USERMSG", "mt": 1234}


# --------------------------------------------------------------- failover
def test_dead_lmstudio_box_falls_through_to_deepseek():
    def lm(sp, um, mt):
        raise ConnectionError("no route to SWARM_PC_IP")

    r = _resolver(("lmstudio", lm), ("deepseek", lambda sp, um, mt: _OK))
    name, out = run_senior_review("sys", "code", resolver=r)
    assert name == "deepseek"
    assert out == _OK
    assert not r.is_healthy("lmstudio")


def test_falls_all_the_way_to_the_gateway():
    r = _resolver(
        ("lmstudio", lambda sp, um, mt: (_ for _ in ()).throw(RuntimeError("down"))),
        ("deepseek", lambda sp, um, mt: (_ for _ in ()).throw(RuntimeError("429"))),
        ("gateway", lambda sp, um, mt: _OK),
    )
    name, out = run_senior_review("sys", "code", resolver=r)
    assert name == "gateway"


def test_every_provider_down_raises_resolver_exhausted():
    r = _resolver(
        ("lmstudio", lambda sp, um, mt: (_ for _ in ()).throw(RuntimeError("a"))),
        ("deepseek", lambda sp, um, mt: (_ for _ in ()).throw(RuntimeError("b"))),
    )
    with pytest.raises(ResolverExhausted):
        run_senior_review("sys", "code", resolver=r)


def test_empty_and_error_prefixed_output_are_treated_as_outages():
    r = _resolver(
        ("lmstudio", lambda sp, um, mt: "   "),
        ("deepseek", lambda sp, um, mt: "❌ endpoint returned empty content"),
        ("gateway", lambda sp, um, mt: _OK),
    )
    name, _ = run_senior_review("sys", "code", resolver=r)
    assert name == "gateway"
    assert not r.is_healthy("lmstudio") and not r.is_healthy("deepseek")


# --------------------------------------------------------------- config knobs
def test_provider_allowlist_env_narrows_and_orders(monkeypatch):
    monkeypatch.setenv("KENBUN_SENIOR_PROVIDERS", "gateway, lmstudio")
    senior_reviewer._CAP.reset()
    try:
        assert senior_reviewer.senior_reviewer_resolver().names() == ["gateway", "lmstudio"]
    finally:
        senior_reviewer._CAP.reset()


def test_deepseek_is_opt_in_not_default(monkeypatch):
    senior_reviewer._CAP.reset()
    monkeypatch.delenv("KENBUN_SENIOR_PROVIDERS", raising=False)
    try:
        assert "deepseek" not in senior_reviewer.senior_reviewer_resolver().names()
    finally:
        senior_reviewer._CAP.reset()
    monkeypatch.setenv("KENBUN_SENIOR_PROVIDERS", "lmstudio,deepseek,gateway")
    senior_reviewer._CAP.reset()
    try:
        assert senior_reviewer.senior_reviewer_resolver().names() == ["lmstudio", "deepseek", "gateway"]
    finally:
        senior_reviewer._CAP.reset()


def test_provider_allowlist_junk_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("KENBUN_SENIOR_PROVIDERS", "nope, nonsense")
    senior_reviewer._CAP.reset()
    try:
        assert senior_reviewer.senior_reviewer_resolver().names() == ["lmstudio", "gateway"]
    finally:
        senior_reviewer._CAP.reset()


def test_cooldown_env_is_honoured(monkeypatch):
    monkeypatch.setenv("KENBUN_SENIOR_COOLDOWN_S", "42")
    senior_reviewer._CAP.reset()
    try:
        assert senior_reviewer.senior_reviewer_resolver()._cooldown_s == 42.0
    finally:
        senior_reviewer._CAP.reset()


def test_module_resolver_is_a_lazy_singleton():
    senior_reviewer._CAP.reset()
    try:
        first = senior_reviewer.senior_reviewer_resolver()
        assert senior_reviewer.senior_reviewer_resolver() is first
        assert first.names() == ["lmstudio", "gateway"]
    finally:
        senior_reviewer._CAP.reset()


# --------------------------------------------------------------- telemetry
def test_failover_records_a_cross_process_event(tmp_path, monkeypatch):
    from tools.infrastructure.config import settings
    from tools.strategy import resolver_events

    monkeypatch.setattr(settings, "BRAIN_HEALTH_DIR", tmp_path)
    r = _resolver(
        ("lmstudio", lambda sp, um, mt: (_ for _ in ()).throw(RuntimeError("box down"))),
        ("deepseek", lambda sp, um, mt: _OK),
    )
    run_senior_review("sys", "code", resolver=r)

    events = resolver_events.recent(10)
    assert len(events) == 1
    assert events[0]["kind"] == "failover"
    assert events[0]["capability"] == "senior_reviewer"
    assert events[0]["provider"] == "deepseek"


# --------------------------------------------- supervisor_agent integration
def test_call_local_senior_returns_content_from_a_fallback(monkeypatch):
    """_call_local_senior keeps its (content, error) contract and serves from a
    fallback (the gateway, by default) when LM Studio is dead."""
    from tools.audit import supervisor_agent

    senior_reviewer._CAP.reset()
    monkeypatch.setattr(senior_reviewer, "_lmstudio_provider",
                        lambda sp, um, mt: (_ for _ in ()).throw(ConnectionError("box down")))
    monkeypatch.setattr(senior_reviewer, "_gateway_provider", lambda sp, um, mt: _OK)
    try:
        content, err = supervisor_agent._call_local_senior("sys", "code")
        assert err is None
        assert content == _OK
    finally:
        senior_reviewer._CAP.reset()


def test_call_local_senior_returns_error_tuple_when_all_providers_down(monkeypatch):
    from tools.audit import supervisor_agent

    senior_reviewer._CAP.reset()
    for name in ("_lmstudio_provider", "_deepseek_provider", "_gateway_provider"):
        monkeypatch.setattr(senior_reviewer, name,
                            lambda sp, um, mt: (_ for _ in ()).throw(RuntimeError("down")))
    try:
        content, err = supervisor_agent._call_local_senior("sys", "code")
        assert content is None
        assert err and err.startswith("❌ Local Senior Fallback failed")
    finally:
        senior_reviewer._CAP.reset()
