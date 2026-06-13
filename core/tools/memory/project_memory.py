import hashlib
import logging
import time
from pathlib import Path
from core.tools.memory.chroma_db_connect import get_project_collection, upsert_embedding, query_embeddings

logger = logging.getLogger(__name__)

# Inputs too short or social to justify a memory lookup. Filtering these stops
# trivial turns ("hi", "thanks") from polluting the prompt with project memory.
_TRIVIAL_INPUTS = {
    "hi", "hey", "hello", "yo", "sup", "thanks", "thank you", "thx", "ty",
    "ok", "okay", "k", "yes", "no", "yep", "nope", "cool", "nice", "great",
    "bye", "goodbye", "gg", "lol",
}


def get_project_id(project_path: str) -> str:
    """Generates a stable 16-character project_id hash from the resolved path."""
    resolved = str(Path(project_path).resolve())
    return hashlib.sha256(resolved.encode()).hexdigest()[:16]


def _is_trivial_input(query: str) -> bool:
    """True when the input is too short/social to warrant a memory lookup."""
    q = (query or "").strip().lower()
    if len(q) < 8:
        return True
    return q.rstrip("!.?") in _TRIVIAL_INPUTS


def build_project_memory_context(
    query: str,
    project_path: str,
    limit: int = 8,
    max_chars: int = 4000,
    distance_threshold: float = 0.75,
) -> str:
    """Queries ChromaDB and builds a relevance-filtered, length-capped context of
    project memory filtered by project_id.

    Only documents whose vector distance is <= ``distance_threshold`` are kept,
    and the total injected text is hard-capped at ``max_chars`` to protect the
    model's context budget. Returns "" when nothing relevant is found or on any
    backend failure (graceful degrade — memory is an enhancement, not a
    dependency)."""
    project_id = get_project_id(project_path)
    try:
        # Search in the "concepts" collection for relevant context
        results = query_embeddings(
            query_text=query,
            n_results=limit,
            category="concepts",
            filter_project=project_id
        )

        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        # Chroma returns distances by default; fail open if the backend omits them.
        distances = (results.get("distances") or [[]])[0]

        if not docs:
            return ""

        context_parts = []
        total = 0
        for idx, (doc, meta) in enumerate(zip(docs, metadatas)):
            # Relevance gate: drop semantically distant memories. When no
            # distance is available we include the doc rather than guess.
            if idx < len(distances) and distances[idx] is not None:
                if distances[idx] > distance_threshold:
                    continue
            title = meta.get("title", "Project Memory") if isinstance(meta, dict) else "Project Memory"
            block = f"### {title}\n{doc}\n"
            # Hard cap: stop once the memory budget is exhausted.
            if total + len(block) > max_chars:
                remaining = max_chars - total
                if remaining > 0:
                    context_parts.append(block[:remaining])
                break
            context_parts.append(block)
            total += len(block)

        return "\n".join(context_parts)
    except Exception as e:
        logger.warning("[PROJECT_MEMORY] Context build failed: %s", e)
        return ""


def auto_recall_context(query: str, project_path: str) -> str:
    """Flag-gated, trivial-filtered automatic project-memory recall shared by the
    dashboard chat endpoint and the CLI engine.

    Returns a ready-to-inject context block (possibly "") so callers can prepend
    it unconditionally. Honors the KENBUN_AUTO_RECALL master switch and pulls the
    relevance/budget knobs from settings."""
    from core.tools.infrastructure.config import settings

    if not getattr(settings, "KENBUN_AUTO_RECALL", True):
        return ""
    if _is_trivial_input(query):
        return ""

    context = build_project_memory_context(
        query,
        project_path,
        max_chars=getattr(settings, "MEMORY_RECALL_MAX_CHARS", 4000),
        distance_threshold=getattr(settings, "MEMORY_RECALL_DISTANCE_THRESHOLD", 0.75),
    )
    if context:
        logger.debug("[AUTO-RECALL] Injected %d chars of project memory.", len(context))
    return context

def ingest_project_rules(project_path: str) -> str:
    """Ingests critical project rules files (HERMES.md, .cursorrules, etc.) into ChromaDB."""
    project_id = get_project_id(project_path)
    resolved_path = Path(project_path).resolve()
    
    files_to_ingest = [
        "HERMES.md", ".cursorrules", ".kenbun_rules.md", 
        "AGENTS.md", "KENBUN.md", "README.md"
    ]
    
    collection = get_project_collection("concepts")
    count = 0
    
    for filename in files_to_ingest:
        file_path = resolved_path / filename
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if not content.strip():
                    continue
                    
                stable_slug = filename.lower().replace(".", "_")
                content_hash = hashlib.sha256(content.encode()).hexdigest()
                memory_id = f"{project_id}:concepts:{stable_slug}:{content_hash[:12]}"
                
                meta = {
                    "project_id": project_id,
                    "project_path": str(resolved_path),
                    "kind": "project_rule",
                    "source": filename,
                    "title": f"Project Rule: {filename}",
                    "created_at": time.time(),
                    "updated_at": time.time()
                }
                
                upsert_embedding(
                    id=memory_id,
                    document=content,
                    metadata=meta,
                    collection_name=collection.name
                )
                count += 1
            except Exception as e:
                print(f"❌ Failed to ingest {filename}: {e}")
                
    return f"SUCCESS: Ingested {count} project rules files for project {project_id}."
