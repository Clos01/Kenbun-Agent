import hashlib
import time
from pathlib import Path
from tools.memory.honcho_connect import add_memory, retrieve_memory

def get_project_id(project_path: str) -> str:
    """Generates a stable 16-character project_id hash from the resolved path."""
    resolved = str(Path(project_path).resolve())
    return hashlib.sha256(resolved.encode()).hexdigest()[:16]

def build_project_memory_context(query: str, project_path: str, limit: int = 8) -> str:
    """Queries Honcho and builds a capped context of project memory."""
    try:
        results = retrieve_memory(query_text=query, n_results=limit, category="concepts")
        
        if not results:
            return ""
            
        context_parts = []
        for doc in results:
            context_parts.append(f"- {doc}\n")
            
        return "\n".join(context_parts)
    except Exception as e:
        print(f"⚠️ [PROJECT_MEMORY] Context build failed: {e}")
        return ""

def ingest_project_rules(project_path: str) -> str:
    """Ingests critical project rules files into Honcho."""
    resolved_path = Path(project_path).resolve()
    
    files_to_ingest = [
        "HERMES.md", ".cursorrules", ".kenbun_rules.md", 
        "AGENTS.md", "KENBUN.md", "README.md"
    ]
    
    count = 0
    
    for filename in files_to_ingest:
        file_path = resolved_path / filename
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if not content.strip():
                    continue
                
                # Send the document to Honcho as a message
                formatted_message = f"DOCUMENT TITLE: Project Rule - {filename}\n\nCONTENT:\n{content}"
                add_memory(content=formatted_message, category="concepts")
                count += 1
            except Exception as e:
                print(f"❌ Failed to ingest {filename}: {e}")
                
    return f"SUCCESS: Ingested {count} project rules files into Honcho."
