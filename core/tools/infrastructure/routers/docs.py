"""
Docs Router
===========
Per-project documentation — many docs per Planka project_id, keyed by slug.
Follows the same shape as the SOW router (project-scoped, idempotent table
creation, no separate migration step).

Why this exists rather than markdown-in-kanban-cards or a bolted-on wiki:

  * Kanban cards are work items. A card that is never "done" is a category
    error, and card descriptions have no revision history, no search, and no
    export path.
  * A separate wiki (Docmost et al.) is a second place to WRITE. Reading in
    many places is fine; writing in two places guarantees drift. It also does
    not travel to a client at handover.

So docs live in Kenbun's own Postgres, are addressable by (project_id, slug),
keep full revision history, are searchable with Postgres FTS, and can be
exported as plain markdown files for handover into a git repo.

Route ordering note: the literal paths (/list, /search, /export) are declared
BEFORE /{slug}, because FastAPI matches in declaration order and /{slug} would
otherwise swallow them.
"""

import json
import logging
import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from tools.infrastructure.server_deps import verify_authorization
from tools.memory.postgres_client import get_connection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/docs", tags=["Docs"])

# Categories are a fixed vocabulary on purpose. Free-text categories drift into
# synonyms ("infra"/"infrastructure"/"Infra") and stop being useful as filters.
CATEGORIES = ("general", "architecture", "runbook", "decision", "record", "reference")


class DocUpsert(BaseModel):
    project_id: str = Field(..., min_length=1)
    slug: Optional[str] = None          # derived from title when omitted
    title: str = Field(..., min_length=1)
    body: str = ""
    category: str = "general"
    tags: Any = Field(default_factory=list)
    author: str = ""


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s or "untitled")[:120]


def _ensure_table(cur) -> None:
    """Idempotent — creates the docs tables on first use, matching the
    init_db()/_ensure_table convention used elsewhere in this codebase."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS docs (
            id SERIAL PRIMARY KEY,
            project_id VARCHAR(255) NOT NULL,
            slug VARCHAR(255) NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL DEFAULT '',
            category VARCHAR(100) NOT NULL DEFAULT 'general',
            tags JSONB NOT NULL DEFAULT '[]'::jsonb,
            author VARCHAR(255) NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE (project_id, slug)
        );
        """
    )
    # Full snapshots rather than diffs: docs are small, and reconstructing a
    # point-in-time doc from a diff chain is the kind of cleverness that breaks
    # exactly when you need the history.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS doc_revisions (
            id SERIAL PRIMARY KEY,
            doc_id INTEGER NOT NULL REFERENCES docs(id) ON DELETE CASCADE,
            title TEXT,
            body TEXT,
            author VARCHAR(255) NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT now()
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS docs_project_idx ON docs (project_id, updated_at DESC);")
    cur.execute("CREATE INDEX IF NOT EXISTS doc_revisions_doc_idx ON doc_revisions (doc_id, created_at DESC);")
    # Postgres FTS rather than embeddings: deterministic, no network call, no
    # model dependency. Semantic search over docs can layer on later via Chroma.
    cur.execute(
        "CREATE INDEX IF NOT EXISTS docs_fts_idx ON docs "
        "USING GIN (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(body,'')));"
    )


