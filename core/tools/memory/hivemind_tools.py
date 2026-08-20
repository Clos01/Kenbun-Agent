import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.infrastructure.config import settings
from tools.registry import sovereign_tool
from tools.utils.helpers import silence_stdout
from tools.utils.path_utils import get_project_root

logger = logging.getLogger("tools.hivemind")
PROJECT_ROOT = get_project_root()


# ============================================================
# KNOWLEDGE MANAGEMENT (Explicit Hivemind Control)
# ============================================================

@sovereign_tool()
def save_to_hivemind(title: str, content: str, tags: str, category: str = "concepts") -> str:
    """
    Use this when the user says 'Save this to the Hivemind' or wants to store a new architectural rule, pattern, or concept.

    Returns a CONCEPT_ID (e.g. kc_1a2b3c4d5e6f). Keep it: it is the only handle
    that patch_hivemind_concept and delete_from_hivemind accept. The id is
    derived from the title, so re-saving the same title addresses the same
    concept.
    """
    with silence_stdout():
        from tools.memory.knowledge_manager import learn_concept
        return learn_concept(title, content, tags, category=category)


@sovereign_tool()
def remember_preference(preference: str, context: str = "") -> str:
    """Record one of the USER's (Carlos's) preferences, decisions, or working style.

    Unlike save_to_hivemind (which models the system), this attributes the message
    to the human user peer so Honcho's deriver builds a personalized model of the
    user over time. Use it whenever the user states a preference, correction, or
    how they like things done.
    """
    with silence_stdout():
        from tools.memory.honcho_connect import USER_PEER, add_user_memory
        msg = f"{preference}" + (f"\nContext: {context}" if context else "")
        add_user_memory(msg)
        return f"✅ Recorded preference for user '{USER_PEER}'. Honcho will fold it into your personal model."


@sovereign_tool()
def search_hivemind_concepts(query: str, category: str = "concepts") -> str:
    """
    Use this to pull up past architectural rules or concepts, especially when asked to compare new ideas against old ones.
    """
    with silence_stdout():
        from tools.memory.knowledge_manager import list_concepts
        return list_concepts(query, category=category)


@sovereign_tool()
def delete_from_hivemind(concept_id: str, category: str = "concepts") -> str:
    """
    Use this to delete outdated concepts from the database when the user explicitly asks to forget them.

    concept_id must be a CONCEPT_ID returned by save_to_hivemind, or one of the
    ids in search_hivemind_concepts' "all_concept_ids". Honcho stores no
    deletable rows, so this posts a retraction instruction that the background
    dreaming process reconciles -- it is not an immediate hard delete.
    """
    with silence_stdout():
        from tools.memory.knowledge_manager import forget_concept
        return forget_concept(concept_id, category=category)


@sovereign_tool()
def patch_hivemind_concept(concept_id: str, title: str = None, content: str = None, tags: str = None) -> str:
    """Updates an existing concept in the Hivemind. Only provided fields will be updated.

    concept_id must be a CONCEPT_ID from save_to_hivemind or
    search_hivemind_concepts. As with deletion, this posts a correction that the
    dreaming process folds in rather than rewriting a stored row in place."""
    with silence_stdout():
        from tools.memory.knowledge_manager import patch_concept
        return patch_concept(concept_id, title, content, tags)


@sovereign_tool()
def ingest_knowledge_from_pdf(pdf_path: str, tech_key: str = "general") -> str:
    """
    Ingests technical knowledge from a PDF file into the Hivemind.
    Use this to 'teach' the AI new libraries (e.g. Three.js, Next.js) using official PDFs.
    """
    from tools.memory.pdf_ingestor import ingest_pdf_to_hivemind
    return ingest_pdf_to_hivemind(pdf_path, tech_key)


@sovereign_tool()
def ingest_url_to_hivemind(url: str, title: str = "", tags: str = "web,scraped") -> str:
    """Fetches a URL, extracts text, chunks it, and saves it to the Hivemind."""
    import requests
    with silence_stdout():
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            html = response.text
            html = re.sub(r'<(script|style).*?>.*?</\1>', '', html, flags=re.IGNORECASE | re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text).strip()
            
            if not text:
                return "ERROR: No text extracted from URL."
                
            from tools.memory.knowledge_manager import learn_concept
            final_title = title if title else url
            return learn_concept(final_title, text, tags)
        except Exception as e:
            return f"ERROR: Failed to ingest URL. {str(e)}"


