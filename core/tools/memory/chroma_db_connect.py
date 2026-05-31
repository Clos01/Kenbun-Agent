import os
import json
import hashlib
import threading
import logging
import time
import chromadb
from pathlib import Path
from tools.infrastructure.config import settings

logger = logging.getLogger(__name__)

# --- 1. CONFIGURATION ---
PROJECT_ROOT = settings.PROJECT_ROOT
PROJECT_NAME = settings.PROJECT_NAME
CHROMA_HOST = settings.CHROMA_HOST
CHROMA_PORT = settings.CHROMA_PORT

print(f"🔍 [HIVE_DEBUG] CHROMA_HOST: {CHROMA_HOST} | PORT: {CHROMA_PORT}")

# GLOBAL MEMORY: The "God Mode" rules (Default to a relative path within project)
GLOBAL_TEMPLATE_PATH = PROJECT_ROOT / "external" / "_TEMPLATE_PROJECT"

# Intelligence Filters (Skip Junk)
IGNORE_DIRS = {
    "node_modules", "venv", ".venv", ".git", ".next", "dist", "build", 
    ".idea", "__pycache__", ".agent", ".vercel", ".DS_Store", "coverage",
    "brain_health", "external"
}
ALLOWED_EXTS = {
    ".js", ".jsx", ".ts", ".tsx", ".py", 
    ".prisma", ".sql", ".md", ".css", ".json", ".html", ".txt"
}

_EMBEDDING_FUNCTION = None
_CHROMA_CLIENT = None
_CHROMA_LOCK = threading.Lock()
_IS_FALLBACK = False
_LAST_RECONNECT_ATTEMPT = 0.0
_RECONNECT_INTERVAL = 30.0  # Throttled remote check interval to prevent connection stampede

def get_embedding(text: str):
    """Generates 384-dimensional vector embedding using ChromaDB default ONNX model locally."""
    global _EMBEDDING_FUNCTION
    if _EMBEDDING_FUNCTION is None:
        from chromadb.utils import embedding_functions
        _EMBEDDING_FUNCTION = embedding_functions.DefaultEmbeddingFunction()
    return _EMBEDDING_FUNCTION([text])[0]

def query_embeddings(query_text: str, n_results: int = 5, category: str = "code", filter_project: str = None, where: dict = None):
    """
    Queries ChromaDB directly for semantic vector search with project filtering.
    """
    try:
        collection = get_project_collection(category)
        
        filters = []
        if filter_project:
            filters.append({"project_id": filter_project})
        if where:
            for k, v in where.items():
                filters.append({k: v})
                
        final_where = None
        if len(filters) == 1:
            final_where = filters[0]
        elif len(filters) > 1:
            final_where = {"$and": filters}
            
        return collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=final_where
        )
    except Exception as e:
        print(f"❌ [CHROMA] Query failed: {e}")
        return {"ids": [[]], "documents": [[]], "metadatas": [[]]}

def upsert_embedding(id: str, document: str, metadata: dict, collection_name: str = None):
    """
    Upserts a single embedding directly into ChromaDB.
    """
    category = metadata.get("category", "code")
    try:
        collection = get_project_collection(category)
        collection.upsert(
            documents=[document],
            metadatas=[metadata],
            ids=[id]
        )
        print(f"✅ [CHROMA] Upserted {id} in collection '{collection.name}'")
    except Exception as e:
        print(f"⚠️ [CHROMA] Upsert failed for {id}: {e}")

# --- 2. CONNECTION ---
def get_chroma_client():
    global _CHROMA_CLIENT, _IS_FALLBACK, _LAST_RECONNECT_ATTEMPT
    
    current_time = time.time()
    
    # 1. Fast path: check if client is already initialized, healthy, and not in fallback state
    client = _CHROMA_CLIENT
    if client is not None and not _IS_FALLBACK:
        try:
            client.heartbeat()
            return client
        except Exception:
            # Sanitized logging to prevent CWE-209 Information Disclosure
            logger.warning("⚠️ [CHROMA] Heartbeat failed. Resetting client under synchronization lock...")

    # 2. Slow path: synchronize to initialize or recreate the client thread-safely
    with _CHROMA_LOCK:
        # Double-check inside lock
        client = _CHROMA_CLIENT
        if client is not None and not _IS_FALLBACK:
            try:
                client.heartbeat()
                return client
            except Exception:
                _CHROMA_CLIENT = None

        # Throttled recovery check: if we are in fallback, verify if reconnect interval has elapsed
        if _IS_FALLBACK and (current_time - _LAST_RECONNECT_ATTEMPT) < _RECONNECT_INTERVAL:
            if client is not None:
                try:
                    client.heartbeat()
                    return client
                except Exception:
                    pass

        # Try to connect/reconnect to the primary remote Hivemind database
        _LAST_RECONNECT_ATTEMPT = current_time
        try:
            # Fast socket ping with context manager (CWE-404 compliance)
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1.5)
                result = sock.connect_ex((CHROMA_HOST, int(CHROMA_PORT)))
            
            if result != 0:
                raise ConnectionError("ChromaDB port is unreachable.")
    
            logger.info("📡 Sovereign Link: Connecting to Hivemind...")
            from chromadb.config import Settings
            remote_client = chromadb.HttpClient(
                host=CHROMA_HOST, 
                port=CHROMA_PORT,
                settings=Settings(
                    chroma_api_impl="chromadb.api.fastapi.FastAPI",
                    allow_reset=False  # Secure: Disable remote database resets (CWE-276 compliance)
                )
            )
            # Verify remote client is healthy
            remote_client.heartbeat()
            
            if _IS_FALLBACK:
                logger.info("✅ [CHROMA] Successfully recovered remote Hivemind connection. Upgrading from local backup.")
                
            _CHROMA_CLIENT = remote_client
            _IS_FALLBACK = False
            return _CHROMA_CLIENT
        except Exception:
            # Fallback block (CWE-209 compliance: sanitized logging)
            if not _IS_FALLBACK or _CHROMA_CLIENT is None:
                logger.error("❌ [HIVE_CRITICAL] Hivemind is offline or unreachable. Initializing local fallback...")
                db_path = str(settings.BRAIN_HEALTH_DIR / "chromadb_local")
                logger.warning(f"⚠️ Falling back to Local Archive: {db_path}")
                _CHROMA_CLIENT = chromadb.PersistentClient(path=db_path)
                _IS_FALLBACK = True
            return _CHROMA_CLIENT

