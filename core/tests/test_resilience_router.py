"""DSH-06 -- the /api/v1/resilience endpoint powering the Observatory panel."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tools.infrastructure.routers.resilience import router
from tools.strategy import decomposition


@pytest.fixture
def client(tmp_path, monkeypatch):
    from tools.infrastructure.config import settings
    monkeypatch.setattr(settings, "BRAIN_HEALTH_DIR", tmp_path)
    decomposition._RESOLVER = None            # fresh, all-healthy
    app = FastAPI()
    app.include_router(router)
    try:
        yield TestClient(app)
    finally:
        decomposition._RESOLVER = None


def test_endpoint_shape(client):
    r = client.get("/api/v1/resilience")
    assert r.status_code == 200
    body = r.json()
    for key in ("capability", "providers", "events", "phases", "primer", "spof",
                "healthy_count", "total_count"):
        assert key in body


def test_reports_the_configured_providers_all_healthy_by_default(client):
    body = client.get("/api/v1/resilience").json()
    names = [p["name"] for p in body["providers"]]
    assert names == ["gemini", "deepseek", "local"]
    assert body["providers"][0]["primary"] is True
    assert body["healthy_count"] == body["total_count"] == 3
    assert body["spof"] is False


def test_a_recorded_failover_shows_up_in_events(client, tmp_path):
    from tools.strategy.resolver_events import record
    record("failover", capability="queen_decomposition", provider="deepseek",
           detail="gemini unavailable", providers_order=["gemini", "deepseek", "local"])
    body = client.get("/api/v1/resilience").json()
    assert len(body["events"]) == 1
    assert body["events"][0]["provider"] == "deepseek"


def test_phases_cover_dsh_01_through_06(client):
    ids = [p["id"] for p in client.get("/api/v1/resilience").json()["phases"]]
    assert ids == ["DSH-01", "DSH-02", "DSH-03", "DSH-04", "DSH-05", "DSH-06"]
