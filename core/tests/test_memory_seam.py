"""Tests for DSH-10 Unified Memory Capability Seam."""
import math
import time
import pytest
from tools.strategy.memory_seam import (
    MemoryEmbedding,
    MemoryRecord,
    MemoryQueryResult,
    SqliteMemoryProvider,
    BaseMemoryProvider,
    UnifiedMemorySeam,
)


def test_memory_embedding_ieee754_validation():
    # Valid embedding
    emb = MemoryEmbedding.create([0.1, 0.2, 0.3])
    assert emb.dimension == 3
    assert emb.vector == (0.1, 0.2, 0.3)

    # Empty vector
    with pytest.raises(ValueError, match="cannot be empty"):
        MemoryEmbedding.create([])

    # NaN component
    with pytest.raises(ValueError, match="not a finite number"):
        MemoryEmbedding.create([0.1, float("nan"), 0.3])

    # Inf component
    with pytest.raises(ValueError, match="not a finite number"):
        MemoryEmbedding.create([0.1, float("inf"), 0.3])


def test_memory_record_and_result_immutability():
    emb = MemoryEmbedding.create([0.5, 0.5])
    record = MemoryRecord(
        id="rec_1",
        content="Testing Kenbun memory",
        source="test",
        metadata={"category": "audit"},
        timestamp=time.time(),
        embedding=emb,
        score=0.95,
    )
    assert record.id == "rec_1"
    assert record.embedding.dimension == 2

    # Verify immutability
    with pytest.raises(AttributeError):
        record.content = "New content"

    result = MemoryQueryResult(
        matches=(record,),
        query="Kenbun",
        total_count=1,
        provider_used="sqlite_local",
        latency_ms=1.5,
        fallback_occurred=False,
    )
    assert len(result.matches) == 1
    with pytest.raises(AttributeError):
        result.total_count = 2


def test_sqlite_memory_provider_lifecycle(tmp_path):
    db_file = tmp_path / "test_memory.db"
    provider = SqliteMemoryProvider(db_path=str(db_file))
    assert provider.is_healthy() is True

    record = MemoryRecord(
        id="mem_101",
        content="PostgreSQL failover to local SQLite fallback on Local Mac",
        source="sqlite",
        metadata={"service": "bayesian"},
        timestamp=time.time(),
        embedding=MemoryEmbedding.create([0.12, 0.34]),
    )

    # Store
    assert provider.store(record) is True

    # Search match
    results = provider.search("PostgreSQL failover", limit=5)
    assert len(results) >= 1
    assert results[0].id == "mem_101"
    assert "PostgreSQL" in results[0].content
    assert results[0].embedding.dimension == 2

    # Search non-match
    no_results = provider.search("quantum computer physics", limit=5)
    assert len(no_results) == 0

    # Delete
    assert provider.delete("mem_101") is True
    assert len(provider.search("PostgreSQL", limit=5)) == 0


class MockFailingProvider(BaseMemoryProvider):
    def __init__(self):
        super().__init__(name="mock_failing", priority=100)

    def is_healthy(self) -> bool:
        return False

    def store(self, record: MemoryRecord) -> bool:
        return False

    def search(self, query: str, limit: int = 5, min_score: float = 0.0):
        return ()

    def delete(self, record_id: str) -> bool:
        return False


def test_unified_seam_automatic_fallback(tmp_path):
    db_file = tmp_path / "fallback.db"
    sqlite_provider = SqliteMemoryProvider(db_path=str(db_file), priority=10)
    failing_primary = MockFailingProvider()

    seam = UnifiedMemorySeam(providers=[failing_primary, sqlite_provider])
    seam.fallback_provider = sqlite_provider

    record = MemoryRecord(
        id="rec_fallback",
        content="Resilient state machine execution under network partition",
        source="unified",
        metadata={"priority": "high"},
        timestamp=time.time(),
    )

    # Storing routes to sqlite because failing_primary is not healthy
    stored = seam.store(record)
    assert stored is True

    # Search automatically falls back to SQLite
    res = seam.search("Resilient state machine", limit=5)
    assert res.total_count == 1
    assert res.matches[0].id == "rec_fallback"
    assert res.fallback_occurred is True
    assert res.provider_used == "sqlite_local"