@router.get("/list", dependencies=[Depends(verify_authorization)])
async def list_docs(project_id: str = "", category: str = "") -> dict[str, Any]:
    """Metadata index for a project — deliberately omits `body` so the sidebar
    does not pull every document's full text on every render."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                _ensure_table(cur)
                sql = (
                    "SELECT id, project_id, slug, title, category, tags, author, "
                    "length(body) AS size, created_at, updated_at FROM docs"
                )
                params: list = []
                clauses = []
                if project_id:
                    clauses.append("project_id = %s")
                    params.append(project_id)
                if category:
                    clauses.append("category = %s")
                    params.append(category)
                if clauses:
                    sql += " WHERE " + " AND ".join(clauses)
                sql += " ORDER BY category, title"
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
                conn.commit()
        return {"docs": rows, "categories": list(CATEGORIES)}
    except Exception as e:
        logger.error(f"list_docs failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to list docs")


@router.get("/search", dependencies=[Depends(verify_authorization)])
async def search_docs(q: str, project_id: str = "", limit: int = 20) -> dict[str, Any]:
    """Full-text search with a highlighted snippet per hit."""
    if not q.strip():
        return {"results": [], "query": q}
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                _ensure_table(cur)
                sql = """
                    SELECT id, project_id, slug, title, category, updated_at,
                           ts_headline('english', body, websearch_to_tsquery('english', %s),
                                       'MaxFragments=2, MaxWords=22, MinWords=6') AS snippet,
                           ts_rank(to_tsvector('english', coalesce(title,'') || ' ' || coalesce(body,'')),
                                   websearch_to_tsquery('english', %s)) AS rank
                      FROM docs
                     WHERE to_tsvector('english', coalesce(title,'') || ' ' || coalesce(body,''))
                           @@ websearch_to_tsquery('english', %s)
                """
                params: list = [q, q, q]
                if project_id:
                    sql += " AND project_id = %s"
                    params.append(project_id)
                sql += " ORDER BY rank DESC LIMIT %s"
                params.append(max(1, min(limit, 100)))
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
                conn.commit()
        return {"results": rows, "query": q}
    except Exception as e:
        logger.error(f"search_docs failed for {q!r}: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("/export", dependencies=[Depends(verify_authorization)])
async def export_docs(project_id: str) -> dict[str, Any]:
    """Every doc for a project as markdown files, ready to be written into a
    repo's docs/ directory. This is the handover path: a client developer gets
    the repo, not access to Kenbun, so documentation has to be able to leave."""
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                _ensure_table(cur)
                cur.execute(
                    "SELECT slug, title, body, category, tags, updated_at FROM docs "
                    "WHERE project_id = %s ORDER BY category, title",
                    (project_id,),
                )
                rows = cur.fetchall()
                conn.commit()

        files = []
        index_lines = ["# Documentation", ""]
        current_cat = None
        for r in rows:
            cat = r["category"] or "general"
            if cat != current_cat:
                index_lines += ["", f"## {cat.title()}", ""]
                current_cat = cat
            path = f"{cat}/{r['slug']}.md"
            index_lines.append(f"- [{r['title']}]({path})")
            front = [
                "---",
                f"title: {r['title']}",
                f"category: {cat}",
                f"updated: {r['updated_at']:%Y-%m-%d}" if r.get("updated_at") else "updated:",
                "---",
                "",
            ]
            files.append({"path": path, "content": "\n".join(front) + (r["body"] or "")})

        files.append({"path": "README.md", "content": "\n".join(index_lines) + "\n"})
        return {"project_id": project_id, "count": len(files), "files": files}
    except Exception as e:
        logger.error(f"export_docs failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Export failed")


@router.get("/revisions", dependencies=[Depends(verify_authorization)])
async def doc_revisions(project_id: str, slug: str, limit: int = 25) -> dict[str, Any]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                _ensure_table(cur)
                cur.execute(
                    """
                    SELECT r.id, r.title, r.body, r.author, r.created_at, length(r.body) AS size
                      FROM doc_revisions r
                      JOIN docs d ON d.id = r.doc_id
                     WHERE d.project_id = %s AND d.slug = %s
                     ORDER BY r.created_at DESC LIMIT %s
                    """,
                    (project_id, slug, max(1, min(limit, 100))),
                )
                rows = cur.fetchall()
                conn.commit()
        return {"revisions": rows}
    except Exception as e:
        logger.error(f"doc_revisions failed for {project_id}/{slug}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load revisions")


@router.post("", dependencies=[Depends(verify_authorization)])
@router.post("/", dependencies=[Depends(verify_authorization)])
async def upsert_doc(payload: DocUpsert) -> dict[str, Any]:
    """Create or update a doc. The previous version is snapshotted into
    doc_revisions first, and only when the content actually changed — otherwise
    an idle save would manufacture noise history."""
    slug = _slugify(payload.slug or payload.title)
    category = payload.category if payload.category in CATEGORIES else "general"
    try:
        tags_json = json.dumps(payload.tags if payload.tags is not None else [])
    except (TypeError, ValueError):
        tags_json = "[]"

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                _ensure_table(cur)
                cur.execute(
                    "SELECT id, title, body, author FROM docs WHERE project_id = %s AND slug = %s",
                    (payload.project_id, slug),
                )
                existing = cur.fetchone()

                if existing and (existing["body"] != payload.body or existing["title"] != payload.title):
                    cur.execute(
                        "INSERT INTO doc_revisions (doc_id, title, body, author) VALUES (%s, %s, %s, %s)",
                        (existing["id"], existing["title"], existing["body"], existing.get("author") or ""),
                    )

                cur.execute(
                    """
                    INSERT INTO docs (project_id, slug, title, body, category, tags, author, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, now())
                    ON CONFLICT (project_id, slug) DO UPDATE SET
                        title      = EXCLUDED.title,
                        body       = EXCLUDED.body,
                        category   = EXCLUDED.category,
                        tags       = EXCLUDED.tags,
                        author     = EXCLUDED.author,
                        updated_at = now()
                    RETURNING id, project_id, slug, title, category, tags, author, created_at, updated_at
                    """,
                    (payload.project_id, slug, payload.title, payload.body or "",
                     category, tags_json, payload.author or ""),
                )
                row = cur.fetchone()
                conn.commit()
        return {"ok": True, "doc": row}
    except Exception as e:
        logger.error(f"upsert_doc failed for {payload.project_id}/{slug}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save doc")


@router.delete("/{slug}", dependencies=[Depends(verify_authorization)])
async def delete_doc(slug: str, project_id: str) -> dict[str, Any]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                _ensure_table(cur)
                cur.execute(
                    "DELETE FROM docs WHERE project_id = %s AND slug = %s RETURNING id",
                    (project_id, slug),
                )
                row = cur.fetchone()
                conn.commit()
        if not row:
            raise HTTPException(status_code=404, detail="Doc not found")
        return {"ok": True, "deleted": slug}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_doc failed for {project_id}/{slug}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete doc")


# Declared last: /{slug} is a catch-all and would otherwise shadow the literal
# routes above it.
@router.get("/{slug}", dependencies=[Depends(verify_authorization)])
async def get_doc(slug: str, project_id: str) -> dict[str, Any]:
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                _ensure_table(cur)
                cur.execute(
                    "SELECT id, project_id, slug, title, body, category, tags, author, "
                    "created_at, updated_at FROM docs WHERE project_id = %s AND slug = %s",
                    (project_id, slug),
                )
                row = cur.fetchone()
                conn.commit()
        if not row:
            return {"project_id": project_id, "slug": slug, "title": "", "body": "",
                    "category": "general", "tags": [], "exists": False}
        row["exists"] = True
        return row
    except Exception as e:
        logger.error(f"get_doc failed for {project_id}/{slug}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load doc")
