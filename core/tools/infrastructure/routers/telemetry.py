"""
Telemetry Router
================
Handles all real-time telemetry and observability endpoints:
- SSE streams for topology events and live logs
- 2D galaxy-map projection of ChromaDB embeddings
- Build/verification status
- Sovereignty registry status
"""

import asyncio
import hashlib
import json
import logging
import math
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from tools.audit.guardrail_agent import guardrail_agent
from tools.infrastructure.config import settings
from tools.infrastructure.topology_manager import get_swarm_events
from tools.memory.honcho_connect import get_project_collection

router = APIRouter()

from tools.infrastructure.server_deps import LOG_FILE


# ──────────────────────────────────────────────
# SSE: Topology Events
# ──────────────────────────────────────────────

@router.get("/api/v1/topology/stream")
async def stream_topology():
    async def event_generator():
        last_idx = 0
        while True:
            events = get_swarm_events()
            if len(events) > last_idx:
                for i in range(last_idx, len(events)):
                    yield f"data: {json.dumps(events[i])}\n\n"
                last_idx = len(events)
            await asyncio.sleep(0.5)
    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ──────────────────────────────────────────────
# SSE: Live Logs
# ──────────────────────────────────────────────

@router.get("/api/v1/logs/stream")
async def stream_logs():
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
                                    if data.get("type") == "log" or "message" in data:
                                        msg = data.get("message", "")
                                        msg_sanitized = guardrail_agent.mask_secrets(msg)
                                        payload = {"message": msg_sanitized, "timestamp": data.get("timestamp", time.time())}
                                        yield f"data: {json.dumps(payload)}\n\n"
                                except Exception:
                                    msg_sanitized = guardrail_agent.mask_secrets(line)
                                    payload = {"message": msg_sanitized, "timestamp": time.time()}
                                    yield f"data: {json.dumps(payload)}\n\n"
                        last_size = current_size
                    except Exception as e:
                        logging.error(f"STREAM_LOG_READ_ERROR: {e}")
            await asyncio.sleep(0.5)
    return StreamingResponse(log_generator(), media_type="text/event-stream")


# ──────────────────────────────────────────────
# Galaxy Map: 2D Embedding Projection
# ──────────────────────────────────────────────

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
            limit=1500,  # Show all indexed signals as 'Real Nodes'
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

                # Infrastructure & API layer
                if "infrastructure" in path or "api_server" in path:
                    room = "Central_Logic"
                # Strategy & Intelligence
                elif "strategy" in path or "intelligence" in path or "classifier" in path:
                    room = "Central_Logic"
                # Memory & Vector DB
                elif "memory" in path or "chroma" in path or "hivemind" in path:
                    room = "Vault"
                # Security & Audit
                elif "audit" in path or "security" in path or "guardrail" in path:
                    room = "Vault"
                # Dashboard / Frontend
                elif "dashboard" in path or "component" in path or "app/" in path:
                    room = "Observatory"
                # Tests & Benchmarks
                elif "test" in path or "benchmark" in path or "simulation" in path:
                    room = "Simulations"
                # Execution & Workers
                elif "execution" in path or "worker" in path or "agent" in path:
                    room = "Simulations"
                # Scripts & DevOps
                elif "script" in path or "docker" in path or "makefile" in path.lower():
                    room = "Central_Logic"
                # Tools (general catch-all for tools/)
                elif "tools" in path:
                    room = "Central_Logic"
                # Core (general catch-all)
                elif "core" in path:
                    room = "Central_Logic"

                nodes.append({
                    "id": meta.get("id", f"node_{i}"),
                    "x": x,
                    "y": y,
                    "file": path.split("/")[-1] if path else "Anonymous Concept",
                    "room": room,
                    "snippet": doc[:100] + "..." if len(doc) > 100 else doc
                })

        if not nodes:
            # Fallback: Generate mock nodes to ensure UI remains engaging if ChromaDB is uninitialized
            for i in range(250):
                seed = i * 4
                x_raw = math.sin(seed + 1) * 10000
                x = (x_raw - math.floor(x_raw)) * 100
                y_raw = math.sin(seed + 2) * 10000
                y = (y_raw - math.floor(y_raw)) * 100
                nodes.append({
                    "id": f"mock_node_{i}",
                    "x": x,
                    "y": y,
                    "file": f"Unindexed Node {i}",
                    "room": "Archives",
                    "snippet": "Run `index_codebase` to populate real nodes."
                })

        return nodes
    except Exception as e:
        logging.error(f"Error generating topology map: {e}")
        return []


# ──────────────────────────────────────────────
# Build & Sovereignty Status
# ──────────────────────────────────────────────

@router.get("/api/v1/build/status")
async def get_build_status():
    registry_path = settings.BRAIN_HEALTH_DIR / "sovereign_registry.json"
    try:
        if registry_path.exists():
            with open(registry_path, "r") as f:
                data = json.load(f)
            return data.get("_system_pulse", {"status": "unverified"})
        return {"status": "ready", "last_build": datetime.now().isoformat()}
    except Exception:
        return {"status": "error"}


@router.get("/api/v1/sovereignty/status")
async def get_sovereignty_status():
    registry_path = settings.BRAIN_HEALTH_DIR / "sovereign_registry.json"
    try:
        if registry_path.exists():
            with open(registry_path, "r") as f:
                return json.load(f)
        return {"error": "Registry not found"}
    except Exception as e:
        return {"error": str(e)}
