import os
import chromadb
from pathlib import Path
from tools.infrastructure.config import settings

from tools.memory.chroma_db_connect import CHROMA_HOST, CHROMA_PORT, get_project_collection, upsert_embedding, query_embeddings
from tools.memory.project_memory import get_project_id

IGNORE_DIRS = {
    "node_modules", "venv", ".venv", ".git", ".next", "dist", "build", 
    ".idea", "__pycache__", ".agent", ".vercel", ".DS_Store", "public", "coverage",
    "benchmarks", "tests", "external", "design_systems", "dev", "training_data", ".pytest_cache", "brain_health", "skills"
}
ALLOWED_EXTS = {".js", ".jsx", ".ts", ".tsx", ".py", ".md", ".json"}

def get_chroma_collection():
    return get_project_collection("code")

import re

def chunk_code(content: str, file_path: str) -> list:
    """Smarter heuristic chunker using Regex boundaries."""
    lines = content.split('\n')
    chunks = []
    
    boundary_pattern = re.compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:class|def|function|const\s+\w+\s*=\s*(?:async\s*)?\()')
    
    current_chunk_lines = []
    start_line = 1
    MAX_CHUNK_LINES = 150
    
    for i, line in enumerate(lines):
        line_num = i + 1
        is_boundary = boundary_pattern.match(line)
        is_too_big = len(current_chunk_lines) >= MAX_CHUNK_LINES
        
        if (is_boundary or is_too_big) and current_chunk_lines:
            if len(current_chunk_lines) > 5 or is_too_big:
                chunk_text = '\n'.join(current_chunk_lines)
                chunks.append({
                    "id": f"{file_path}:{start_line}-{line_num - 1}",
                    "document": chunk_text,
                    "metadata": {
                        "file_path": file_path,
                        "start_line": start_line,
                        "end_line": line_num - 1,
                        "room": "General" # Default
                    }
                })
                current_chunk_lines = []
                start_line = line_num
        current_chunk_lines.append(line)
            
    if current_chunk_lines:
        chunk_text = '\n'.join(current_chunk_lines)
        chunks.append({
            "id": f"{file_path}:{start_line}-{len(lines)}",
            "document": chunk_text,
            "metadata": {
                "file_path": file_path,
                "start_line": start_line,
                "end_line": len(lines),
                "room": "General"
            }
        })
    return chunks

def index_project(project_path: str) -> str:
    """Scans the project, chunks the code, and indexes it into ChromaDB."""
    print(f"📂 Scanning Project: {project_path}")
    try:
        collection = get_chroma_collection()
    except Exception as e:
        return f"ERROR: Failed to connect to ChromaDB. {e}"
        
    project_id = get_project_id(project_path)
    docs_to_add = []
    metas_to_add = []
    ids_to_add = []
    
    files_processed = 0
    chunks_created = 0

    if not os.path.exists(project_path):
        return f"ERROR: Project path '{project_path}' does not exist."

    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            if any(file.endswith(ext) for ext in ALLOWED_EXTS):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, project_path)
                
                try:
                    print(f"📖 Reading: {rel_path}...")
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    if not content.strip():
                        continue
                        
                    chunks = chunk_code(content, rel_path)
                    
                    # Room Assignment based on path
                    room = "Archives"
                    if "core" in rel_path: room = "Central_Logic"
                    if "dashboard" in rel_path: room = "Observatory"
                    if "test" in rel_path: room = "Simulations"
                    if "security" in rel_path: room = "Vault"
                    
                    for chunk in chunks:
                        chunk["metadata"]["room"] = room
                        chunk["metadata"]["project_id"] = project_id
                        chunk["metadata"]["project_path"] = str(Path(project_path).resolve())
                        
                        unique_id = f"{project_id}:code:{chunk['id']}"
                        
                        docs_to_add.append(chunk["document"])
                        metas_to_add.append(chunk["metadata"])
                        ids_to_add.append(unique_id)
                        chunks_created += 1
                        
                    files_processed += 1
                except Exception as e:
                    print(f"❌ Error processing {file}: {e}")
                    
    if docs_to_add:
        print(f"⬆️  Found {chunks_created} semantic chunks. Starting upload...")
        for j in range(len(docs_to_add)):
            try:
                meta = {**metas_to_add[j], "project": settings.PROJECT_NAME, "category": "code"}
                upsert_embedding(
                    id=ids_to_add[j],
                    document=docs_to_add[j],
                    metadata=meta,
                    collection_name=collection.name
                )
            except Exception as e:
                print(f"❌ Upload failed for chunk {ids_to_add[j]}: {e}")
            
    return f"SUCCESS: Indexed {files_processed} files into {chunks_created} semantic chunks."

def search_code(query: str, n_results: int = 5) -> str:
    """Searches the codebase vector embeddings for semantic matches."""
    try:
        results = query_embeddings(query, n_results=n_results, category="code")
        if not results['documents'] or not results['documents'][0]:
            return "No matching code found."
            
        output = [f"## 🔍 Search: '{query}'\n"]
        for i, doc in enumerate(results['documents'][0]):
            meta = results['metadatas'][0][i]
            output.append(f"### MATCH {i+1}: `{meta.get('file_path')}` | Room: {meta.get('room')}")
            output.append(f"```\n{doc}\n```\n")
        return "\n".join(output)
    except Exception as e:
        return f"ERROR searching code: {e}"
