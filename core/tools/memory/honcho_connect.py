import os
import logging
import re
import uuid
import socket
import time
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from honcho import Honcho
from tools.infrastructure.config import settings
from tools.utils.path_utils import get_project_root

logger = logging.getLogger(__name__)

_LOCAL_DB_LOCK = threading.Lock()


def _get_local_db_path() -> Path:
    base = Path(get_project_root()) / "brain_health"
    base.mkdir(parents=True, exist_ok=True)
    return base / "honcho_local.db"


def _init_local_db():
    db_path = _get_local_db_path()
    with _LOCAL_DB_LOCK, sqlite3.connect(str(db_path)) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS honcho_local_messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                peer_name TEXT NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            );
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_honcho_session ON honcho_local_messages(session_id);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_honcho_category ON honcho_local_messages(category);")
        con.commit()


def _is_local_db_healthy() -> bool:
    try:
        _init_local_db()
        return True
    except Exception:
        return False


def _save_local_message(content: str, category: str, peer_name: str) -> str:
    try:
        _init_local_db()
        msg_id = f"hlm_{uuid.uuid4().hex[:12]}"
        sess_id = safe_session_name(category)
        now = time.time()
        db_path = _get_local_db_path()
        with _LOCAL_DB_LOCK, sqlite3.connect(str(db_path)) as con:
            con.execute(
                "INSERT INTO honcho_local_messages (id, session_id, peer_name, category, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (msg_id, sess_id, peer_name, category, content, now)
            )
            con.commit()
        return msg_id
    except Exception as e:
        logger.warning("Local memory write failed: %s", e)
        return ""


def _search_local_messages(query_text: str, n_results: int = 5, category: str = "concepts") -> List[str]:
    try:
        db_path = _get_local_db_path()
        if not db_path.exists():
            return []
        sess_id = safe_session_name(category)
        tokens = [t.strip().lower() for t in query_text.split() if len(t.strip()) > 2]
        with _LOCAL_DB_LOCK, sqlite3.connect(str(db_path)) as con:
            con.row_factory = sqlite3.Row
            if tokens:
                where_clauses = " OR ".join(["LOWER(content) LIKE ?" for _ in tokens])
                params = [f"%{t}%" for t in tokens]
                sql = f"SELECT content FROM honcho_local_messages WHERE (category = ? OR session_id = ?) AND ({where_clauses}) ORDER BY created_at DESC LIMIT ?"
                rows = con.execute(sql, [category, sess_id, *params, n_results]).fetchall()
            else:
                sql = "SELECT content FROM honcho_local_messages WHERE (category = ? OR session_id = ?) ORDER BY created_at DESC LIMIT ?"
                rows = con.execute(sql, [category, sess_id, n_results]).fetchall()
            return [r["content"] for r in rows if r["content"]]
    except Exception as e:
        logger.warning("Local memory search failed: %s", e)
        return []


def _probe_tcp(host: str, port: int, timeout: float = 0.8) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _record_memory_degraded(store: str, err: BaseException) -> None:
    """DSH-06 s5: a memory read that fell through to empty because the store was
    unreachable (not because there were genuinely no matches) is recorded to the
    cross-process resolver_events trail, so the Observatory Resilience panel
    shows memory is degraded instead of it being silent."""
    try:
        from tools.strategy.resolver_events import record
        record("degraded", capability="memory", provider=store,
               detail=f"{store} read failed ({type(err).__name__})")
    except Exception as rec_err:  # noqa: BLE001 -- telemetry must never break a memory read
        logger.debug("resolver_events unavailable for memory-degraded event: %s", type(rec_err).__name__)


HONCHO_BASE_URL = os.getenv("HONCHO_BASE_URL", "http://127.0.0.1:8001")
_HONCHO_CLIENT = None
_HONCHO_HTTP_COOLDOWN_UNTIL = 0.0
_HONCHO_HTTP_COOLDOWN_S = 60.0

_CHROMA_CLIENT = None
_CHROMA_HTTP_COOLDOWN_UNTIL = 0.0
_CHROMA_HTTP_COOLDOWN_S = 60.0


# The system self-model peer vs. the human user peer. Previously everything was
# attributed to the system peer, so Honcho never built a model of the user. The
# user peer lets the deriver learn Carlos's preferences/decisions over time.
def _system_peer() -> str:
    return f"system_{settings.PROJECT_NAME}"

USER_PEER = os.getenv("KENBUN_USER_PEER", "carlos")


