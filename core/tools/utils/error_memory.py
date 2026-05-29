"""
Error Memory — Semantic error→fix recall using ChromaDB.

"The AI never makes the same mistake twice."

When a bug is fixed, store the error message + solution.
When a similar error appears later, recall the past fix
and inject it as a hint into the AI prompt.

Uses ChromaDB (already running in Docker) with semantic search —
so "NoneType has no attribute 'get'" matches "AttributeError on None object".
"""
import os
import json
import chromadb
from datetime import datetime


# --- CONFIGURATION ---
COLLECTION_NAME = "error_solutions"
MAX_RECALL_RESULTS = 3


from tools.memory.chroma_db_connect import get_project_collection

def _get_collection(pc_ip: str, chroma_port: str):
    """Connect to ChromaDB and get/create the namespaced history collection."""
    return get_project_collection("history")


def remember_fix(
    error_message: str,
    solution: str,
    file_context: str = "",
    pc_ip: str = "",
    chroma_port: str = "8000",
) -> str:
    """
    Save an error→fix mapping to the knowledge base.

    The error message is embedded as a vector so future similar errors
    can be found via semantic search (not exact match).

    Args:
        error_message: The error/exception/stack trace
        solution: How you fixed it (description or code diff)
        file_context: Optional — which file/function it occurred in
        pc_ip: ChromaDB host IP
        chroma_port: ChromaDB port
    """
    if not error_message or not solution:
        return "❌ Both error_message and solution are required."

    try:
        collection = _get_collection(pc_ip, chroma_port)

        import hashlib
        import time
        timestamp = datetime.now().isoformat()
        
        # Build a robust unique ID with content hash and nanoseconds
        content_hash = hashlib.md5(error_message.encode()).hexdigest()[:12]
        doc_id = f"fix_{int(time.time())}_{content_hash}"

        # The document text is what gets embedded for search
        document = f"ERROR: {error_message}\nSOLUTION: {solution}"

        metadata = {
            "error_message": error_message[:500],  # Truncate for metadata
            "solution": solution[:2000],
            "file_context": file_context[:500] if file_context else "",
            "timestamp": timestamp,
            "type": "error_fix",
        }

        collection.upsert(
            documents=[document],
            metadatas=[metadata],
            ids=[doc_id],
        )

        count = collection.count()

        return (
            f"## 🧠 Error Fix Saved\n\n"
            f"**ID:** `{doc_id}`\n"
            f"**Error:** {error_message[:100]}...\n"
            f"**Solution:** {solution[:100]}...\n"
            f"**Total memories:** {count}\n\n"
            f"This fix will be recalled automatically when a similar error occurs."
        )

    except Exception as e:
        return f"❌ Failed to save error fix: {e}"


def recall_fix(
    error_message: str,
    pc_ip: str = "",
    chroma_port: str = "8000",
    n_results: int = MAX_RECALL_RESULTS,
) -> str:
    """
    Search for similar past errors and their solutions.

    Uses semantic search, so the error doesn't need to match exactly.
    "KeyError: 'user_id'" will match past fixes for "KeyError accessing user data".

    Args:
        error_message: The current error/exception you're facing
        pc_ip: ChromaDB host IP
        chroma_port: ChromaDB port
        n_results: Maximum number of past fixes to return
    """
    if not error_message:
        return "❌ Error message is required."

    try:
        collection = _get_collection(pc_ip, chroma_port)

        if collection.count() == 0:
            return (
                "## 🧠 Error Memory\n\n"
                "No past fixes stored yet. Use `remember_fix()` to start building the knowledge base."
            )

        results = collection.query(
            query_texts=[error_message],
            n_results=min(n_results, collection.count()),
            where={"type": "error_fix"}
        )

        if not results["documents"] or not results["documents"][0]:
            return "## 🧠 Error Memory\n\nNo similar errors found in the knowledge base."

        # Format results
        output = [f"## 🧠 Error Memory — {len(results['documents'][0])} Similar Fixes Found\n"]

        for i, (doc, meta, distance) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )):
            confidence = max(0, round((1 - distance / 2) * 100))  # Rough confidence %
            timestamp = meta.get("timestamp", "unknown")
            file_ctx = meta.get("file_context", "")

            output.append(
                f"### Fix #{i+1} (Confidence: {confidence}%)\n"
                f"**When:** {timestamp}\n"
                f"{'**File:** ' + file_ctx + chr(10) if file_ctx else ''}"
                f"**Past Error:** {meta.get('error_message', 'N/A')}\n"
                f"**Solution:** {meta.get('solution', 'N/A')}\n"
            )

        return "\n".join(output)

    except Exception as e:
        return f"❌ Error memory recall failed: {e}"
