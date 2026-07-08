"""
antigravity_importer.py — Antigravity IDE session history → Kenbun session_search index.

Antigravity (Google's agentic IDE) writes a clean JSONL transcript for every
conversation at:

    ~/.gemini/antigravity/brain/<trajectory_id>/.system_generated/logs/transcript.jsonl

This module ingests those transcripts into the same SQLite FTS5 database that
`session_search` queries (state.db, schema identical to tools/utils/sessions_db.py),
making the user's entire Antigravity history searchable from any MCP client.

It is split into two stdlib-only modes so the extract can run where the files
live (the user's Mac) while the index lives where search executes (the remote
Kenbun container, which has no access to the Mac's ~/.gemini):

    extract  — walk brain dirs, emit normalized JSONL records on stdout
    apply    — read those records on stdin, idempotently upsert into state.db

Idempotency: a per-trajectory high-water mark (ag_sync_state.last_step_index)
means re-running a sync only inserts steps newer than what is already indexed,
so the sync can run on a schedule or before every search. The index is a
rebuildable cache — losing it just means re-running a full sync.

Typical pipeline (from the Mac):

    python3 core/tools/sensory/antigravity_importer.py extract \
      | ssh lg2025 docker exec -i portable_fastmcp \
          python3 /app/core/tools/sensory/antigravity_importer.py apply

Format risk: transcript.jsonl is not a documented Google format. Unknown or
malformed records are counted and skipped, never fatal.
"""
import argparse
import datetime
import glob
import json
import os
import re
import sqlite3
import sys

DEFAULT_BRAIN_DIR = os.path.expanduser("~/.gemini/antigravity/brain")
TRANSCRIPT_REL = ".system_generated/logs/transcript.jsonl"
SESSION_SOURCE = "antigravity"
MAX_CONTENT_CHARS = 20000
TITLE_MAX = 72

# Step types that only restate other steps or carry no recall value.
# CONVERSATION_HISTORY re-embeds the whole conversation and would flood FTS
# with duplicates; EPHEMERAL_MESSAGE is transient UI status; CHECKPOINT is
# internal bookkeeping.
SKIP_TYPES = {"CONVERSATION_HISTORY", "EPHEMERAL_MESSAGE", "CHECKPOINT"}

