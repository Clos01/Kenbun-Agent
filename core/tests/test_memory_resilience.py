"""Tests for Chroma and Honcho resilience, local fallback persistence, and collection resolution."""
import pytest
from pathlib import Path


def test_chroma_persistent_client_fallback(tmp_path, monkeypatch):
    """When HTTP host is unreachable, get_chroma_client falls back to local PersistentClient."""
    from tools.memory import honcho_connect
    from tools.infrastructure.config import settings

    monkeypatch.setattr(settings, "CHROMA_HOST", "192.0.2.1")  # Test-net unroutable IP
    monkeypatch.setattr(settings, "CHROMA_PORT", 8000)
    monkeypatch.setattr(honcho_connect, "_CHROMA_CLIENT", None)
    monkeypatch.setattr(honcho_connect, "_CHROMA_HTTP_COOLDOWN_UNTIL", 0.0)
    monkeypatch.setenv("KENBUN_CHROMA_LOCAL_PATH", str(tmp_path / "chroma_test"))

    client = honcho_connect.get_chroma_client()
    assert client is not None
    assert client.heartbeat() > 0


def test_collection_resolution_aliasing(tmp_path, monkeypatch):
    """Collection resolution automatically maps bare names to populated legacy aliases."""
    from tools.memory import honcho_connect
    import chromadb

    db_path = str(tmp_path / "chroma_alias_test")
    client = chromadb.PersistentClient(path=db_path)
    # Populate a legacy aliased collection
    col_qjl = client.create_collection("kenbun-agent.concepts_qjl")
    col_qjl.add(ids=["c1"], documents=["Legacy concept content"], metadatas=[{"title": "Legacy"}])

    resolved = honcho_connect._resolve_collection(client, "concepts")
    assert resolved is not None
    assert resolved.name == "kenbun-agent.concepts_qjl"
    assert resolved.count() == 1


def test_dual_persistence_and_search(tmp_path, monkeypatch):
    """add_memory dual-writes to local SQLite and Chroma, and search_messages finds it."""
    from tools.memory import honcho_connect

    monkeypatch.setattr(honcho_connect, "_get_local_db_path", lambda: tmp_path / "honcho_test.db")
    monkeypatch.setenv("KENBUN_CHROMA_LOCAL_PATH", str(tmp_path / "chroma_dual_test"))
    monkeypatch.setattr(honcho_connect, "_CHROMA_CLIENT", None)
    monkeypatch.setattr(honcho_connect, "get_honcho_client", lambda: None)  # Simulate offline daemon

    honcho_connect.add_memory("Architectural rule: Zero downtime failover", category="concepts")

    # Verify search finds the memory via local SQLite fallback
    hits = honcho_connect.search_messages("downtime", category="concepts")
    assert len(hits) >= 1
    assert "Zero downtime failover" in hits[0]

    # Verify semantic retrieve_memory finds the memory
    retrieved = honcho_connect.retrieve_memory("downtime failover", category="concepts")
    assert len(retrieved) >= 1
    assert any("Zero downtime failover" in r for r in retrieved)


def test_honcho_readiness(tmp_path, monkeypatch):
    """is_honcho_ready returns True when local SQLite DB is accessible."""
    from tools.memory import honcho_connect

    monkeypatch.setattr(honcho_connect, "_get_local_db_path", lambda: tmp_path / "honcho_ready_test.db")
    monkeypatch.setattr(honcho_connect, "get_honcho_client", lambda: None)

    assert honcho_connect.is_honcho_ready() is True
