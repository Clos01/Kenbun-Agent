import time
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
from tools.memory.chroma_db_connect import get_project_collection

# Standard SRE logging configuration
logger = logging.getLogger(__name__)

# Global state for real-time swarm activity (strictly bounded to prevent memory leaks)
swarm_events: List[Dict[str, Any]] = []

def log_swarm_event(event_type: str, data: Dict[str, Any]):
    """
    Logs a swarm event for the real-time topology stream.
    Also persists DECISION-type events to ChromaDB for historical auditing.
    """
    event = {
        "timestamp": time.time(),
        "type": event_type,
        "data": data
    }
    swarm_events.append(event)
    
    # Persist to Hivemind (ChromaDB) if it's a major decision
    if event_type == "DECISION":
        try:
            collection = get_project_collection("history")
            
            # Type-safe confidence parser
            raw_confidence = data.get("confidence", 0.0)
            try:
                confidence = float(raw_confidence)
            except (ValueError, TypeError):
                confidence = 0.0
                
            # String length protection against database size limits
            logic_doc = str(data.get("logic", "Unknown Logic Pulse"))
            output_val = str(data.get("output", logic_doc))
            if len(output_val) > 10000:
                output_val = output_val[:10000] + "... [TRUNCATED FOR SIZE SAFETY]"
                
            collection.add(
                ids=[str(uuid.uuid4())],
                documents=[logic_doc],
                metadatas=[{
                    "type": "DECISION",
                    "tool": str(data.get("tool", "unknown")),
                    "confidence": confidence,
                    "result": str(data.get("result", "success")),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "output": output_val
                }]
            )
        except Exception as e:
            logger.error(f"FAILED_TO_PERSIST_DECISION: {e}", exc_info=True)

    # Bounded sliding window pruning to prevent unbounded memory growth
    if len(swarm_events) > 500:
        swarm_events.pop(0)

def get_swarm_events():
    return swarm_events
