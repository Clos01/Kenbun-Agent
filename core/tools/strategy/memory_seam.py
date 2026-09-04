"""DSH-10 -- Unified Memory Capability Seam (Definition/Provider/Consumer).

Abstracts SQLite, ChromaDB, and Honcho behind a unified MemoryProvider seam,
replacing fragmented conditional logic with spatiotemporal composability.

Structures all query results, memory embeddings, and stored records as immutable
record types (NamedTuple) with strict IEEE-754 validation and health-aware
automatic fallback.
"""
from __future__ import annotations

import json
import logging
import math
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Tuple, Union

from tools.infrastructure.config import settings
from tools.strategy.context_engine import CapabilityDefinition, CapabilityProvider

logger = logging.getLogger("kenbun.memory_seam")


# ── IMMUTABLE RECORD TYPES ──────────────────────────────────────────────────

class MemoryEmbedding(NamedTuple):
    """Immutable record for a vector embedding with strict IEEE-754 validation."""
    vector: Tuple[float, ...]
    dimension: int
    model: str = "text-embedding-3-small"

    @classmethod
    def create(
        cls,
        vector: Sequence[float],
        model: str = "text-embedding-3-small",
    ) -> MemoryEmbedding:
        if not vector:
            raise ValueError("Embedding vector cannot be empty.")
        validated: List[float] = []
        for i, val in enumerate(vector):
            f_val = float(val)
            if not math.isfinite(f_val):
                raise ValueError(f"Vector component at index {i} is not a finite number: {val}")
            validated.append(f_val)
        return cls(vector=tuple(validated), dimension=len(validated), model=model)


class MemoryRecord(NamedTuple):
    """Immutable record representing a unit of memory across any store."""
    id: str
    content: str
    source: str  # "sqlite", "chroma", "honcho"
    metadata: Dict[str, Any]
    timestamp: float
    embedding: Optional[MemoryEmbedding] = None
    score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source,
            "metadata": dict(self.metadata),
            "timestamp": self.timestamp,
            "score": round(self.score, 4) if self.score is not None else None,
            "has_embedding": self.embedding is not None,
            "embedding_dim": self.embedding.dimension if self.embedding else None,
        }


class MemoryQueryResult(NamedTuple):
    """Immutable query result envelope returned by the unified memory seam."""
    matches: Tuple[MemoryRecord, ...]
    query: str
    total_count: int
    provider_used: str
    latency_ms: float
    fallback_occurred: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "total_count": self.total_count,
            "provider_used": self.provider_used,
            "latency_ms": round(self.latency_ms, 2),
            "fallback_occurred": self.fallback_occurred,
            "error": self.error,
            "matches": [m.to_dict() for m in self.matches],
        }


# ── SERVICE PROTOCOL & BASE PROVIDER ────────────────────────────────────────

class MemoryProviderProtocol(ABC):
    """Protocol contract for memory store implementations."""

    @abstractmethod
    def store(self, record: MemoryRecord) -> bool:
        """Stores or upserts a memory record. Returns True on success."""
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> Tuple[MemoryRecord, ...]:
        """Searches memory records matching query string or keywords."""
        pass

    @abstractmethod
    def delete(self, record_id: str) -> bool:
        """Deletes a record by ID. Returns True if deleted."""
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """Returns True if the underlying storage engine is reachable."""
        pass


class BaseMemoryProvider(CapabilityProvider[MemoryProviderProtocol], MemoryProviderProtocol, ABC):
    """Base class for all Memory Capability Providers."""

    def __init__(self, name: str, priority: int = 100):
        super().__init__(name=name, capability_name="unified_memory", priority=priority)

    def get_instance(self) -> MemoryProviderProtocol:
        return self


# ── CONCRETE PROVIDERS ──────────────────────────────────────────────────────

