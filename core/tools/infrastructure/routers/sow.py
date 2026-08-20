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

import html
import json
import logging
import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from tools.infrastructure.planka import _planka_request
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
async def get_sow(project_id: str) -> dict[str, Any]:
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
    except Exception:
        logger.error("get_sow failed for project_id: %s", project_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load SOW")


@router.post("", dependencies=[Depends(verify_authorization)])
@router.post("/", dependencies=[Depends(verify_authorization)])
async def upsert_sow(payload: SOWUpsert) -> dict[str, Any]:
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
    except Exception:
        logger.error("upsert_sow failed for project_id: %s", payload.project_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save SOW")


@router.get("/list", dependencies=[Depends(verify_authorization)])
async def list_sows() -> dict[str, Any]:
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
    except Exception:
        logger.error("list_sows failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list SOWs")


class SOWDispatchRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=128)
    board_id: Optional[str] = Field(None, max_length=128)
    target_list_name: str = Field("Backlog", max_length=64)


def _sanitize_text(val: Any, max_len: int = 2000) -> str:
    """Strips dangerous control chars, escapes HTML entities, and normalizes whitespace."""
    if not val or not isinstance(val, str):
        return ""
    # Strip null bytes and non-printable control chars
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", val).strip()
    escaped = html.escape(cleaned)
    return escaped[:max_len]


@router.post("/dispatch", dependencies=[Depends(verify_authorization)])
async def dispatch_sow_to_planka(payload: SOWDispatchRequest) -> dict[str, Any]:
    """
    Autonomous SOW-to-Kanban Dispatcher:
    Converts SOW scope deliverables and epics into structured Planka Kanban cards
    so autonomous agent swarms can pick up tasks with full context.
    """
    # 1. Validate ID formats (prevent path injection / traversal)
    id_pattern = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")
    if not id_pattern.match(payload.project_id):
        raise HTTPException(status_code=400, detail="Invalid project_id format.")
    if payload.board_id and not id_pattern.match(payload.board_id):
        raise HTTPException(status_code=400, detail="Invalid board_id format.")
        
    # 2. Retrieve the SOW
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                _ensure_table(cur)
                cur.execute(
                    "SELECT project_id, project_name, board_id, title, content, epics, meta "
                    "FROM sows WHERE project_id = %s",
                    (payload.project_id,)
                )
                sow_row = cur.fetchone()
                conn.commit()
    except Exception:
        logger.error("Failed to load SOW for dispatch: project_id=%s", payload.project_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to query database for SOW.")
        
    if not sow_row:
        raise HTTPException(status_code=404, detail="SOW not found for this project.")
        
    raw_board_id = payload.board_id or sow_row.get("board_id")
    if not raw_board_id or not isinstance(raw_board_id, str) or not id_pattern.match(raw_board_id):
        raise HTTPException(status_code=400, detail="Valid board_id is required to dispatch to Kanban.")
    board_id = raw_board_id.strip()
        
    # 3. Query the Planka board to inspect lists & cards
    try:
        board_data = _planka_request(f"/api/boards/{board_id}", "GET")
        included = board_data.get("included", {})
        lists = included.get("lists", [])
        existing_cards = included.get("cards", [])
    except (ConnectionError, ValueError, KeyError) as e:
        logger.error("Planka API communication error for board_id=%s: %s", board_id, e, exc_info=True)
        raise HTTPException(status_code=502, detail="Failed to communicate with Kanban backend service.")
    except Exception as e:
        logger.error("Unexpected error querying Planka board: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error during Kanban dispatch.")
        
    if not lists:
        raise HTTPException(status_code=400, detail="The specified Planka board has no lists.")
        
    target_list_name_clean = _sanitize_text(payload.target_list_name, max_len=64) or "Backlog"
    target_list = next((l for l in lists if isinstance(l, dict) and l.get("name", "").lower() == target_list_name_clean.lower()), lists[0])
    target_list_id = target_list.get("id")
    
    existing_card_names = {c.get("name", "").strip().lower() for c in existing_cards if isinstance(c, dict)}
    
    # 4. Extract items to dispatch from epics or meta (capped to 50 items)
    items_to_dispatch: list[dict[str, str]] = []
    
    epics = sow_row.get("epics") or []
    if isinstance(epics, list):
        for epic in epics:
            if isinstance(epic, dict):
                title = _sanitize_text(epic.get("title") or epic.get("name"), max_len=255)
                desc = _sanitize_text(epic.get("details") or epic.get("description") or epic.get("scope"), max_len=2000)
                done = bool(epic.get("completed") or epic.get("done") or epic.get("status") == "completed")
                if title and not done:
                    items_to_dispatch.append({"name": title, "description": desc})
                    
    meta = sow_row.get("meta") or {}
    deliverables = meta.get("deliverables") or []
    if isinstance(deliverables, list):
        for d in deliverables:
            if isinstance(d, dict):
                title = _sanitize_text(d.get("title") or d.get("name"), max_len=255)
                desc = _sanitize_text(d.get("details") or d.get("description"), max_len=2000)
                done = bool(d.get("completed") or d.get("done") or d.get("status") == "completed")
                if title and not done and title.lower() not in {it["name"].lower() for it in items_to_dispatch}:
                    items_to_dispatch.append({"name": title, "description": desc})
                    
    items_to_dispatch = items_to_dispatch[:50]
    
    if not items_to_dispatch:
        return {
            "ok": True,
            "message": "All SOW items are already completed or no deliverables found.",
            "dispatched_count": 0,
            "failed_count": 0,
            "created_cards": []
        }
        
    # 5. Create missing cards on the target list
    created_cards = []
    failed_cards = []
    for item in items_to_dispatch:
        card_name = item["name"]
        if card_name.lower() in existing_card_names:
            continue
            
        desc = f"### SOW Deliverable\n\n{item['description']}\n\n*Generated autonomously from SOW Studio.*"
        try:
            card_res = _planka_request(
                f"/api/lists/{target_list_id}/cards",
                "POST",
                {
                    "name": card_name,
                    "description": desc,
                    "position": 65535
                }
            )
            created_item = card_res.get("item", {}) if isinstance(card_res, dict) else {}
            created_cards.append({
                "id": created_item.get("id"),
                "name": card_name,
                "list_id": target_list_id
            })
            existing_card_names.add(card_name.lower())
        except (ConnectionError, ValueError, KeyError) as e:
            logger.warning("Failed to create Planka card '%s': %s", card_name, e)
            failed_cards.append({"name": card_name, "error": "Creation failed"})
        except Exception as e:
            logger.error("Unexpected error creating Planka card '%s': %s", card_name, e, exc_info=True)
            failed_cards.append({"name": card_name, "error": "Creation error"})
            
    is_success = len(created_cards) > 0 or len(failed_cards) == 0
    return {
        "ok": is_success,
        "message": f"Dispatched {len(created_cards)} SOW deliverables to '{target_list.get('name')}'." + (f" ({len(failed_cards)} failed)" if failed_cards else ""),
        "dispatched_count": len(created_cards),
        "failed_count": len(failed_cards),
        "created_cards": created_cards,
        "board_id": board_id,
        "list_name": target_list.get("name")
    }


