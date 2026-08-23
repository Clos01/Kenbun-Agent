import json
import logging
from typing import Dict, Any

from tools.registry import sovereign_tool
from tools.memory.code_indexer import search_code
from tools.memory.honcho_connect import query_embeddings, retrieve_memory

logger = logging.getLogger("tools.reflexion")

@sovereign_tool()
def autonomous_reflexion(query: str, project_path: str = None) -> str:
    """
    Mandatory RAG + Reflexion pre-flight check.
    Queries the codebase and past mistakes/fixes from Honcho to provide logic context.
    """
    
    
    # 1. Pull Code Context (Chroma)
    try:
        code_context = search_code(query)
    except Exception as e:
        logger.warning(f"Failed to pull code context: {e}")
        code_context = "No code context retrieved."
        
    # 2. Pull Past Mistakes (Honcho - concepts / fixes)
    try:
        # Pull from 'fixes' or 'concepts'
        mistakes = query_embeddings(query, n_results=3, category="fixes", filter_project=project_path)
        if not mistakes or len(mistakes) == 0:
            mistakes = retrieve_memory(query, n_results=3, category="fixes")
    except Exception as e:
        logger.warning(f"Failed to pull Honcho fixes: {e}")
        mistakes = []
        
    
    # Calculate counts for dynamic logging
    mistake_count = len(mistakes) if mistakes else 0
    ref_count = 3 if code_context and "No code context" not in code_context else 0  # search_code returns a synthesized string, typically from top 3 matches
    
    logger.info(f"🧠 Retrieving {ref_count} project references and {mistake_count} past mistakes from Hivemind/Honcho...")
    print(f"\n\033[95m🧠 Autonomous Reflexion:\033[0m Retrieved {ref_count} references and {mistake_count} past mistakes.")

    # 3. Format strictly for SLMs
    payload = {
        "query": query,
        "past_mistakes_to_avoid": mistakes if mistakes else ["No relevant past mistakes found."],
        "code_context": code_context
    }
    
    # Return as JSON string so SLM parses it natively
    return json.dumps(payload, indent=2)