def get_honcho_client():
    global _HONCHO_CLIENT, _HONCHO_HTTP_COOLDOWN_UNTIL
    if _HONCHO_CLIENT is not None:
        return _HONCHO_CLIENT

    # If Honcho base URL points to port 8000 and Chroma is also on 8000, avoid collision
    if ":8000" in HONCHO_BASE_URL and settings.CHROMA_PORT == 8000:
        return None

    now = time.monotonic()
    if now < _HONCHO_HTTP_COOLDOWN_UNTIL:
        return None

    try:
        import urllib.parse
        parsed = urllib.parse.urlparse(HONCHO_BASE_URL)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not _probe_tcp(host, port, timeout=0.8):
            _HONCHO_HTTP_COOLDOWN_UNTIL = now + _HONCHO_HTTP_COOLDOWN_S
            return None
    except Exception:
        pass

    try:
        logger.info(f"📡 Connecting to Honcho at {HONCHO_BASE_URL}...")
        _HONCHO_CLIENT = Honcho(base_url=HONCHO_BASE_URL)
    except Exception as e:
        logger.warning(f"❌ Failed to connect to Honcho: {e}")
        _HONCHO_HTTP_COOLDOWN_UNTIL = now + _HONCHO_HTTP_COOLDOWN_S
    return _HONCHO_CLIENT


def is_honcho_ready() -> bool:
    """True if remote Honcho is online or local fallback memory is operational."""
    if get_honcho_client() is not None:
        return True
    return _is_local_db_healthy()


def get_chroma_client():
    global _CHROMA_CLIENT, _CHROMA_HTTP_COOLDOWN_UNTIL
    if _CHROMA_CLIENT is not None:
        return _CHROMA_CLIENT

    import chromadb
    from chromadb.config import Settings

    now = time.monotonic()
    # 1. Fast-probe remote/local HTTP endpoint if configured and not on cooldown
    host = settings.CHROMA_HOST
    port = int(settings.CHROMA_PORT)
    if now >= _CHROMA_HTTP_COOLDOWN_UNTIL:
        if _probe_tcp(host, port, timeout=0.8):
            try:
                client = chromadb.HttpClient(
                    host=host,
                    port=port,
                    settings=Settings(chroma_api_impl="chromadb.api.fastapi.FastAPI")
                )
                client.heartbeat()
                logger.info(f"✅ Connected to HTTP ChromaDB at {host}:{port}")
                _CHROMA_CLIENT = client
                return _CHROMA_CLIENT
            except Exception as e:
                logger.warning(f"⚠️ ChromaDB HTTP heartbeat failed: {e}. Cooldown activated.")
                _CHROMA_HTTP_COOLDOWN_UNTIL = now + _CHROMA_HTTP_COOLDOWN_S
        else:
            logger.debug("ChromaDB HTTP %s:%d unreachable (fast probe). Cooldown activated.", host, port)
            _CHROMA_HTTP_COOLDOWN_UNTIL = now + _CHROMA_HTTP_COOLDOWN_S

    # 2. Resilient Fallback: Persistent local client
    persistent_dir = os.getenv("KENBUN_CHROMA_LOCAL_PATH")
    if not persistent_dir:
        local_default = Path(get_project_root()) / "brain_health" / "chromadb_local"
        if local_default.exists():
            persistent_dir = str(local_default)
        else:
            persistent_dir = str(Path(get_project_root()) / "data" / "chromadb_local")

    try:
        os.makedirs(persistent_dir, exist_ok=True)
        _CHROMA_CLIENT = chromadb.PersistentClient(path=persistent_dir)
        logger.info(f"✅ Connected to persistent local ChromaDB at {persistent_dir}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Persistent ChromaDB client: {e}")
        _CHROMA_CLIENT = None

    return _CHROMA_CLIENT


def _resolve_collection(chroma, name: str):
    """Resolve a collection, checking for existing populated aliases."""
    if chroma is None:
        return None
    try:
        col = chroma.get_collection(name)
        if col.count() > 0:
            return col
    except Exception:
        col = None

    for candidate in [f"kenbun-agent.{name}_qjl", f"kenbun-agent.{name}", f"{settings.PROJECT_NAME}-{name}"]:
        try:
            c = chroma.get_collection(candidate)
            if c.count() > 0:
                logger.debug("Resolved collection '%s' to alias '%s' (%d items)", name, candidate, c.count())
                return c
        except Exception:
            continue

    if col is not None:
        return col
    return chroma.get_or_create_collection(name)

_SESSION_SAFE = re.compile(r"[^a-zA-Z0-9_-]+")


def safe_session_name(category: str, fallback: str = "concepts") -> str:
    """Coerce a caller-supplied category into a legal Honcho session id.

    Honcho requires session ids to match ^[a-zA-Z0-9_-]+$ and rejects anything
    else with a Pydantic string_pattern_mismatch on body.id. `category` reaches
    us straight from tool arguments, so any caller passing a space, a slash or a
    human-readable phrase blew up with a raw validation dump instead of saving.
    Two independent stress drivers (a local llama3.2 and Gemini) both hit this
    within a handful of calls by passing category=" ".
    """
    if not isinstance(category, str):
        return fallback
    cleaned = _SESSION_SAFE.sub("_", category.strip()).strip("_")
    return cleaned or fallback


