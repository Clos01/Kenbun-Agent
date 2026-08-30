"""DSH-06 -- a small, cross-process log of provider failover activity.

The Resolver's health state lives in whichever process is running; the swarm
(MCP entrypoint) and the dashboard API are not always the same process. This
module writes a bounded JSONL trail to ``brain_health/`` (a local bind-mounted
volume) so the Observatory can show "what actually happened" regardless of
which process served the decomposition.

Concurrency: both the writer's read-modify-write and the reader's read are
guarded by an OS-level advisory lock (``fcntl.flock`` -- ``LOCK_EX`` for writes,
``LOCK_SH`` for reads) so a reader in one process can never observe the file
mid-truncate from a writer in another, plus a ``threading.Lock`` for threads
within one process. This mirrors ``orchestrator.log_to_dashboard``. Best-effort
throughout: a failure to record or read an event never breaks a swarm run.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import fcntl  # POSIX only (Linux container + macOS dev) -- absent on Windows
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

logger = logging.getLogger("kenbun.resolver_events")

_MAX_LINES = 200
_lock = threading.Lock()


def _path() -> Path:
    from tools.infrastructure.config import settings

    return settings.BRAIN_HEALTH_DIR / "resolver_events.jsonl"


def record(kind: str, *, capability: str, provider: Optional[str] = None,
           detail: str = "", providers_order: Optional[List[str]] = None) -> None:
    """Append one event. ``kind`` is 'failover' | 'exhausted' | 'recovered'."""
    event: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "capability": capability,
        "provider": provider,
        "detail": detail[:280],
    }
    if providers_order:
        event["providers_order"] = providers_order
    line = json.dumps(event, ensure_ascii=False)

    try:
        with _lock:
            p = _path()
            p.parent.mkdir(parents=True, exist_ok=True)
            # a+ so the file is created if missing; we manage the offset ourselves.
            with open(p, "a+", encoding="utf-8") as f:
                if fcntl is not None:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.seek(0)
                    existing = [ln for ln in f.read().splitlines() if ln.strip()]
                    existing.append(line)
                    f.seek(0)
                    f.truncate()
                    f.write("\n".join(existing[-_MAX_LINES:]) + "\n")
                finally:
                    if fcntl is not None:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError as e:  # disk full, perms -- telemetry is never load-bearing
        logger.debug("resolver_events: could not record %s: %s", kind, e)


def recent(limit: int = 50) -> List[Dict[str, Any]]:
    """Most-recent-first list of events. Empty list if nothing has happened."""
    try:
        p = _path()
        if not p.exists():
            return []
        with open(p, "r", encoding="utf-8") as f:
            if fcntl is not None:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)   # blocks against a concurrent record()
            try:
                raw = f.read()
            finally:
                if fcntl is not None:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        out: List[Dict[str, Any]] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        out.reverse()
        return out[:limit]
    except OSError as e:
        logger.debug("resolver_events: could not read events: %s", e)
        return []