@sovereign_tool()
def ingest_file_to_hivemind(file_path: str, tags: str = "file,ingested") -> str:
    """Reads a local file, chunks it, and saves it to the Hivemind."""
    with silence_stdout():
        try:
            path = Path(file_path).resolve()
            if not path.is_relative_to(settings.PROJECT_ROOT.resolve()):
                return "ERROR: Security Breach Blocked: Path is outside project root."
                
            if not path.exists():
                return f"ERROR: File not found: {file_path}"
                
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            from tools.memory.knowledge_manager import learn_concept
            title = os.path.basename(file_path)
            return learn_concept(title, content, tags)
        except Exception as e:
            return f"ERROR: Failed to ingest file. {str(e)}"


@sovereign_tool()
def prune_hivemind() -> str:
    """NO-OP: deletes nothing. Honcho's background 'Dreaming' process consolidates
    and merges redundant concepts on its own. Kept for callers that still invoke it.
    To remove one concept, use delete_from_hivemind(concept_id).
    """
    with silence_stdout():
        from tools.memory import knowledge_manager
        return knowledge_manager.prune_hivemind()


@sovereign_tool()
def get_intelligence_stats() -> str:
    """Returns the current Bayesian intelligence stats for all tools."""
    try:
        from tools.strategy.strategy_manager import governor
        all_stats = governor.get_all_stats()

        if not all_stats:
            if governor.use_local and governor.local_conn:
                with governor._lock:
                    cursor = governor.local_conn.cursor()
                    cursor.execute(
                        "SELECT tool_id, alpha, beta, success_count, failure_count "
                        "FROM intelligence ORDER BY success_count DESC"
                    )
                    rows = cursor.fetchall()
                if not rows:
                    return "No intelligence data collected yet."
                backend = "🗄️ Local SQLite"
                stats = [f"# 🧠 System 4: Intelligence Dashboard [{backend}]\n"]
                for tool_id, alpha, beta, s, f in rows:
                    prob = float(alpha) / (float(alpha) + float(beta))
                    stats.append(f"• **{tool_id}**: {prob:.2%} success probability ({s}S/{f}F)")
                return "\n".join(stats)
            return "No intelligence data collected yet or store disconnected."

        backend = "🐘 Remote PostgreSQL" if not governor.use_local else "🗄️ Local SQLite"
        stats = [f"# 🧠 System 4: Intelligence Dashboard [{backend}]\n"]
        stats.append("_Success probability is recency-weighted; ⌛ marks stale (decayed) evidence._\n")

        sorted_stats = sorted(all_stats, key=lambda x: x.get("success_count", 0), reverse=True)

        for entry in sorted_stats:
            tool = entry["tool_id"]
            a = float(entry.get("alpha", 2.0))
            b = float(entry.get("beta", 2.0))
            s = int(entry.get("success_count", 0))
            f = int(entry.get("failure_count", 0))
            recency = entry.get("recency")
            prob = a / (a + b)
            stale = ""
            if recency is not None and recency < 0.25:
                stale = f"  ⌛ stale (recency {recency:.2f})"
            stats.append(f"• **{tool}**: {prob:.2%} success probability ({s}S/{f}F){stale}")

        return "\n".join(stats)
    except Exception as e:
        return f"ERROR: Failed to retrieve stats. {e}"


@sovereign_tool()
def session_search(
    query: Optional[str] = None,
    session_id: Optional[str] = None,
    around_message_id: Optional[int] = None,
    window: int = 5,
    limit: int = 3,
    sort: str = "newest",
    role_filter: str = "user,assistant"
) -> str:
    """Recall past conversation contexts, resume, and search database."""
    with silence_stdout():
        from tools.sensory.session_search import (
            perform_session_search,
            render_search_results_markdown,
        )
        res = perform_session_search(
            query=query,
            session_id=session_id,
            around_message_id=around_message_id,
            window=window,
            limit=limit,
            sort=sort,
            role_filter=role_filter
        )
        return render_search_results_markdown(res)
