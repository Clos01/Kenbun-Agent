"""
SOW Router
==========
Per-project Statement of Work persistence — ONE row per Planka project_id, so
each project has its own SOW instead of one shared/hardcoded document.

Backed by the same PostgreSQL store as the intelligence layer
(tools.memory.postgres_client.get_connection).

NOTE (supervisor-caught bug, fixed here): `epics` may be omitted or null in the
payload. json.dumps(None) is "null" and json.dumps(undefined-equivalent) blows up
the driver, so we coalesce a missing/invalid value to [] before binding.
"""

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from tools.infrastructure.server_deps import verify_authorization
from tools.memory.postgres_client import get_connection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sow", tags=["SOW"])


class SOWUpsert(BaseModel):
    project_id: str = Field(..., min_length=1)
    project_name: str = ""
    board_id: str = ""
    title: Optional[str] = None
    content: Optional[str] = None
    epics: Any = Field(default_factory=list)
    # structured SOW fields: {client, consultant, hourly_rate, weekly_hours,
    # total_hours, date, overview, targets:[{label,value}], prereqs:[str]}
    meta: Any = Field(default_factory=dict)


def _ensure_table(cur) -> None:
    """Idempotent — creates the sows table on first use so no separate migration
    step is needed. Matches the init_db() convention in postgres_client."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sows (
            id SERIAL PRIMARY KEY,
            project_id VARCHAR(255) UNIQUE NOT NULL,
            project_name TEXT NOT NULL DEFAULT '',
            board_id VARCHAR(255) NOT NULL DEFAULT '',
            title TEXT,
            content TEXT,
            epics JSONB NOT NULL DEFAULT '[]'::jsonb,
            meta JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
        """
    )
    # idempotent add for tables created before `meta` existed
    cur.execute("ALTER TABLE sows ADD COLUMN IF NOT EXISTS meta JSONB NOT NULL DEFAULT '{}'::jsonb;")


@router.get("", dependencies=[Depends(verify_authorization)])
@router.get("/", dependencies=[Depends(verify_authorization)])
async def get_sow(project_id: str):
    """Load a single project's SOW. Returns an empty shell (exists=False) when the
    project has no SOW yet, so the editor can start a fresh one."""
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                _ensure_table(cur)
                cur.execute(
                    "SELECT project_id, project_name, board_id, title, content, epics, meta, "
                    "created_at, updated_at FROM sows WHERE project_id = %s",
                    (project_id,),
                )
                row = cur.fetchone()
                conn.commit()
        if not row:
            return {
                "project_id": project_id, "project_name": "", "board_id": "",
                "title": "", "content": "", "epics": [], "meta": {}, "exists": False,
            }
        row["exists"] = True
        return row
    except Exception as e:
        logger.error(f"get_sow failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load SOW")


@router.post("", dependencies=[Depends(verify_authorization)])
@router.post("/", dependencies=[Depends(verify_authorization)])
async def upsert_sow(payload: SOWUpsert):
    """Create or update a project's SOW (upsert on project_id)."""
    epics = payload.epics if payload.epics is not None else []
    meta = payload.meta if payload.meta is not None else {}
    try:
        epics_json = json.dumps(epics)
    except (TypeError, ValueError):
        epics_json = "[]"
    try:
        meta_json = json.dumps(meta)
    except (TypeError, ValueError):
        meta_json = "{}"
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                _ensure_table(cur)
                cur.execute(
                    """
                    INSERT INTO sows
                        (project_id, project_name, board_id, title, content, epics, meta, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, now())
                    ON CONFLICT (project_id) DO UPDATE SET
                        project_name = EXCLUDED.project_name,
                        board_id     = EXCLUDED.board_id,
                        title        = EXCLUDED.title,
                        content      = EXCLUDED.content,
                        epics        = EXCLUDED.epics,
                        meta         = EXCLUDED.meta,
                        updated_at   = now()
                    RETURNING project_id, project_name, board_id, title, content, epics, meta,
                              created_at, updated_at
                    """,
                    (payload.project_id, payload.project_name or "", payload.board_id or "",
                     payload.title, payload.content, epics_json, meta_json),
                )
                row = cur.fetchone()
                conn.commit()
        return {"ok": True, "sow": row}
    except Exception as e:
        logger.error(f"upsert_sow failed for {payload.project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save SOW")


@router.get("/list", dependencies=[Depends(verify_authorization)])
async def list_sows():
    """Lightweight index of every project that has a SOW (for the selector)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                _ensure_table(cur)
                cur.execute(
                    "SELECT project_id, project_name, board_id, title, updated_at "
                    "FROM sows ORDER BY updated_at DESC"
                )
                rows = cur.fetchall()
                conn.commit()
        return {"sows": rows}
    except Exception as e:
        logger.error(f"list_sows failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to list SOWs")
