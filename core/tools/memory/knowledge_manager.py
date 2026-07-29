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

def learn_concept(title: str, content: str, tags: str, category: str = "concepts") -> str:
    """Saves a discrete concept into the Honcho memory layer."""
    try:
        chunks = _chunk_text_safely(content)
        
        for i, chunk in enumerate(chunks):
            meta = f"TITLE: {title}\nTAGS: {tags}\nCHUNK: {i+1}/{len(chunks)}"
            formatted_msg = f"{meta}\n\nCONTENT:\n{chunk}"
            add_memory(content=formatted_msg, category=category)
            
        return f"SUCCESS: Concept '{title}' saved to Honcho. The background dreaming process will consolidate it."
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
            formatted_results.append({
                "id": f"honcho_conclusion_{i}",
                "content": doc
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