def add_memory(content: str, category: str = "concepts", peer_name: str = None):
    """
    Sends a message to Honcho with dual-persistence into local SQLite and ChromaDB.
    """
    peer_name = peer_name or _system_peer()

    # 1. Dual-write to local SQLite store (guarantees local zero-loss)
    _save_local_message(content=content, category=category, peer_name=peer_name)

    # 2. Dual-write to local Chroma vector store
    chroma = get_chroma_client()
    if chroma:
        try:
            col = _resolve_collection(chroma, category)
            if col:
                col.upsert(
                    ids=[f"honcho_{uuid.uuid4().hex[:12]}"],
                    documents=[content],
                    metadatas=[{"category": category, "peer_name": peer_name, "source": "local_mirror"}]
                )
        except Exception as e:
            logger.debug("Chroma mirror write skipped: %s", e)

    # 3. Write to remote Honcho daemon if online
    client = get_honcho_client()
    if not client:
        return

    session = client.session(safe_session_name(category))
    peer = client.peer(peer_name)

    try:
        session.add_messages([peer.message(content)])
        logger.debug(f"✅ [HONCHO] Added memory for peer '{peer_name}'.")
    except Exception as e:
        logger.warning(f"⚠️ [HONCHO] Failed to add memory: {e}")


def add_user_memory(content: str, category: str = "preferences"):
    """Attribute a message/decision to the human user peer so Honcho personalizes over time."""
    return add_memory(content, category=category, peer_name=USER_PEER)


def retrieve_memory(query_text: str, n_results: int = 5, category: str = "concepts", peer_name: str = None):
    """
    Performs a semantic search against Honcho's reasoned representations with local Chroma/SQLite fallback.
    """
    client = get_honcho_client()
    peer_name = peer_name or _system_peer()

    if client:
        try:
            session = client.session(safe_session_name(category))
            conclusions = session.representation(
                peer_name,
                search_query=query_text,
                search_top_k=n_results
            )

            # SDK v2 returns the representation as one formatted string
            if isinstance(conclusions, str):
                if conclusions.strip():
                    return [conclusions]
            else:
                results = []
                for c in conclusions:
                    if hasattr(c, 'content'):
                        results.append(c.content)
                    elif isinstance(c, dict) and 'content' in c:
                        results.append(c['content'])
                    else:
                        results.append(str(c))
                if results:
                    return results
        except Exception as e:
            logger.error("⚠️ [HONCHO] Query failed (%s)", type(e).__name__)
            _record_memory_degraded("honcho", e)

    # Local Fallback 1: Query Chroma semantic vector collection
    chroma = get_chroma_client()
    if chroma:
        try:
            col = _resolve_collection(chroma, category)
            if col and col.count() > 0:
                res = col.query(query_texts=[query_text], n_results=n_results)
                docs = res.get("documents", [[]])[0]
                if docs and any(docs):
                    return [d for d in docs if d]
        except Exception as ce:
            logger.debug("Chroma fallback query skipped: %s", ce)

    # Local Fallback 2: Query local SQLite message store
    return _search_local_messages(query_text, n_results=n_results, category=category)


def search_messages(query_text: str, n_results: int = 5, category: str = "concepts"):
    """Search stored messages, falling back to local SQLite and Chroma vector stores when Honcho is offline."""
    client = get_honcho_client()
    contents = []

    if client:
        try:
            results = client.session(safe_session_name(category)).search(query_text)
            for msg in results:
                content = getattr(msg, "content", None)
                if content is None and isinstance(msg, dict):
                    content = msg.get("content")
                if content:
                    contents.append(content)
                if len(contents) >= n_results:
                    break
        except Exception as e:
            logger.error("⚠️ [HONCHO] Message search failed (%s)", type(e).__name__)
            _record_memory_degraded("honcho", e)

    if contents:
        return contents

    # Local Fallback 1: Search local SQLite message store
    local_msgs = _search_local_messages(query_text, n_results=n_results, category=category)
    if local_msgs:
        return local_msgs

    # Local Fallback 2: Search Chroma collection
    chroma = get_chroma_client()
    if chroma:
        try:
            col = _resolve_collection(chroma, category)
            if col and col.count() > 0:
                res = col.query(query_texts=[query_text], n_results=n_results)
                docs = res.get("documents", [[]])[0]
                return [d for d in docs if d]
        except Exception as ce:
            logger.debug("Chroma fallback search skipped: %s", ce)

    return []


