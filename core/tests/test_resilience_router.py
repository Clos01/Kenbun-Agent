"""DSH-06 -- the /api/v1/resilience endpoint powering the Observatory panel."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tools.infrastructure.routers.resilience import router
from tools.strategy import decomposition, reasoning, senior_reviewer


@pytest.fixture
def client(tmp_path, monkeypatch):
    from tools.infrastructure.config import settings
    monkeypatch.setattr(settings, "BRAIN_HEALTH_DIR", tmp_path)
    from tools.infrastructure.routers import resilience
    monkeypatch.setattr(resilience, "_chroma_ok", lambda: False)
    monkeypatch.setattr(resilience, "_honcho_ok", lambda: False)
    from tools.utils import llm_router
    llm_router._LLM_GATEWAY_CAP.reset()
    for mod in (decomposition, reasoning):
        mod._CAP.reset()
    senior_reviewer._CAP.reset()
    senior_reviewer._AUDIT_CAP.reset()
    app = FastAPI()
    app.include_router(router)
    try:
        yield TestClient(app)
    finally:
        for mod in (decomposition, reasoning):
            mod._CAP.reset()
        senior_reviewer._CAP.reset()
        senior_reviewer._AUDIT_CAP.reset()
        llm_router._LLM_GATEWAY_CAP.reset()


def test_endpoint_shape(client):
    r = client.get("/api/v1/resilience")
    assert r.status_code == 200
    body = r.json()
    for key in ("capabilities", "providers", "events", "phases", "primer", "spof",
                "healthy_count", "total_count"):
        assert key in body


def test_every_wired_capability_is_reported(client):
    caps = {c["name"]: c for c in client.get("/api/v1/resilience").json()["capabilities"]}
    assert set(caps) == {
        "Queen decomposition", "Supervisor senior reviewer",
        "Two-pass cloud audit", "Reasoning (misc callers)", "Memory read",
        "LLM gateway",
    }
    assert [p["name"] for p in caps["Queen decomposition"]["providers"]] == ["gemini", "deepseek", "local"]
    assert [p["name"] for p in caps["Supervisor senior reviewer"]["providers"]] == ["lmstudio", "gateway"]
    assert [p["name"] for p in caps["LLM gateway"]["providers"]] == ["primary", "fallback", "gemini"]
    assert [p["name"] for p in caps["Memory read"]["providers"]] == ["chroma", "honcho"]
    for name, c in caps.items():
        if name == "Memory read":
            continue  # infra-dependent in the test env
        assert c["spof"] is False
        assert c["healthy_count"] == c["total_count"] >= 2


def test_a_memory_degradation_is_recorded_and_surfaced(client, tmp_path):
    from tools.strategy.resolver_events import record
    record("degraded", capability="memory", provider="honcho", detail="connection refused")
    body = client.get("/api/v1/resilience").json()
    ev = body["events"][0]
    assert ev["kind"] == "degraded"
    assert ev["capability"] == "memory"
    assert ev["provider"] == "honcho"


def test_backcompat_top_level_fields_track_the_first_capability(client):
    body = client.get("/api/v1/resilience").json()
    assert [p["name"] for p in body["providers"]] == ["gemini", "deepseek", "local"]
    assert body["providers"][0]["primary"] is True
    assert body["healthy_count"] == body["total_count"] == 3
    # top-level spof is the aggregate "is any capability a SPOF right now"; the
    # first (decomposition) capability itself is not
    assert body["capabilities"][0]["spof"] is False


def test_a_recorded_failover_shows_up_in_events(client, tmp_path):
    from tools.strategy.resolver_events import record
    record("failover", capability="senior_reviewer", provider="gateway",
           detail="lmstudio unavailable", providers_order=["lmstudio", "gateway"])
    body = client.get("/api/v1/resilience").json()
    assert len(body["events"]) == 1
    assert body["events"][0]["provider"] == "gateway"


def test_phases_cover_dsh_01_through_07(client):
    ids = [p["id"] for p in client.get("/api/v1/resilience").json()["phases"]]
    assert ids == ["DSH-01", "DSH-02", "DSH-03", "DSH-04", "DSH-05", "DSH-06", "DSH-07"]
