import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any
from tools.memory.honcho_connect import upsert_embedding

import collections

# Standard SRE logging configuration
logger = logging.getLogger(__name__)

# Global state for real-time swarm activity (strictly bounded to prevent memory leaks)
swarm_events: collections.deque = collections.deque(maxlen=500)

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
            logic_doc = str(data.get("logic", data.get("output", "No reasoning provided.")))
            confidence = float(data.get("confidence", 1.0))
            output_val = str(data.get("output", "No output provided."))
            upsert_embedding(
                id=str(uuid.uuid4()),
                document=logic_doc,
                metadata={
                    "category": "history",
                    "type": "DECISION",
                    "tool": str(data.get("tool", "unknown")),
                    "confidence": confidence,
                    "result": str(data.get("result", "success")),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "output": output_val
                }
            )
        except Exception as e:
            logger.error(f"FAILED_TO_PERSIST_DECISION: {e}", exc_info=True)

    # Bounded sliding window pruning is handled automatically by deque maxlen

def get_swarm_events():
    return list(swarm_events)
