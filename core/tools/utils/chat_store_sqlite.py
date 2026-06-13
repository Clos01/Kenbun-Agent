"""SQLite-backed chat session store (scalability issue #3).

Replaces the single flat ``chat_sessions.json`` + global spin-wait lockfile with
a WAL-mode SQLite database:
  * message appends are O(1) INSERTs, not whole-file rewrites;
  * WAL gives concurrent readers + a single writer (no global lock that could
    fail and silently drop history);
  * no temp-file/rename corruption window.

This module holds ONLY the SQL. Public callers go through
``chat_history_manager`` (facade), which keeps the original function signatures
so api_server.py and the CLI need no changes.
"""
import json
import logging
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from core.tools.infrastructure.config import settings

logger = logging.getLogger("chat_store_sqlite")

# Bump when the schema changes; _init() applies forward migrations.
_SCHEMA_VERSION = 1

INITIAL_GREETING = (
    "I am the Kenbun interface. I monitor the Hivemind memory and execute "
    "System 1 reflexes. How can I assist you?"
)

# One-shot guard so the legacy JSON import is attempted at most once per process.
_migration_done = False


def get_db_path() -> Path:
    """Absolute path to the SQLite chat database."""
    settings.BRAIN_HEALTH_DIR.mkdir(parents=True, exist_ok=True)
    return settings.BRAIN_HEALTH_DIR / "chat_sessions.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path()), check_same_thread=False, timeout=5.0)
    conn.row_factory = sqlite3.Row
    # WAL: concurrent reads alongside one writer. foreign_keys is per-connection.
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def _init(conn: sqlite3.Connection) -> None:
    """Create the schema if absent (idempotent) and stamp the schema version."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id         TEXT PRIMARY KEY,
            title      TEXT NOT NULL,
            timestamp  TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            id         TEXT NOT NULL,
            sender     TEXT NOT NULL,
            content    TEXT NOT NULL,
            timestamp  TEXT NOT NULL,
            seq        INTEGER NOT NULL,
            PRIMARY KEY (session_id, id)
        );
        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, seq);
        """
    )
    if conn.execute("PRAGMA user_version;").fetchone()[0] < _SCHEMA_VERSION:
        # PRAGMA cannot be parameterized; _SCHEMA_VERSION is an int literal.
        conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION};")
    conn.commit()


def _store() -> sqlite3.Connection:
    """Open a ready-to-use connection: schema ensured + legacy import attempted."""
    conn = _connect()
    _init(conn)
    _maybe_migrate_legacy_json(conn)
    return conn


def _maybe_migrate_legacy_json(conn: sqlite3.Connection) -> None:
    """One-time import of the old chat_sessions.json into SQLite.

    Runs inside a single transaction; on success the legacy file is renamed to
    ``chat_sessions.json.migrated`` (kept, never deleted) as a manual rollback
    artifact. On failure the JSON is left in place so a later process retries.
    """
    global _migration_done
    if _migration_done:
        return
    _migration_done = True

    legacy = settings.BRAIN_HEALTH_DIR / "chat_sessions.json"
    if not legacy.exists():
        return
    if conn.execute("SELECT COUNT(*) FROM sessions;").fetchone()[0] > 0:
        return  # DB already populated — don't clobber.

    try:
        raw = legacy.read_text(encoding="utf-8").strip()
        data = json.loads(raw) if raw else []
    except Exception as e:
        logger.error("Legacy chat migration: could not parse %s: %s", legacy, e)
        return

    try:
        with conn:  # single atomic transaction
            for s in data:
                sid = s.get("id")
                if not sid:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO sessions(id, title, timestamp, created_at) VALUES (?,?,?,?)",
                    (sid, s.get("title", "New Transmissions"), s.get("timestamp", ""), time.time()),
                )
                for i, m in enumerate(s.get("messages", [])):
                    conn.execute(
                        "INSERT OR IGNORE INTO messages(session_id, id, sender, content, timestamp, seq) "
                        "VALUES (?,?,?,?,?,?)",
                        (
                            sid,
                            m.get("id", f"msg_{uuid.uuid4().hex[:12]}"),
                            m.get("sender", "kenbun"),
                            m.get("content", ""),
                            m.get("timestamp", ""),
                            i,
                        ),
                    )
        legacy.rename(legacy.with_suffix(".json.migrated"))
        logger.info("Migrated %d legacy chat session(s) from JSON to SQLite.", len(data))
    except Exception as e:
        logger.error("Legacy chat migration failed (JSON left in place): %s", e)


