import json
import asyncio
import time
import hashlib
import math
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from core.tools.infrastructure.config import settings
from core.tools.infrastructure.topology_manager import get_assembly_events
from core.tools.audit.guardrail_agent import guardrail_agent
from core.tools.memory.chroma_db_connect import get_project_collection

router = APIRouter()

LOG_FILE = settings.PROJECT_ROOT / "brain_health" / "live_telemetry.json"

@router.get("/api/v1/topology/stream")
async def stream_topology():
    """
    Streams live assembly topology and task events to the Dashboard.
    """
    async def event_generator():
        last_idx = 0
        while True:
            events = get_assembly_events()
            if len(events) > last_idx:
                for i in range(last_idx, len(events)):
                    yield f"data: {json.dumps(events[i])}\n\n"
                last_idx = len(events)
            await asyncio.sleep(0.5)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/api/v1/logs/stream")
async def stream_logs():
    """
    Streams live assembly daemon and orchestrator logs to the Dashboard in real-time.
    """
    async def log_generator():
        last_size = 0
        if LOG_FILE.exists():
            last_size = LOG_FILE.stat().st_size
            
        while True:
            if LOG_FILE.exists():
                current_size = LOG_FILE.stat().st_size
                if current_size > last_size:
                    try:
                        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                            f.seek(last_size)
                            new_lines = f.readlines()
                            for line in new_lines:
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    data = json.loads(line)
                                    # Stream log types, or standard JSON records
                                    if data.get("type") == "log" or "message" in data:
                                        msg = data.get("message", "")
                                        msg_sanitized = guardrail_agent.mask_secrets(msg)
                                        payload = {
                                            "message": msg_sanitized,
                                            "timestamp": data.get("timestamp", time.time())
                                        }
                                        yield f"data: {json.dumps(payload)}\n\n"
                                except Exception:
                                    msg_sanitized = guardrail_agent.mask_secrets(line)
                                    payload = {
                                        "message": msg_sanitized,
                                        "timestamp": time.time()
                                    }
                                    yield f"data: {json.dumps(payload)}\n\n"
                        last_size = current_size
                    except Exception as e:
                        logging.error(f"STREAM_LOG_READ_ERROR: {e}")
            await asyncio.sleep(0.5)

    return StreamingResponse(log_generator(), media_type="text/event-stream")


@router.get("/api/v1/topology/map")
async def get_topology_map():
    """
    Projects high-dimensional neural embeddings from ChromaDB into 
    2D coordinates for the Galaxy Map.
    """
    try:
        collection = get_project_collection("code")
        
        # Fetch actual records with embeddings
        results = await run_in_threadpool(
            collection.get,
            limit=1500, # Show all indexed signals as 'Real Nodes'
            include=['embeddings', 'metadatas', 'documents']
        )
        
        nodes = []
        if results.get('metadatas') is not None and len(results['metadatas']) > 0:
            
            for i in range(len(results['metadatas'])):
                meta = results['metadatas'][i]
                doc = results['documents'][i] if results.get('documents') else ""
                
                # Check if real embeddings exist
                if results.get('embeddings') is not None and i < len(results['embeddings']) and len(results['embeddings'][i]) > 0:
                    emb = results['embeddings'][i]
                    half_len = len(emb) // 2
                    x_raw = sum(v * math.sin(idx) for idx, v in enumerate(emb[:half_len]))
                    y_raw = sum(v * math.cos(idx) for idx, v in enumerate(emb[half_len:]))
                    
                    # Normalize real embeddings organically using tanh
                    x = (math.tanh(x_raw) + 1) * 50
                    y = (math.tanh(y_raw) + 1) * 50
                else:
                    # Pseudo-embedding using hash if no real embeddings
                    h = hashlib.sha256((meta.get("file_path", "") + str(meta.get("start_line", ""))).encode('utf-8')).hexdigest()
                    x_raw = int(h[:8], 16)
                    y_raw = int(h[8:16], 16)
                    
                    # Distribute evenly across 0-100 for hashes
                    x = x_raw % 100
                    y = y_raw % 100
                
                # Semantic Zoning based on directory structure
                path = meta.get("file_path", "").lower()
                room = "Archives"  # Default fallback
                
                if "infrastructure" in path or "api_server" in path:
                    room = "Central_Logic"
                elif "strategy" in path or "intelligence" in path or "classifier" in path:
                    room = "Central_Logic"
                elif "memory" in path or "chroma" in path or "hivemind" in path:
                    room = "Vault"
                elif "audit" in path or "security" in path or "guardrail" in path:
                    room = "Vault"
                elif "dashboard" in path or "component" in path or "app/" in path:
                    room = "Observatory"
                elif "test" in path or "benchmark" in path or "simulation" in path:
                    room = "Simulations"
                elif "execution" in path or "worker" in path or "agent" in path:
                    room = "Simulations"
                elif "script" in path or "docker" in path or "makefile" in path.lower():
                    room = "Central_Logic"
                elif "tools" in path:
                    room = "Central_Logic"
                elif "core" in path:
                    room = "Central_Logic"
                
                nodes.append({
                    "id": results['ids'][i],
                    "x": x,
                    "y": y,
                    "file": path,
                    "room": room,
                    "snippet": doc[:200]
                })
        
        return nodes
    except Exception as e:
        logging.error(f"TOPOLOGY_ERROR: {e}")
        return []
