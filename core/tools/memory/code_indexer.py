import os
import chromadb
import re
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
ALLOWED_ROOMS = {"Archives", "Central_Logic", "Observatory", "Simulations", "Vault"}

def get_chroma_collection():
    return get_project_collection("code")

def is_relative_to_compat(path: Path, base: Path) -> bool:
    """Cross-platform Python 3.8+ compatible replacement for Path.is_relative_to."""
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False

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

def whitelist_metadata(meta: dict) -> dict:
    """Enforces a strict metadata whitelist to prevent key/parameter injection."""
    room_val = str(meta.get("room", "Archives"))
    if room_val not in ALLOWED_ROOMS:
        room_val = "Archives"
        
    return {
        "project": str(settings.PROJECT_NAME),
        "category": "code",
        "file_path": str(meta.get("file_path", "")),
        "start_line": int(meta.get("start_line", 0)),
        "end_line": int(meta.get("end_line", 0)),
        "room": room_val,
        "project_id": str(meta.get("project_id", ""))
    }

def index_project(project_path: str) -> str:
    """Scans the project, chunks the code, and indexes it into ChromaDB with production-grade security safeguards."""
    print(f"📂 Scanning Project: {project_path}")
    try:
        collection = get_chroma_collection()
    except Exception:
        # Sanitized error message to prevent information disclosure (CWE-209)
        return "ERROR: Failed to connect to secure memory indexing store."
        
    try:
        resolved_project_path = Path(project_path).resolve()
    except Exception:
        return "ERROR: Invalid project path configuration."

    if not resolved_project_path.exists():
        return "ERROR: Configured project path does not exist."
        
    project_id = get_project_id(str(resolved_project_path))
    docs_to_add = []
    metas_to_add = []
    ids_to_add = []
    
    files_processed = 0
    chunks_created = 0

    for root, dirs, files in os.walk(str(resolved_project_path)):
        if files_processed >= 2500:
            print("⚠️ Reached max files processed limit (2500). Stopping traversal.")
            break
            
        # Calculate directory depth relative to resolved_project_path
        rel_root = os.path.relpath(root, str(resolved_project_path))
        depth = 0 if rel_root == "." else len(Path(rel_root).parts)
        
        # Max directory traversal depth safeguard (max 10)
        if depth > 10:
            dirs.clear()
            continue
        elif depth == 10:
            dirs.clear()
            
        # Hardened dir traversal: Prune ignored folders and explicitly reject symlink directories to prevent loops/traversal attacks
        dirs[:] = [
            d for d in dirs 
            if d not in IGNORE_DIRS and not os.path.islink(os.path.join(root, d))
        ]
        
        for file in files:
            if files_processed >= 2500:
                break
                
            if any(file.endswith(ext) for ext in ALLOWED_EXTS):
                full_path = os.path.join(root, file)
                
                # Platform-portable strict path resolution & symlink validation
                try:
                    resolved_full_path = Path(full_path).resolve(strict=True)
                except Exception:
                    continue
                
                # Explicit symlink rejection (prevent traversal loops)
                if os.path.islink(full_path) or os.path.islink(str(resolved_full_path)):
                    continue
                
                # Strict path validation (Python 3.8+ compatible): Prevent arbitrary read outside project path
                if not is_relative_to_compat(resolved_full_path, resolved_project_path):
                    print("⚠️ Security Alert: Skipping path traversal outside project path.")
                    continue
                
                try:
                    print(f"📖 Reading: {os.path.relpath(resolved_full_path, resolved_project_path)}...")
                    # Hardened encoding: errors='replace' to avoid silent evasion while retaining system stability
                    with open(resolved_full_path, 'r', encoding='utf-8', errors='replace') as f:
                        # Atomic file-descriptor-based size validation (DoS protection)
                        stat_info = os.fstat(f.fileno())
                        if stat_info.st_size > 2 * 1024 * 1024:
                            print(f"⚠️ Skipping too large file: {resolved_full_path.name}")
                            continue
                        
                        content = f.read()
                    
                    if not content.strip():
                        continue
                        
                    rel_path = os.path.relpath(resolved_full_path, resolved_project_path)
                    chunks = chunk_code(content, rel_path)
                    
                    # Safe ceiling to prevent single-file memory exhaustion spikes
                    if len(chunks) > 500:
                        chunks = chunks[:500]
                    
                    # Secure Room Assignment: strictly couple classification to first-level system-controlled directory components
                    rel_parts = Path(rel_path).parts
                    first_component = rel_parts[0] if rel_parts else ""
                    
                    room = "Archives"
                    if first_component == "core": 
                        room = "Central_Logic"
                    elif first_component == "dashboard": 
                        room = "Observatory"
                    elif first_component == "tests" or first_component == "test": 
                        room = "Simulations"
                    elif first_component == "security": 
                        room = "Vault"
                    
                    for chunk in chunks:
                        chunk["metadata"]["room"] = room
                        chunk["metadata"]["project_id"] = project_id
                        
                        unique_id = f"{project_id}:code:{chunk['id']}"
                        
                        docs_to_add.append(chunk["document"])
                        metas_to_add.append(chunk["metadata"])
                        ids_to_add.append(unique_id)
                        chunks_created += 1
                        
                        # Incremental batch flush to prevent memory spikes (DoS mitigation)
                        if len(docs_to_add) >= 100:
                            batch_metas = [
                                whitelist_metadata(m)
                                for m in metas_to_add
                            ]
                            try:
                                collection.upsert(
                                    ids=ids_to_add,
                                    documents=docs_to_add,
                                    metadatas=batch_metas
                                )
                                print(f"✅ Incremental bulk upserted {len(docs_to_add)} chunks")
                            except Exception:
                                print("❌ Incremental bulk upsert failed.")
                            
                            # Clear arrays to prevent list copying memory bottleneck
                            docs_to_add.clear()
                            ids_to_add.clear()
                            metas_to_add.clear()
                        
                    files_processed += 1
                except Exception:
                    continue
                    
    # Flush any remaining chunks
    if docs_to_add:
        batch_metas = [
            whitelist_metadata(m)
            for m in metas_to_add
        ]
        try:
            collection.upsert(
                ids=ids_to_add,
                documents=docs_to_add,
                metadatas=batch_metas
            )
            print(f"✅ Final incremental bulk upserted {len(docs_to_add)} chunks")
        except Exception:
            print("❌ Final bulk upsert failed.")
            
    return f"SUCCESS: Indexed {files_processed} files into {chunks_created} semantic chunks."

def search_code(query: str, n_results: int = 5) -> str:
    """Searches the codebase vector embeddings for semantic matches with sanitized error handling."""
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
    except Exception:
        # Sanitized error message to prevent information disclosure (CWE-209)
        return "ERROR: Secure code search failed."