def _derive_title(content: str) -> str:
    """First-user-message auto-title: word-aware truncation (parity with JSON impl)."""
    raw = content.strip()
    if len(raw) <= 25:
        return raw
    short = ""
    for w in raw.split():
        if len(short) + len(w) + 1 <= 22:
            short += (" " if short else "") + w
        else:
            break
    return short + "..." if short else raw[:22] + "..."


def _msg_dict(row: sqlite3.Row) -> Dict:
    return {
        "id": row["id"],
        "sender": row["sender"],
        "content": row["content"],
        "timestamp": row["timestamp"],
    }


# ── Public CRUD (mirrors the original chat_history_manager API) ──────────────

def create_session(title: str = "New Transmissions") -> Dict:
    sid = f"session_{uuid.uuid4().hex[:12]}"
    ts = datetime.fromtimestamp(time.time()).isoformat()
    conn = _store()
    try:
        with conn:
            conn.execute(
                "INSERT INTO sessions(id, title, timestamp, created_at) VALUES (?,?,?,?)",
                (sid, title, ts, time.time()),
            )
            conn.execute(
                "INSERT INTO messages(session_id, id, sender, content, timestamp, seq) VALUES (?,?,?,?,?,?)",
                (sid, "initial", "kenbun", INITIAL_GREETING, ts, 0),
            )
    finally:
        conn.close()
    return {
        "id": sid,
        "title": title,
        "timestamp": ts,
        "messages": [
            {"id": "initial", "sender": "kenbun", "content": INITIAL_GREETING, "timestamp": ts}
        ],
    }


def get_session(session_id: str) -> Optional[Dict]:
    conn = _store()
    try:
        s = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not s:
            return None
        msgs = conn.execute(
            "SELECT id, sender, content, timestamp FROM messages WHERE session_id = ? ORDER BY seq",
            (session_id,),
        ).fetchall()
    finally:
        conn.close()
    return {
        "id": s["id"],
        "title": s["title"],
        "timestamp": s["timestamp"],
        "messages": [_msg_dict(m) for m in msgs],
    }


def list_sessions() -> List[Dict]:
    """Sidebar summaries. Single query with a correlated subquery for the last
    message — avoids the N+1 the supervisor flagged."""
    conn = _store()
    try:
        rows = conn.execute(
            """
            SELECT s.id, s.title, s.timestamp,
                   (SELECT content FROM messages m
                      WHERE m.session_id = s.id
                      ORDER BY m.seq DESC LIMIT 1) AS last_message
            FROM sessions s
            ORDER BY s.timestamp DESC
            """
        ).fetchall()
    finally:
        conn.close()
    summaries = []
    for r in rows:
        last = r["last_message"] or ""
        summaries.append(
            {
                "id": r["id"],
                "title": r["title"] or "New Transmissions",
                "timestamp": r["timestamp"] or "",
                "last_message": last[:60] + "..." if len(last) > 60 else last,
            }
        )
    return summaries


def delete_session(session_id: str) -> bool:
    conn = _store()
    try:
        with conn:
            cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return cur.rowcount > 0  # messages cascade via FK
    finally:
        conn.close()


def add_message_to_session(session_id: str, sender: str, content: str) -> Optional[Dict]:
    conn = _store()
    try:
        if not conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone():
            return None
        ts = datetime.fromtimestamp(time.time()).isoformat()
        mid = f"msg_{uuid.uuid4().hex[:12]}"
        with conn:
            seq = conn.execute(
                "SELECT COALESCE(MAX(seq), -1) + 1 AS nx FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()["nx"]
            conn.execute(
                "INSERT INTO messages(session_id, id, sender, content, timestamp, seq) VALUES (?,?,?,?,?,?)",
                (session_id, mid, sender, content, ts, seq),
            )
            # Auto-title on the first user message only.
            if sender == "user":
                user_count = conn.execute(
                    "SELECT COUNT(*) FROM messages WHERE session_id = ? AND sender = 'user'",
                    (session_id,),
                ).fetchone()[0]
                if user_count == 1:
                    conn.execute(
                        "UPDATE sessions SET title = ? WHERE id = ?",
                        (_derive_title(content), session_id),
                    )
    finally:
        conn.close()
    return {"id": mid, "sender": sender, "content": content, "timestamp": ts}
