import os
import hashlib
import time
from pathlib import Path
from tools.infrastructure.config import settings
from tools.memory.chroma_db_connect import get_project_collection, upsert_embedding, query_embeddings

def get_project_id(project_path: str) -> str:
    """Generates a stable 16-character project_id hash from the resolved path."""
    resolved = str(Path(project_path).resolve())
    return hashlib.sha256(resolved.encode()).hexdigest()[:16]

def build_project_memory_context(query: str, project_path: str, limit: int = 8) -> str:
    """Queries ChromaDB and builds a capped context of project memory filtered by project_id."""
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
        
        if not docs:
            return ""
            
        context_parts = []
        for doc, meta in zip(docs, metadatas):
            context_parts.append(f"### {meta.get('title', 'Project Memory')}\n{doc}\n")
            
        return "\n".join(context_parts)
    except Exception as e:
        print(f"⚠️ [PROJECT_MEMORY] Context build failed: {e}")
        return ""

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
                content_hash = hashlib.md5(content.encode()).hexdigest()
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