def get_project_collection(category: str):
    """
    Returns a namespaced collection for the current project.
    Categories: 'code', 'concepts', 'history', 'global'
    """
    client = get_chroma_client()
    if not client: return None
    
    if category == "global":
        name = "global.brain"
    else:
        name = f"{PROJECT_NAME}.{category}"
        
    return client.get_or_create_collection(
        name=name,
        metadata={"project": PROJECT_NAME, "category": category}
    )

def get_file_hash(content):
    return hashlib.md5(content.encode('utf-8')).hexdigest()

import re
import ast

def _chunk_python_semantically(content: str, file_path: str):
    """Uses AST to split Python code into logical functions and classes."""
    chunks = []
    try:
        tree = ast.parse(content)
        lines = content.split('\n')
        
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start_line = node.lineno
                end_line = getattr(node, 'end_lineno', len(lines))
                chunk_body = "\n".join(lines[start_line-1:end_line])
                
                chunks.append({
                    "id": f"CHILD:{file_path}:{start_line}",
                    "document": chunk_body,
                    "metadata": {
                        "type": "CHILD", 
                        "file_path": file_path, 
                        "start_line": start_line, 
                        "name": node.name,
                        "parent_id": f"PARENT:{file_path}"
                    }
                })
        return chunks
    except Exception as e:
        print(f"⚠️ AST Parse failed for {file_path}: {e}. Falling back to line-based chunking.")
        return []

def chunk_code_semantically(content: str, file_path: str):
    """Splits code into logical blocks (Child Chunks) and keeps full file as context (Parent)."""
    chunks = []
    
    # Add Parent Doc (Full File)
    chunks.append({
        "id": f"PARENT:{file_path}",
        "document": content[:25000],
        "metadata": {"type": "PARENT", "file_path": file_path}
    })

    # Language-specific chunking
    if file_path.endswith(".py"):
        py_chunks = _chunk_python_semantically(content, file_path)
        if py_chunks:
            chunks.extend(py_chunks)
            return chunks

    # Fallback/JS/TS line-based chunking
    lines = content.split('\n')
    boundary_pattern = re.compile(r'^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:class|def|function|const\s+\w+\s*=\s*(?:async\s*)?\()')
    
    current_chunk = []
    start_line = 1
    
    for i, line in enumerate(lines):
        line_num = i + 1
        if boundary_pattern.match(line) and current_chunk:
            if len(current_chunk) > 3:
                chunks.append({
                    "id": f"CHILD:{file_path}:{start_line}",
                    "document": "\n".join(current_chunk),
                    "metadata": {"type": "CHILD", "file_path": file_path, "start_line": start_line, "parent_id": f"PARENT:{file_path}"}
                })
            current_chunk = []
            start_line = line_num
        current_chunk.append(line)
        if len(current_chunk) > 150:
            chunks.append({
                "id": f"CHILD:{file_path}:{start_line}",
                "document": "\n".join(current_chunk),
                "metadata": {"type": "CHILD", "file_path": file_path, "start_line": start_line, "parent_id": f"PARENT:{file_path}"}
            })
            current_chunk = []
            start_line = line_num + 1

    if current_chunk:
        chunks.append({
            "id": f"CHILD:{file_path}:{start_line}",
            "document": "\n".join(current_chunk),
            "metadata": {"type": "CHILD", "file_path": file_path, "start_line": start_line, "parent_id": f"PARENT:{file_path}"}
        })
    return chunks

def scan_directory(path, prefix="LOCAL"):
    """Scans and returns documents with hierarchical Parent-Child metadata."""
    all_chunks = []
    path_obj = Path(path)
    if not path_obj.exists():
        print(f"⚠️ Warning: Path not found: {path}")
        return []

    print(f"📂 Scanning ({prefix}): {path}")
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in ALLOWED_EXTS:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, path)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if content.strip():
                        all_chunks.extend(chunk_code_semantically(content, f"{prefix}:{rel_path}"))
                except Exception as e:
                    print(f"Error reading {file}: {e}")
    return all_chunks

# --- 4. SYNC LOGIC ---
def sync_all(client):
    collection = get_project_collection("code")
    data = scan_directory(PROJECT_ROOT, prefix=f"PROJECT:{PROJECT_NAME}") + scan_directory(GLOBAL_TEMPLATE_PATH, prefix="GLOBAL")
    
    if not data:
        print("⚠️ No documents found.")
        return

    print(f"⬆️  Upserting {len(data)} hierarchical chunks to ChromaDB...")
    for c in data:
        meta = {**c["metadata"], "project": PROJECT_NAME, "category": "code"}
        upsert_embedding(c["id"], c["document"], meta, collection.name)
    print(f"✅ System 3 Sync Complete. Namespaced brain initialized.")

if __name__ == "__main__":
    client = get_chroma_client()
    if client:
        sync_all(client)