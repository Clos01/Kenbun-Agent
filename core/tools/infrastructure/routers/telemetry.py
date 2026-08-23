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

        # Fetch actual records with embeddings. Was capped at 1500, which made the
        # dashboard report a fake "1,500 Indexed Nodes" when the real code collection
        # holds far more (~6k). Use the true collection size so the galaxy shows every
        # indexed node; the frontend disables the O(n^2) constellation web above 2k
        # nodes to stay performant.
        total_count = await run_in_threadpool(collection.count)
        results = await run_in_threadpool(
            collection.get,
            limit=max(total_count, 1),
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

        # No fabricated fallback: when the code collection is empty we return an
        # empty list so the Galaxy Map can render an honest "not indexed" state
        # instead of 250 fake "Unindexed Node" stars.
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


@router.get("/api/v1/proxy/status")
async def get_proxy_status():
    """Checks the status of the subscription proxy."""
    import socket
    port = 8645
    host = "127.0.0.1"
    active = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect((host, port))
            active = True
    except Exception:
        pass

    providers = []
    if settings.GEMINI_API_KEY:
        providers.append("gemini")
    if settings.DEEPSEEK_API_KEY:
        providers.append("deepseek")
    if settings.OPENAI_API_KEY:
        providers.append("openai")
    if settings.ANTHROPIC_API_KEY:
        providers.append("anthropic")
    if hasattr(settings, "XAI_API_KEY") and settings.XAI_API_KEY:
        providers.append("xai")
    if hasattr(settings, "NVIDIA_API_KEY") and settings.NVIDIA_API_KEY:
        providers.append("nvidia")

    return {
        "status": "running" if active else "stopped",
        "port": port,
        "host": host,
        "providers": providers
    }
