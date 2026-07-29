import hashlib
import re
import uuid
import json
from tools.infrastructure.config import settings

HIVEMIND_HOST = settings.SWARM_PC_IP
HIVEMIND_PORT = settings.CHROMA_PORT

HIVEMIND_HOST = settings.SWARM_PC_IP
HIVEMIND_PORT = settings.CHROMA_PORT

from tools.memory.honcho_connect import add_memory, retrieve_memory

def _chunk_text_safely(text: str, max_chars: int = 3000, overlap: int = 300) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end >= len(text):
            chunks.append(text[start:])
            break
            
        # Try to find a paragraph break or newline to snap to
        snap_pos = text.rfind('\n\n', start, end)
        if snap_pos == -1 or snap_pos <= start + (max_chars // 2):
            snap_pos = text.rfind('\n', start, end)
            
        if snap_pos != -1 and snap_pos > start + (max_chars // 2):
            end = snap_pos
        else:
            # Fallback to space
            snap_pos = text.rfind(' ', start, end)
            if snap_pos != -1 and snap_pos > start + (max_chars // 2):
                end = snap_pos
                
        chunks.append(text[start:end].strip())
        start = end - overlap
        
    return chunks

def concept_id_for(title: str) -> str:
    """Stable handle for a concept, derived from its title.

    Honcho has no per-document primary key: retrieve_memory returns a single
    synthesized representation, not the stored messages, so there is nothing to
    hand back that the storage layer would recognise later. Instead we mint a
    deterministic id from the title and WRITE IT INTO the message body, so the
    token survives into the representation and the forget/patch instructions
    that reference it are actually about something the memory layer has seen.

    Deriving from the title (not the content) keeps the id stable when a concept
    is re-saved with edited text, so it addresses the same logical concept.
    """
    digest = hashlib.sha1(title.strip().lower().encode("utf-8")).hexdigest()[:12]
    return f"kc_{digest}"


def learn_concept(title: str, content: str, tags: str, category: str = "concepts") -> str:
    """Saves a discrete concept into the Honcho memory layer.

    Returns the concept id, which is required by patch_concept/forget_concept.
    """
    try:
        chunks = _chunk_text_safely(content)
        concept_id = concept_id_for(title)

        for i, chunk in enumerate(chunks):
            meta = (f"CONCEPT_ID: {concept_id}\nTITLE: {title}\n"
                    f"TAGS: {tags}\nCHUNK: {i+1}/{len(chunks)}")
            formatted_msg = f"{meta}\n\nCONTENT:\n{chunk}"
            add_memory(content=formatted_msg, category=category)

        return (
            f"SUCCESS: Concept '{title}' saved to Honcho.\n"
            f"CONCEPT_ID: {concept_id}\n"
            "Pass that id to patch_hivemind_concept or delete_from_hivemind to "
            "amend or retract this concept. The background dreaming process will "
            "consolidate it."
        )
    except Exception as e:
        return f"ERROR: Failed to save concept. {str(e)}"

def list_concepts(query_text: str, n_results: int = 5, category: str = "concepts") -> str:
    """Searches Honcho for related concepts."""
    try:
        results = retrieve_memory(query_text, n_results=n_results, category=category)
        
        if not results:
            return "No matching concepts found in Honcho's representation."
            
        formatted_results = []
        for i, doc in enumerate(results):
            # Prefer the real CONCEPT_ID written in at save time. The positional
            # "honcho_conclusion_{i}" fallback is not an identifier -- it is the
            # index of this result in this query, so it names a different concept
            # on the next search and is useless for patch/forget. Label it as such
            # rather than passing it off as an id.
            found = re.findall(r"CONCEPT_ID:\s*(kc_[0-9a-f]+)", str(doc))
            formatted_results.append({
                "id": found[0] if found else None,
                "all_concept_ids": sorted(set(found)),
                "addressable": bool(found),
                "position": f"result_{i}",
                "content": doc,
            })

        return json.dumps(formatted_results, indent=2)
    except Exception as e:
        return f"ERROR: Failed to query Honcho. {str(e)}"

def forget_concept(concept_id: str, category: str = "concepts") -> str:
    """In Honcho, you issue an instruction to forget or discard a concept."""
    add_memory(f"INSTRUCTION: Please disregard and forget the prior conclusion or concept related to {concept_id}.", category=category)
    return f"SUCCESS: Instructed Honcho to forget {concept_id}. The dreaming process will reconcile this."

def patch_concept(concept_id: str, title: str = None, content: str = None, tags: str = None) -> str:
    """Updates an existing concept in Honcho by issuing a correction message."""
    patch_msg = f"INSTRUCTION: Update the concept related to {concept_id}.\n"
    if title: patch_msg += f"New Title: {title}\n"
    if tags: patch_msg += f"New Tags: {tags}\n"
    if content: patch_msg += f"New Content:\n{content}\n"
    
    add_memory(patch_msg, category="concepts")
    return f"SUCCESS: Correction for {concept_id} sent to Honcho."

def prune_hivemind(min_relevance_score: float = 0.5) -> str:
    """
    NO-OP. Deletes nothing.

    Honcho performs autonomous consolidation ('Dreaming') in the background to
    deduplicate and merge concepts, so there is nothing for this to do. It is
    kept only so existing callers do not break. min_relevance_score is ignored.

    The name and the old docstring both claimed this removed concepts, which
    meant an agent could "prune" the store, get a success string, and believe
    stale knowledge had been cleared when nothing had happened.
    """
    return (
        "NO-OP: prune_hivemind deletes nothing. Consolidation is handled "
        "autonomously by Honcho's background 'Dreaming' process, which merges "
        "redundant concepts on its own. To remove a specific concept, use "
        "delete_from_hivemind(concept_id)."
    )

def record_post_mortem(task: str, error: str, solution: str, tags: str = "auto-lesson"):
    """Distills a task completion into a permanent lesson in the Hivemind."""
    title = f"Lesson: {task[:50]}..."
    content = f"TASK: {task}\nERROR: {error}\nSOLUTION: {solution}"
    return learn_concept(title, content, f"post-mortem,{tags}", category="history")

def log_architectural_decision(decision: str, rationale: str, component: str):
    """Records an architectural decision to prevent future regressions."""
    title = f"Decision: {component}"
    content = f"DECISION: {decision}\nRATIONALE: {rationale}\nCOMPONENT: {component}"
    return learn_concept(title, content, "architecture,decision", category="concepts")