def retrieve_user_memory(query_text: str, n_results: int = 5, category: str = "preferences"):
    """Retrieve the human user's reasoned representation (preferences/decisions)."""
    return retrieve_memory(query_text, n_results=n_results, category=category, peer_name=USER_PEER)


# --- ADAPTERS FOR BACKWARDS COMPATIBILITY ---
def upsert_embedding(id: str, document: str, metadata: dict, collection_name: str = None):
    """Adapter to map ChromaDB's upsert to Honcho's add_memory or local ChromaDB directly."""
    category = metadata.get("category", "concepts")
    chroma = get_chroma_client()
    if chroma:
        try:
            col_name = collection_name or category
            collection = _resolve_collection(chroma, col_name)
            collection.upsert(ids=[id], documents=[document], metadatas=[metadata])
            return
        except Exception as e:
            logger.warning("⚠️ [CHROMA] Upsert failed (%s). Falling back to Honcho.", type(e).__name__)
            _record_memory_degraded("chroma", e)

    content = f"METADATA: {metadata}\n\nCONTENT:\n{document}"
    add_memory(content, category=category)


def query_embeddings(query_text: str, n_results: int = 5, category: str = "concepts", filter_project: str = None, where: dict = None):
    """Adapter to map ChromaDB's query to Honcho's retrieve_memory or query local ChromaDB directly."""
    chroma = get_chroma_client()
    if chroma:
        try:
            collection = _resolve_collection(chroma, category)
            res = collection.query(query_texts=[query_text], n_results=n_results)
            # Fall back to Honcho if Chroma has no matching documents for this query
            if res.get("documents") and res["documents"][0]:
                return {
                    "ids": res.get("ids", [[]]),
                    "documents": res.get("documents", [[]]),
                    "metadatas": res.get("metadatas", [[]])
                }
        except Exception as e:
            logger.warning("⚠️ [CHROMA] Query failed (%s). Falling back to Honcho.", type(e).__name__)
            _record_memory_degraded("chroma", e)

    results = retrieve_memory(query_text, n_results=n_results, category=category)
    return {
        "ids": [[str(uuid.uuid4()) for _ in results]] if results else [[]],
        "documents": [results] if results else [[]],
        "metadatas": [[{"source": "honcho"}] * len(results)] if results else [[]]
    }


class DummyCollection:
    def __init__(self, name):
        self.name = name

    def add(self, ids, documents, metadatas=None):
        for doc, meta in zip(documents, metadatas or [{}] * len(documents)):
            upsert_embedding(id=str(uuid.uuid4()), document=doc, metadata=meta, collection_name=self.name)

    def upsert(self, ids, documents, metadatas=None):
        self.add(ids, documents, metadatas)

    def query(self, query_texts=None, query_embeddings=None, n_results=5, where=None, where_document=None, include=None, **kwargs):
        chroma = get_chroma_client()
        if chroma:
            try:
                collection = _resolve_collection(chroma, self.name)
                return collection.query(query_texts=query_texts, query_embeddings=query_embeddings, n_results=n_results, where=where, where_document=where_document, include=include, **kwargs)
            except Exception as e:
                logger.warning(f"⚠️ [CHROMA] Query failed: {e}")
        if query_texts:
            return query_embeddings(query_texts[0], n_results=n_results, category=self.name)
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    def count(self):
        chroma = get_chroma_client()
        if chroma:
            try:
                collection = _resolve_collection(chroma, self.name)
                return collection.count()
            except Exception as e:
                logger.warning(f"⚠️ [CHROMA] Count failed: {e}")
        return 0

    def get(self, ids=None, where=None, limit=None, offset=None, where_document=None, include=None, **kwargs):
        chroma = get_chroma_client()
        if chroma:
            try:
                collection = _resolve_collection(chroma, self.name)
                return collection.get(ids=ids, where=where, limit=limit, offset=offset, where_document=where_document, include=include, **kwargs)
            except Exception as e:
                logger.warning(f"⚠️ [CHROMA] Get failed: {e}")
        return {"ids": [], "embeddings": [], "documents": [], "metadatas": []}

    def delete(self, ids=None, where=None, **kwargs):
        chroma = get_chroma_client()
        if chroma:
            try:
                collection = _resolve_collection(chroma, self.name)
                return collection.delete(ids=ids, where=where, **kwargs)
            except Exception as e:
                logger.warning(f"⚠️ [CHROMA] Delete failed: {e}")
        return None

    def peek(self, limit=10, **kwargs):
        return self.get(limit=limit, **kwargs)


def get_project_collection(name: str):
    chroma = get_chroma_client()
    if chroma:
        try:
            return _resolve_collection(chroma, name)
        except Exception as e:
            logger.warning(f"⚠️ [CHROMA] Failed to get/create collection {name}: {e}. Falling back to Dummy.")
    return DummyCollection(name)
