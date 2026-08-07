"""Health-check and diagnostics routes.

Provides a lightweight liveness probe (GET /health) and a deeper
diagnostics endpoint that pings ChromaDB, Ollama, and other
infrastructure layers.
"""

import os

import requests
from fastapi import APIRouter, status

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {"status": "healthy"}


@router.get("/api/v1/system/storage")
async def get_storage_telemetry():
    """Retrieves disk storage usage across local node and p330 server."""
    from tools.infrastructure.storage_monitor import get_storage_stats
    return get_storage_stats()


@router.get("/api/v1/health/diagnostics")
async def get_system_diagnostics():
    from tools.memory.honcho_connect import get_project_collection

    status = {
        "mcp_backend": {"status": "online", "message": "FastMCP Server Active"},
        "system_3_memory": {"status": "offline", "message": "Checking ChromaDB..."},
        "ollama_acceleration": {"status": "offline", "message": "Checking Host Ollama..."},
        "system_4_governor": {"status": "online", "message": "Bayesian logic ready."},
    }

    # 1. Check ChromaDB
    try:
        collection = get_project_collection("code")
        if collection:
            status["system_3_memory"] = {"status": "online", "message": "ChromaDB Connected"}
    except Exception as e:
        status["system_3_memory"]["message"] = f"Error: {e}"

    # 2. Check Host Ollama
    try:
        ollama_url = os.environ.get("OLLAMA_URL", "http://ollama_server:11434/api/generate")
        base_url = ollama_url.split("/api/")[0]
        res = requests.get(base_url, timeout=1.0)
        if res.status_code == 200:
            status["ollama_acceleration"] = {
                "status": "online",
                "message": "Dockerized Ollama Engine Active",
            }
    except requests.exceptions.RequestException:
        status["ollama_acceleration"]["message"] = (
            "Initializing: Dockerized Ollama is booting and pulling models..."
        )

    return status