USER_REQUEST_RE = re.compile(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", re.DOTALL)
METADATA_BLOCK_RE = re.compile(r"<ADDITIONAL_METADATA>.*?</ADDITIONAL_METADATA>", re.DOTALL)


def clean_user_content(text):
    m = USER_REQUEST_RE.search(text)
    if m:
        text = m.group(1)
    return METADATA_BLOCK_RE.sub("", text).strip()


def map_role(rec):
    if rec.get("source") == "USER_EXPLICIT":
        return "user", None
    rtype = rec.get("type") or "GENERIC"
    if rtype == "PLANNER_RESPONSE":
        return "assistant", None
    if rec.get("source") == "SYSTEM":
        return "system", None
    return "tool", rtype.lower()


def iter_transcript(path):
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except (json.JSONDecodeError, ValueError):
                yield None  # counted as skipped by caller


def extract_trajectory(trajectory_id, transcript_path):
    """Yield a session record then message records for one trajectory."""
    messages = []
    skipped = 0
    title = None
    for rec in iter_transcript(transcript_path):
        if rec is None or not isinstance(rec, dict):
            skipped += 1
            continue
        if rec.get("type") in SKIP_TYPES:
            continue
        role, tool_name = map_role(rec)
        content = rec.get("content") or ""
        if role == "user":
            content = clean_user_content(content)
        if role == "assistant" and not content.strip():
            content = rec.get("thinking") or ""
        if not content.strip() and not rec.get("tool_calls"):
            continue
        if title is None and role == "user" and content.strip():
            first_line = content.strip().splitlines()[0]
            title = first_line[:TITLE_MAX].strip()
        messages.append({
            "kind": "message",
            "trajectory_id": trajectory_id,
            "step_index": rec.get("step_index", -1),
            "role": role,
            "tool_name": tool_name,
            "content": content[:MAX_CONTENT_CHARS],
            "tool_calls": rec.get("tool_calls"),
            "timestamp": rec.get("created_at"),
        })
    if not messages:
        return
    # Suffix with the trajectory prefix so titles never collide with the
    # unique index on sessions.title.
    title = "%s [%s]" % (title or "Untitled Antigravity session", trajectory_id[:8])
    timestamps = [m["timestamp"] for m in messages if m["timestamp"]]
    yield {
        "kind": "session",
        "trajectory_id": trajectory_id,
        "title": title,
        "started_at": min(timestamps) if timestamps else None,
        "last_active_at": max(timestamps) if timestamps else None,
        "skipped_records": skipped,
    }
    for m in messages:
        yield m


def cmd_extract(args):
    pattern = os.path.join(args.brain_dir, "*", TRANSCRIPT_REL)
    paths = sorted(glob.glob(pattern))
    if args.trajectory:
        paths = [p for p in paths if args.trajectory in p]
    n_sessions = n_messages = 0
    for path in paths:
        trajectory_id = path[len(args.brain_dir):].lstrip("/").split("/")[0]
        for rec in extract_trajectory(trajectory_id, path) or []:
            sys.stdout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if rec["kind"] == "session":
                n_sessions += 1
            else:
                n_messages += 1
    sys.stderr.write("extract: %d sessions, %d messages from %d transcripts\n"
                     % (n_sessions, n_messages, len(paths)))


# ── apply side ───────────────────────────────────────────────────────────────
# Schema below must stay byte-compatible with tools/utils/sessions_db.init_db()
# so session_search reads this database without any changes.

SCHEMA = [
    '''CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY, source TEXT, user_id TEXT, model TEXT, title TEXT,
        system_prompt TEXT, config TEXT,
        token_count_input INTEGER DEFAULT 0, token_count_output INTEGER DEFAULT 0,
        parent_id TEXT, started_at TEXT, ended_at TEXT, last_active_at TEXT)''',
    '''CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_title
        ON sessions(title) WHERE title IS NOT NULL''',
    '''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
        role TEXT NOT NULL, content TEXT, tool_calls TEXT, tool_name TEXT,
        token_count INTEGER DEFAULT 0, timestamp TEXT,
        FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE)''',
    '''CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
        content, content='messages', content_rowid='id')''',
    '''CREATE TRIGGER IF NOT EXISTS t_messages_ai AFTER INSERT ON messages BEGIN
        INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
    END''',
    '''CREATE TRIGGER IF NOT EXISTS t_messages_ad AFTER DELETE ON messages BEGIN
        INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
    END''',
    '''CREATE TRIGGER IF NOT EXISTS t_messages_au AFTER UPDATE ON messages BEGIN
        INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
        INSERT INTO messages_fts(rowid, content) VALUES(new.id, new.content);
    END''',
    '''CREATE TABLE IF NOT EXISTS ag_sync_state (
        trajectory_id TEXT PRIMARY KEY,
        last_step_index INTEGER NOT NULL DEFAULT -1,
        synced_at TEXT)''',
]


def default_db_path():
    kenbun_dir = os.path.expanduser("~/.kenbun")
    os.makedirs(kenbun_dir, exist_ok=True)
    return os.path.join(kenbun_dir, "state.db")


def cmd_apply(args):
    db_path = args.db or default_db_path()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    for stmt in SCHEMA:
        conn.execute(stmt)

    watermarks = dict(conn.execute(
        "SELECT trajectory_id, last_step_index FROM ag_sync_state").fetchall())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    n_new_sessions = n_new_messages = n_skipped = 0

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            n_skipped += 1
            continue

        if rec.get("kind") == "session":
            tid = rec["trajectory_id"]
            cur = conn.execute(
                """INSERT OR IGNORE INTO sessions
                   (id, source, title, started_at, last_active_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (tid, SESSION_SOURCE, rec.get("title"),
                 rec.get("started_at"), rec.get("last_active_at")))
            if cur.rowcount:
                n_new_sessions += 1
            else:
                conn.execute(
                    "UPDATE sessions SET last_active_at = ? WHERE id = ? AND source = ?",
                    (rec.get("last_active_at"), tid, SESSION_SOURCE))

        elif rec.get("kind") == "message":
            tid = rec["trajectory_id"]
            step = rec.get("step_index", -1)
            if step <= watermarks.get(tid, -1):
                continue
            conn.execute(
                """INSERT INTO messages
                   (session_id, role, content, tool_calls, tool_name, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (tid, rec["role"], rec.get("content"),
                 json.dumps(rec["tool_calls"]) if rec.get("tool_calls") else None,
                 rec.get("tool_name"), rec.get("timestamp")))
            n_new_messages += 1
            conn.execute(
                """INSERT INTO ag_sync_state (trajectory_id, last_step_index, synced_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(trajectory_id) DO UPDATE SET
                     last_step_index = MAX(last_step_index, excluded.last_step_index),
                     synced_at = excluded.synced_at""",
                (tid, step, now))
        else:
            n_skipped += 1

    conn.commit()
    conn.close()
    print("apply: %d new sessions, %d new messages, %d skipped records (db: %s)"
          % (n_new_sessions, n_new_messages, n_skipped, db_path))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    sub = parser.add_subparsers(dest="mode", required=True)
    p_ext = sub.add_parser("extract", help="emit normalized JSONL from Antigravity brain dirs")
    p_ext.add_argument("--brain-dir", default=DEFAULT_BRAIN_DIR)
    p_ext.add_argument("--trajectory", help="only extract trajectories matching this id substring")
    p_app = sub.add_parser("apply", help="apply extracted JSONL from stdin into state.db")
    p_app.add_argument("--db", help="override state.db path (default ~/.kenbun/state.db)")
    args = parser.parse_args()
    cmd_extract(args) if args.mode == "extract" else cmd_apply(args)


if __name__ == "__main__":
    main()