class SqliteMemoryProvider(BaseMemoryProvider):
    """Local SQLite memory provider (always available fallback, priority=10)."""

    def __init__(self, db_path: Optional[str] = None, priority: int = 10):
        super().__init__(name="sqlite_local", priority=priority)
        self.db_path = db_path or settings.INTELLIGENCE_DB_PATH
        self._lock = threading.Lock()
        self._init_table()

    def _init_table(self) -> None:
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS unified_memory_records (
                        id TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        source TEXT NOT NULL,
                        metadata TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        embedding_dim INTEGER,
                        embedding_json TEXT
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_unified_mem_ts ON unified_memory_records(timestamp);")
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize SQLite memory table: {e}")

    def is_healthy(self) -> bool:
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1;")
                return True
        except Exception:
            return False

    def store(self, record: MemoryRecord) -> bool:
        try:
            meta_json = json.dumps(record.metadata)
            emb_json = json.dumps(record.embedding.vector) if record.embedding else None
            emb_dim = record.embedding.dimension if record.embedding else None

            with self._lock, sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO unified_memory_records (
                        id, content, source, metadata, timestamp, embedding_dim, embedding_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        content = excluded.content,
                        source = excluded.source,
                        metadata = excluded.metadata,
                        timestamp = excluded.timestamp,
                        embedding_dim = excluded.embedding_dim,
                        embedding_json = excluded.embedding_json;
                """, (record.id, record.content, record.source, meta_json, record.timestamp, emb_dim, emb_json))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"SqliteMemoryProvider.store error: {e}")
            return False

    def search(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> Tuple[MemoryRecord, ...]:
        q = (query or "").strip().lower()
        if not q:
            return ()

        matches: List[MemoryRecord] = []
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                # Substring matching with LIKE
                cur.execute("""
                    SELECT id, content, source, metadata, timestamp, embedding_dim, embedding_json
                    FROM unified_memory_records
                    WHERE LOWER(content) LIKE ? OR LOWER(metadata) LIKE ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (f"%{q}%", f"%{q}%", limit))

                for row in cur.fetchall():
                    rid, content, source, meta_str, ts, emb_dim, emb_json = row
                    meta = json.loads(meta_str) if meta_str else {}
                    embedding = None
                    if emb_dim and emb_json:
                        vec = tuple(json.loads(emb_json))
                        embedding = MemoryEmbedding(vector=vec, dimension=emb_dim)

                    # Simple token overlap score for ranking
                    words = set(q.split())
                    target_words = set(content.lower().split())
                    overlap = len(words.intersection(target_words)) / max(len(words), 1)
                    score = max(0.1, min(1.0, overlap))

                    if score >= min_score:
                        matches.append(
                            MemoryRecord(
                                id=rid,
                                content=content,
                                source=source,
                                metadata=meta,
                                timestamp=float(ts),
                                embedding=embedding,
                                score=score,
                            )
                        )
        except Exception as e:
            logger.error(f"SqliteMemoryProvider.search error: {e}")

        matches.sort(key=lambda m: m.score or 0.0, reverse=True)
        return tuple(matches)

    def delete(self, record_id: str) -> bool:
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM unified_memory_records WHERE id = ?", (record_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"SqliteMemoryProvider.delete error: {e}")
            return False


class ChromaMemoryProvider(BaseMemoryProvider):
    """ChromaDB vector memory provider (priority=50)."""

    def __init__(self, priority: int = 50):
        super().__init__(name="chroma_vector", priority=priority)

    def is_healthy(self) -> bool:
        try:
            from tools.memory.honcho_connect import get_project_collection
            coll = get_project_collection("code")
            return coll is not None
        except Exception:
            return False

    def store(self, record: MemoryRecord) -> bool:
        try:
            from tools.memory.honcho_connect import get_project_collection
            coll = get_project_collection("code")
            if coll is None:
                return False
            meta = dict(record.metadata)
            meta["source"] = record.source
            meta["timestamp"] = record.timestamp
            coll.upsert(
                ids=[record.id],
                documents=[record.content],
                metadatas=[meta],
            )
            return True
        except Exception as e:
            logger.debug(f"ChromaMemoryProvider.store unavailable: {e}")
            return False

    def search(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> Tuple[MemoryRecord, ...]:
        try:
            from tools.memory.honcho_connect import get_project_collection
            coll = get_project_collection("code")
            if coll is None:
                return ()
            results = coll.query(query_texts=[query], n_results=limit)
            if not results or not results.get("ids") or not results["ids"][0]:
                return ()

            matches: List[MemoryRecord] = []
            ids = results["ids"][0]
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0] if "distances" in results else []

            for i, rid in enumerate(ids):
                doc = docs[i] if i < len(docs) else ""
                meta = metas[i] if i < len(metas) else {}
                dist = distances[i] if i < len(distances) else 0.5
                score = max(0.0, 1.0 - float(dist)) if dist is not None else 0.5
                if score >= min_score:
                    matches.append(
                        MemoryRecord(
                            id=rid,
                            content=doc,
                            source="chroma",
                            metadata=meta or {},
                            timestamp=float(meta.get("timestamp", time.time())),
                            score=score,
                        )
                    )
            return tuple(matches)
        except Exception as e:
            logger.debug(f"ChromaMemoryProvider.search unavailable: {e}")
            return ()

    def delete(self, record_id: str) -> bool:
        try:
            from tools.memory.honcho_connect import get_project_collection
            coll = get_project_collection("code")
            if coll is None:
                return False
            coll.delete(ids=[record_id])
            return True
        except Exception as e:
            logger.debug(f"ChromaMemoryProvider.delete unavailable: {e}")
            return False


class HonchoMemoryProvider(BaseMemoryProvider):
    """Honcho System 3 Memory Provider (priority=90)."""

    def __init__(self, priority: int = 90):
        super().__init__(name="honcho_remote", priority=priority)

    def is_healthy(self) -> bool:
        try:
            from tools.memory.honcho_connect import is_honcho_healthy
            return bool(is_honcho_healthy())
        except Exception:
            return False

    def store(self, record: MemoryRecord) -> bool:
        try:
            from tools.memory.honcho_connect import save_concept
            cat = str(record.metadata.get("category", "general"))
            save_concept(cat, record.content, session_id=record.id)
            return True
        except Exception as e:
            logger.debug(f"HonchoMemoryProvider.store unavailable: {e}")
            return False

    def search(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> Tuple[MemoryRecord, ...]:
        try:
            from tools.memory.honcho_connect import search_concepts
            results = search_concepts(query, limit=limit)
            if not results:
                return ()
            matches: List[MemoryRecord] = []
            for r in results:
                cid = str(r.get("id", f"honcho_{int(time.time())}"))
                content = str(r.get("content", r.get("summary", "")))
                score = float(r.get("score", 0.8))
                if score >= min_score:
                    matches.append(
                        MemoryRecord(
                            id=cid,
                            content=content,
                            source="honcho",
                            metadata=r,
                            timestamp=float(r.get("timestamp", time.time())),
                            score=score,
                        )
                    )
            return tuple(matches)
        except Exception as e:
            logger.debug(f"HonchoMemoryProvider.search unavailable: {e}")
            return ()

    def delete(self, record_id: str) -> bool:
        try:
            from tools.memory.honcho_connect import delete_concept
            delete_concept(record_id)
            return True
        except Exception as e:
            logger.debug(f"HonchoMemoryProvider.delete unavailable: {e}")
            return False


# ── UNIFIED SEAM CONTROLLER (ROLE 3: CONSUMER) ──────────────────────────────

class UnifiedMemorySeam:
    """Unified Memory Seam Controller.

    Exposes a consolidated API over Honcho, Chroma, and SQLite.
    Resolves providers in descending priority order and automatically falls back
    to local SQLite if higher-tier stores are unreachable.
    """

    def __init__(
        self,
        providers: Optional[Sequence[BaseMemoryProvider]] = None,
        mirror_to_fallback: bool = True,
    ) -> None:
        self.fallback_provider = SqliteMemoryProvider(priority=10)
        default_providers = [
            HonchoMemoryProvider(priority=90),
            ChromaMemoryProvider(priority=50),
            self.fallback_provider,
        ]
        self._providers = sorted(
            providers if providers is not None else default_providers,
            key=lambda p: p.priority,
            reverse=True,
        )
        self.mirror_to_fallback = mirror_to_fallback

    def get_healthy_providers(self) -> List[BaseMemoryProvider]:
        """Returns all providers currently passing their health check, sorted by priority."""
        return [p for p in self._providers if p.is_healthy()]

    def store(self, record: MemoryRecord) -> bool:
        """Stores the record in the primary available provider and mirrors to fallback SQLite."""
        stored_any = False
        target_provider = None

        for p in self._providers:
            if p.is_healthy():
                target_provider = p
                break

        if target_provider is None:
            target_provider = self.fallback_provider

        success = target_provider.store(record)
        if success:
            stored_any = True

        # Always mirror to local SQLite if enabled and primary wasn't SQLite
        if self.mirror_to_fallback and target_provider != self.fallback_provider:
            try:
                self.fallback_provider.store(record)
            except Exception as e:
                logger.debug(f"Failed to mirror memory record to fallback: {e}")

        return stored_any

    def search(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> MemoryQueryResult:
        """Executes unified memory search with automatic fallback."""
        start_time = time.perf_counter()
        fallback_occurred = False
        provider_used = "none"

        for p in self._providers:
            if not p.is_healthy():
                fallback_occurred = True
                continue

            try:
                matches = p.search(query, limit=limit, min_score=min_score)
                provider_used = p.name
                if matches:
                    duration_ms = (time.perf_counter() - start_time) * 1000.0
                    return MemoryQueryResult(
                        matches=matches,
                        query=query,
                        total_count=len(matches),
                        provider_used=provider_used,
                        latency_ms=duration_ms,
                        fallback_occurred=fallback_occurred or (p != self._providers[0]),
                    )
            except Exception as e:
                logger.warning(f"Provider '{p.name}' search failed: {e}; falling back...")
                fallback_occurred = True

        # If primary stores had no hits or failed, query local SQLite fallback
        fallback_occurred = True
        provider_used = self.fallback_provider.name
        matches = self.fallback_provider.search(query, limit=limit, min_score=min_score)
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        return MemoryQueryResult(
            matches=matches,
            query=query,
            total_count=len(matches),
            provider_used=provider_used,
            latency_ms=duration_ms,
            fallback_occurred=fallback_occurred,
        )

    def delete(self, record_id: str) -> bool:
        """Deletes a record across all providers."""
        deleted_any = False
        for p in self._providers:
            if p.is_healthy():
                try:
                    if p.delete(record_id):
                        deleted_any = True
                except Exception:
                    pass
        # Also clean fallback
        if self.fallback_provider.delete(record_id):
            deleted_any = True
        return deleted_any
