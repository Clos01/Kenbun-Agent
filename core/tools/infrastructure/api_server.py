import os
import json
import asyncio
import time
import hashlib
import math
import logging
from dataclasses import asdict
from pathlib import Path
import random
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, Depends
from pydantic import BaseModel
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

# Import centralized settings
from tools.infrastructure.config import settings
project_root = settings.PROJECT_ROOT

from tools.strategy.strategy_manager import governor
from tools.infrastructure.topology_manager import get_swarm_events
from tools.infrastructure.server_deps import get_or_create_config_token, update_signals_count_task
from tools.infrastructure.orchestrator import orchestrate
from tools.strategy.intelligence_engine import intelligence_engine
from tools.audit.guardrail_agent import guardrail_agent
from tools.execution.claude_code_agent import claude_code_agent
from tools.execution.p330_worker import p330_worker
from tools.utils.workspace_manager import workspace_manager
from tools.strategy.token_governor import token_governor
from tools.autonomic.autonomic_corrector import corrector
from tools.memory.honcho_connect import get_project_collection
from tools.strategy.neural_classifier import neural_classifier

app = FastAPI(title="Kenbun Mission Control API")

def health_check():
    return {"status": "healthy"}

from urllib.parse import urlparse

def build_cors_origins() -> List[str]:
    """
    Constructs a hardened, explicit CORS origin whitelist.
    Adheres strictly to the CTO-Consensus security standards:
    - Eliminates DNS rebinding risks by using a static, explicit whitelist.
    - Sanitizes all environment-derived strings using urllib.parse.
    - Prevents arbitrary port and protocol injections.
    """
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    
    # 1. Sanitize and append settings.FRONTEND_URL
    if settings.FRONTEND_URL:
        try:
            parsed = urlparse(settings.FRONTEND_URL)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                origins.append(f"{parsed.scheme}://{parsed.netloc}")
        except Exception as e:
            logging.error(f"CORS Init: Invalid FRONTEND_URL: {e}")

    # 2. Sanitize and trust the host machine's configured Tailscale/PC IP for local development
    if settings.SWARM_PC_IP:
        pc_ip = settings.SWARM_PC_IP.strip('"\'')
        if pc_ip not in ("localhost", "127.0.0.1"):
            # Clean and validate PC IP
            try:
                # If a port is present in FRONTEND_URL, reuse it; otherwise default to 3000
                frontend_port = 3000
                if settings.FRONTEND_URL:
                    parsed_fe = urlparse(settings.FRONTEND_URL)
                    if parsed_fe.port:
                        frontend_port = parsed_fe.port
                
                # Strip potential path or protocol injections from pc_ip
                clean_ip = pc_ip.split("/")[-1].split(":")[0].strip("[]")
                
                # Trust and construct explicit entries
                origins.append(f"http://{clean_ip}:{frontend_port}")
                origins.append(f"https://{clean_ip}:{frontend_port}")
            except Exception as e:
                logging.error(f"CORS Init: Invalid SWARM_PC_IP: {e}")

    # Dedup and return
    return list(set(origins))

# Allow Dashboard to connect securely (CTO Standard CORS Whitelisting)
# NOTE: Using wildcard for local Docker dev. Tighten for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=build_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)






def get_projects_to_watch():
    return workspace_manager.get_projects()

# In-memory queue for swarm events
swarm_events = []



@app.on_event("startup")
async def startup_event():
    """Start background daemons on server load."""
    try:
        get_or_create_config_token()
    except RuntimeError as e:
        logging.critical(f"FATAL STARTUP ERROR: {e}")
        # Halt startup in production (Fail-Closed)
        import sys
        sys.exit(1)
        
    # Start the non-blocking signals count update task
    asyncio.create_task(update_signals_count_task())
    from tools.memory.digester import digester_daemon
    asyncio.create_task(digester_daemon.digestion_loop())


# --- Router Registrations ---
from tools.infrastructure.routers.health import router as health_router
from tools.infrastructure.routers.config import router as config_router
from tools.infrastructure.routers.telemetry import router as telemetry_router
from tools.infrastructure.routers.intelligence import router as intelligence_router
from tools.infrastructure.routers.chat import router as chat_router
from tools.infrastructure.routers.swarm import router as swarm_router
from tools.infrastructure.routers.legacy import router as legacy_router

app.include_router(health_router)
app.include_router(config_router)
app.include_router(telemetry_router)
app.include_router(intelligence_router)
app.include_router(chat_router)
app.include_router(swarm_router)
app.include_router(legacy_router)


if __name__ == "__main__":
    import uvicorn
    # Bind host is configurable via API_HOST. Defaults to 0.0.0.0 for Docker
    # container networking; set API_HOST=127.0.0.1 for native/loopback-only runs.
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
