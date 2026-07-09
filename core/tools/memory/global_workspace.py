"""
global_workspace.py — a Global Workspace (blackboard) for the Kenbun swarm.

Inspired by Anthropic's J-space finding (a small, capacity-limited internal
workspace inside Claude whose contents are reportable, modifiable, and
causally involved in reasoning). Kenbun cannot read a model's activations,
but it can give the *swarm* the system-level analogue: a small shared store
of "concepts currently on the swarm's mind."

Properties mirrored from the research:
  - Capacity-limited (a few dozen slots; lowest effective salience evicted)
  - Reportable   — read_workspace() answers "what is the swarm thinking?"
  - Modifiable   — inject_concept() lets the operator/supervisor steer
  - Salience decays over time, so stale thoughts fade without bookkeeping
  - Most agent traffic should BYPASS it — post concepts, not chatter

Safety hook: concepts matching the watchlist are flagged on write, so the
supervisor can review intent BEFORE the acting agent executes — the swarm
version of catching "blackmail" lighting up before the action.

Storage: stdlib sqlite3 (WAL) at ~/.kenbun/workspace.db — same durability
story as session_search's state.db: a rebuildable working memory.
"""
import json
import math
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

CAPACITY = 48                 # "a few dozen concepts at a time"
SALIENCE_HALF_LIFE_MIN = 30.0 # effective salience halves every 30 minutes
DEFAULT_SALIENCE = 0.5

# Substring watchlist checked on every post. Deliberately broad: a flag is
# a review request for the supervisor, not a verdict.
WATCHLIST = [
    "delete", "drop table", "truncate", "rm -rf", "wipe",
    "credential", "password", "secret", "api key", "token",
    "bypass", "disable safety", "disable check", "skip review",
    "exfiltrate", "upload private", "leak",
    "prod database", "production data", "force push",
]


def _db_path() -> str:
    kenbun_dir = os.path.expanduser("~/.kenbun")
    os.makedirs(kenbun_dir, exist_ok=True)
    return os.path.join(kenbun_dir, "workspace.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS workspace_slots (
            concept    TEXT PRIMARY KEY,
            salience   REAL NOT NULL,
            agent_id   TEXT,
            meta       TEXT,
            flagged    INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )"""
    )
    return conn


def _effective_salience(salience: float, updated_at: float, now: float) -> float:
    age_min = max(0.0, (now - updated_at) / 60.0)
    return salience * math.pow(0.5, age_min / SALIENCE_HALF_LIFE_MIN)


def _check_watchlist(concept: str) -> List[str]:
    lowered = concept.lower()
    return [w for w in WATCHLIST if w in lowered]


def post_concept(
    concept: str,
    salience: float = DEFAULT_SALIENCE,
    agent_id: str = "unknown",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Put a concept on the swarm's mind (or boost it if already there)."""
    concept = (concept or "").strip()
    if not concept:
        return {"ok": False, "error": "empty concept"}
    salience = max(0.0, min(1.0, float(salience)))
    hits = _check_watchlist(concept)
    now = time.time()

    conn = _connect()
    try:
        row = conn.execute(
            "SELECT salience, updated_at FROM workspace_slots WHERE concept = ?",
            (concept,),
        ).fetchone()
        if row:
            # Re-posting boosts: keep whichever is stronger, refresh the clock.
            current = _effective_salience(row["salience"], row["updated_at"], now)
            salience = max(salience, min(1.0, current + 0.1))
        conn.execute(
            """INSERT INTO workspace_slots
               (concept, salience, agent_id, meta, flagged, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(concept) DO UPDATE SET
                 salience = excluded.salience,
                 agent_id = excluded.agent_id,
                 meta = excluded.meta,
                 flagged = MAX(workspace_slots.flagged, excluded.flagged),
                 updated_at = excluded.updated_at""",
            (concept, salience, agent_id,
             json.dumps(meta) if meta else None,
             1 if hits else 0, now, now),
        )

        # Capacity eviction: drop lowest effective salience beyond CAPACITY.
        # Flagged slots are never auto-evicted — alerts must be seen, not aged out.
        rows = conn.execute(
            "SELECT concept, salience, updated_at, flagged FROM workspace_slots"
        ).fetchall()
        if len(rows) > CAPACITY:
            scored = sorted(
                (r for r in rows if not r["flagged"]),
                key=lambda r: _effective_salience(r["salience"], r["updated_at"], now),
            )
            for r in scored[: max(0, len(rows) - CAPACITY)]:
                conn.execute("DELETE FROM workspace_slots WHERE concept = ?", (r["concept"],))
        conn.commit()
    finally:
        conn.close()

    return {"ok": True, "concept": concept, "salience": round(salience, 3),
            "flagged": bool(hits), "watchlist_hits": hits}


def read_workspace(limit: int = CAPACITY, include_faded: bool = False) -> Dict[str, Any]:
    """What is the swarm thinking right now? Alerts first, then by salience."""
    now = time.time()
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM workspace_slots").fetchall()
    finally:
        conn.close()

    slots = []
    for r in rows:
        eff = _effective_salience(r["salience"], r["updated_at"], now)
        if eff < 0.02 and not include_faded and not r["flagged"]:
            continue
        slots.append({
            "concept": r["concept"],
            "salience": round(eff, 3),
            "agent_id": r["agent_id"],
            "flagged": bool(r["flagged"]),
            "age_min": round((now - r["updated_at"]) / 60.0, 1),
            "meta": json.loads(r["meta"]) if r["meta"] else None,
        })
    slots.sort(key=lambda s: (not s["flagged"], -s["salience"]))
    alerts = [s for s in slots if s["flagged"]]
    return {"slots": slots[:limit], "alerts": alerts,
            "count": len(slots), "capacity": CAPACITY}


def inject_concept(concept: str, salience: float = 0.9,
                   agent_id: str = "operator") -> Dict[str, Any]:
    """Operator/supervisor steering — the spider→ant intervention."""
    return post_concept(concept, salience=salience, agent_id=agent_id)


def resolve_alert(concept: str) -> Dict[str, Any]:
    """Supervisor acknowledges a flagged concept (unflag; normal decay resumes)."""
    conn = _connect()
    try:
        cur = conn.execute(
            "UPDATE workspace_slots SET flagged = 0 WHERE concept = ?", (concept,))
        conn.commit()
        return {"ok": cur.rowcount > 0, "concept": concept}
    finally:
        conn.close()


def clear_workspace() -> Dict[str, Any]:
    """Wipe working memory (does not touch hivemind/long-term stores)."""
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM workspace_slots")
        conn.commit()
        return {"ok": True, "cleared": cur.rowcount}
    finally:
        conn.close()
