"""DSH-07 -- LLM Gateway CapabilityResolver (tools.utils.llm_router).

Tests:
  - Happy path routing to primary provider
  - Demotion and failover to fallback when primary fails / raises
  - Demotion to gemini when both primary and fallback fail
  - Raising RuntimeError on ResolverExhausted when all fail
  - Direct execution bypassing resolver when url_override is provided
  - Snapshot capability for Observatory Resilience panel
"""
import pytest

from tools.strategy.resolver import Resolver
from tools.utils import llm_router
from tools.utils.llm_router import (
    _LLM_GATEWAY_CAP,
    call_llm_gateway,
    llm_gateway_resolver,
)


@pytest.fixture(autouse=True)
def _reset_gateway_resolver():
    _LLM_GATEWAY_CAP.reset()
    yield
    _LLM_GATEWAY_CAP.reset()


def _resolver(*providers):
    r = Resolver(cooldown_s=100)
    for name, fn in providers:
        r.add(name, fn)
    return r


# --------------------------------------------------------------- happy path
def test_primary_serves_when_healthy(monkeypatch):
    monkeypatch.setattr(llm_router, "_primary_provider", lambda sp, um, t, mt: "primary response")
    monkeypatch.setattr(
        llm_router, "_fallback_provider", lambda sp, um, t, mt: pytest.fail("fallback reached unexpectedly")
    )

    out = call_llm_gateway("sys", "user")
    assert out == "primary response"


def test_url_override_bypasses_resolver(monkeypatch):
    called = {}

    def fake_try_endpoint(url, model, sp, um, t, mt, label):
        called.update(url=url, model=model, label=label)
        return "override response"

    monkeypatch.setattr(llm_router, "_try_endpoint", fake_try_endpoint)

    out = call_llm_gateway("sys", "user", url_override="http://custom:1234/v1", model_override="custom-m")
    assert out == "override response"
    assert called == {"url": "http://custom:1234/v1", "model": "custom-m", "label": "Override"}


# --------------------------------------------------------------- failover
def test_primary_failure_falls_through_to_fallback(monkeypatch):
    def dead_primary(sp, um, t, mt):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(llm_router, "_primary_provider", dead_primary)
    monkeypatch.setattr(llm_router, "_fallback_provider", lambda sp, um, t, mt: "fallback response")

    out = call_llm_gateway("sys", "user")
    assert out == "fallback response"

    # Resolver should show primary is demoted
    r = llm_gateway_resolver()
    assert not r.is_healthy("primary")
    assert r.is_healthy("fallback")


def test_empty_content_triggers_failover(monkeypatch):
    # Provider returning empty content should be treated as unavailable (text_unavailable)
    monkeypatch.setattr(llm_router, "_primary_provider", lambda sp, um, t, mt: "   ")
    monkeypatch.setattr(llm_router, "_fallback_provider", lambda sp, um, t, mt: "fallback rescued")

    out = call_llm_gateway("sys", "user")
    assert out == "fallback rescued"


def test_falls_through_to_gemini_when_primary_and_fallback_fail(monkeypatch):
    monkeypatch.setattr(llm_router, "_primary_provider", lambda sp, um, t, mt: (_ for _ in ()).throw(RuntimeError("primary 500")))
    monkeypatch.setattr(llm_router, "_fallback_provider", lambda sp, um, t, mt: (_ for _ in ()).throw(RuntimeError("fallback 429")))
    monkeypatch.setattr(llm_router, "_gemini_provider", lambda sp, um, t, mt: "gemini rescued")

    out = call_llm_gateway("sys", "user")
    assert out == "gemini rescued"


def test_all_endpoints_failing_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(llm_router, "_primary_provider", lambda sp, um, t, mt: (_ for _ in ()).throw(RuntimeError("err1")))
    monkeypatch.setattr(llm_router, "_fallback_provider", lambda sp, um, t, mt: (_ for _ in ()).throw(RuntimeError("err2")))
    monkeypatch.setattr(llm_router, "_gemini_provider", lambda sp, um, t, mt: (_ for _ in ()).throw(RuntimeError("err3")))

    with pytest.raises(RuntimeError) as exc_info:
        call_llm_gateway("sys", "user")
    assert "LLM_ROUTER CRITICAL: All endpoints failed" in str(exc_info.value)


# --------------------------------------------------------------- observatory snapshot
def test_llm_gateway_resolver_snapshot():
    r = llm_gateway_resolver()
    snap = r.snapshot()
    names = [p["name"] for p in snap]
    assert "primary" in names
    assert "fallback" in names
    assert "gemini" in names
