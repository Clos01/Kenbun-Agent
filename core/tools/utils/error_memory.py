"""
Error Memory — Semantic error→fix recall using ChromaDB.

"The AI never makes the same mistake twice."

When a bug is fixed, store the error message + solution.
When a similar error appears later, recall the past fix
and inject it as a hint into the AI prompt.

Uses ChromaDB (already running in Docker) with semantic search —
so "NoneType has no attribute 'get'" matches "AttributeError on None object".
"""
from datetime import datetime


# --- CONFIGURATION ---
COLLECTION_NAME = "error_solutions"
MAX_RECALL_RESULTS = 3


from tools.memory.chroma_db_connect import get_project_collection

def _get_collection(chroma_database_server_host_ip_address: str, chroma_database_server_connection_port: str):
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
    """
    runtime_error_stack_trace_message = error_message
    developer_resolution_or_code_diff = solution
    offending_file_context_path = file_context
    chroma_database_server_host_ip_address = pc_ip
    chroma_database_server_connection_port = chroma_port

    if not runtime_error_stack_trace_message or not developer_resolution_or_code_diff:
        return "❌ Both error_message and solution are required."

    try:
        chroma_vector_collection_instance = _get_collection(chroma_database_server_host_ip_address, chroma_database_server_connection_port)

        import hashlib
        import time
        current_iso_formatted_incident_timestamp = datetime.now().isoformat()
        
        # Build a robust unique ID with content hash and nanoseconds
        sha256_checksum_hash_of_error_message = hashlib.sha256(runtime_error_stack_trace_message.encode()).hexdigest()[:12]
        unique_semantic_memory_document_id = f"fix_{int(time.time())}_{sha256_checksum_hash_of_error_message}"

        # The document text is what gets embedded for search
        raw_text_embedding_document = f"ERROR: {runtime_error_stack_trace_message}\nSOLUTION: {developer_resolution_or_code_diff}"

        associated_memory_metadata_dictionary = {
            "error_message": runtime_error_stack_trace_message[:500],  # Truncate for metadata
            "solution": developer_resolution_or_code_diff[:2000],
            "file_context": offending_file_context_path[:500] if offending_file_context_path else "",
            "timestamp": current_iso_formatted_incident_timestamp,
            "type": "error_fix",
        }

        chroma_vector_collection_instance.upsert(
            documents=[raw_text_embedding_document],
            metadatas=[associated_memory_metadata_dictionary],
            ids=[unique_semantic_memory_document_id],
        )

        total_stored_memories_count = chroma_vector_collection_instance.count()

        return (
            f"## 🧠 Error Fix Saved\n\n"
            f"**ID:** `{unique_semantic_memory_document_id}`\n"
            f"**Error:** {runtime_error_stack_trace_message[:100]}...\n"
            f"**Solution:** {developer_resolution_or_code_diff[:100]}...\n"
            f"**Total memories:** {total_stored_memories_count}\n\n"
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
    """
    runtime_error_stack_trace_message = error_message
    chroma_database_server_host_ip_address = pc_ip
    chroma_database_server_connection_port = chroma_port
    maximum_number_of_recall_results_requested = n_results

    if not runtime_error_stack_trace_message:
        return "❌ Error message is required."

    try:
        chroma_vector_collection_instance = _get_collection(chroma_database_server_host_ip_address, chroma_database_server_connection_port)

        if chroma_vector_collection_instance.count() == 0:
            return (
                "## 🧠 Error Memory\n\n"
                "No past fixes stored yet. Use `remember_fix()` to start building the knowledge base."
            )

        semantic_query_results_dictionary = chroma_vector_collection_instance.query(
            query_texts=[runtime_error_stack_trace_message],
            n_results=min(maximum_number_of_recall_results_requested, chroma_vector_collection_instance.count()),
            where={"type": "error_fix"}
        )

        if not semantic_query_results_dictionary["documents"] or not semantic_query_results_dictionary["documents"][0]:
            return "## 🧠 Error Memory\n\nNo similar errors found in the knowledge base."

        # Format results
        formatted_past_fixes_report_builder_list = [f"## 🧠 Error Memory — {len(semantic_query_results_dictionary['documents'][0])} Similar Fixes Found\n"]

        for loop_index_counter, (past_memory_text_document, past_memory_metadata_dictionary, vector_space_semantic_distance_metric) in enumerate(zip(
            semantic_query_results_dictionary["documents"][0],
            semantic_query_results_dictionary["metadatas"][0],
            semantic_query_results_dictionary["distances"][0],
        )):
            calculated_matching_confidence_percentage = max(0, round((1 - vector_space_semantic_distance_metric / 2) * 100))  # Rough confidence %
            past_incident_iso_timestamp = past_memory_metadata_dictionary.get("timestamp", "unknown")
            past_offending_file_context = past_memory_metadata_dictionary.get("file_context", "")

            formatted_past_fixes_report_builder_list.append(
                f"### Fix #{loop_index_counter+1} (Confidence: {calculated_matching_confidence_percentage}%)\n"
                f"**When:** {past_incident_iso_timestamp}\n"
                f"{'**File:** ' + past_offending_file_context + chr(10) if past_offending_file_context else ''}"
                f"**Past Error:** {past_memory_metadata_dictionary.get('error_message', 'N/A')}\n"
                f"**Solution:** {past_memory_metadata_dictionary.get('solution', 'N/A')}\n"
            )

        return "\n".join(formatted_past_fixes_report_builder_list)

    except Exception as e:
        return f"❌ Error memory recall failed: {e}"
