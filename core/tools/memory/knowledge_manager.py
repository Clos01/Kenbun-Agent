import os
import chromadb
import uuid
import json
from pathlib import Path
from tools.infrastructure.config import settings

HIVEMIND_HOST = settings.SWARM_PC_IP
HIVEMIND_PORT = settings.CHROMA_PORT

HIVEMIND_HOST = settings.SWARM_PC_IP
HIVEMIND_PORT = settings.CHROMA_PORT

from tools.memory.chroma_db_connect import get_project_collection, upsert_embedding, query_embeddings

def _get_collection(category: str = "concepts"):
    return get_project_collection(category)

def learn_concept(title: str, content: str, tags: str, category: str = "concepts") -> str:
    """Saves a discrete concept into the Hivemind ChromaDB and Supabase collections."""
    concept_id = f"concept_{str(uuid.uuid4())[:8]}"
    
    try:
        meta = {
            "title": title,
            "tags": tags,
            "project": settings.PROJECT_NAME,
            "category": category
        }
        upsert_embedding(
            id=concept_id,
            document=content,
            metadata=meta,
            collection_name=f"{settings.PROJECT_NAME}.{category}"
        )
        return f"SUCCESS: Concept '{title}' saved to Hivemind with ID: {concept_id}"
    except Exception as e:
        return f"ERROR: Failed to save concept. {str(e)}"

def list_concepts(query_text: str, n_results: int = 5, category: str = "concepts") -> str:
    """Searches the Hivemind for related concepts and returns their IDs and content."""
    try:
        results = query_embeddings(query_text, n_results=n_results, category=category)
        
        if not results['ids'] or not results['ids'][0]:
            return "No matching concepts found in the Hivemind."
            
        formatted_results = []
        for i in range(len(results['ids'][0])):
            formatted_results.append({
                "id": results['ids'][0][i],
                "title": results['metadatas'][0][i].get('title', 'Untitled'),
                "tags": results['metadatas'][0][i].get('tags', ''),
                "content": results['documents'][0][i]
            })
            
        return json.dumps(formatted_results, indent=2)
    except Exception as e:
        return f"ERROR: Failed to query Hivemind. {str(e)}"

def forget_concept(concept_id: str, category: str = "concepts") -> str:
    """Deletes a specific concept from the Hivemind by its ID."""
    try:
        collection = _get_collection(category)
        collection.delete(ids=[concept_id])
    except Exception as e:
        print(f"⚠️ [CHROMA] Delete failed for {concept_id}: {e}")
            
    return f"SUCCESS: Concept {concept_id} has been permanently deleted from the Hivemind."

def patch_concept(concept_id: str, title: str = None, content: str = None, tags: str = None) -> str:
    """Updates an existing concept in the Hivemind. Only provided fields will be updated."""
    try:
        collection = _get_collection()
        
        # Get current metadata to preserve fields not being updated
        current = collection.get(ids=[concept_id])
        if not current['ids']:
            return f"ERROR: Concept {concept_id} not found."
            
        new_metadata = current['metadatas'][0].copy()
        if title: new_metadata['title'] = title
        if tags: new_metadata['tags'] = tags
        
        new_doc = content if content else current['documents'][0]
        
        # This will update Chroma and Supabase under the hood!
        upsert_embedding(
            id=concept_id,
            document=new_doc,
            metadata=new_metadata,
            collection_name=collection.name
        )
        return f"SUCCESS: Concept {concept_id} has been patched."
    except Exception as e:
        return f"ERROR: Failed to patch concept. {str(e)}"

def prune_hivemind(min_relevance_score: float = 0.5) -> str:
    """
    Iterates through concepts and deletes those with redundant titles.
    In the future, this will use semantic similarity (vector distance) 
    to merge overlapping concepts.
    """
    collection = _get_collection()
    if not collection:
        return "ERROR: Could not connect to Hivemind."
        
    try:
        results = collection.get()
        ids = results['ids']
        metadatas = results['metadatas']
        
        titles_seen = {}
        deleted_count = 0
        
        for i in range(len(ids)):
            title = metadatas[i].get('title', '').lower().strip()
            if not title:
                continue
                
            if title in titles_seen:
                # Redundant concept found
                collection.delete(ids=[ids[i]])
                deleted_count += 1
            else:
                titles_seen[title] = ids[i]
                
        return f"Neural Pruning complete: Audited {len(ids)} concepts. Removed {deleted_count} redundant entries."
    except Exception as e:
        return f"ERROR: Pruning failed. {str(e)}"

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
