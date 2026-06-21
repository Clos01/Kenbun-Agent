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

@app.get("/health")
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






# Shared File Paths
LOG_FILE = project_root / "brain_health" / "live_telemetry.json"
TASKS_FILE = project_root / "brain_health" / "swarm_tasks.json"
BENCHMARKS_FILE = project_root / "brain_health" / "BENCHMARKS.json"

# Projects to scan for AG_TASKS.md
def get_projects_to_watch():
    return workspace_manager.get_projects()

# In-memory queue for swarm events
swarm_events = []

_cached_config_token = None

def get_or_create_config_token() -> str:
    """
    Retrieves or generates a secure hex token.
    Prioritizes environment-based secret injection for absolute secure secret management (Least Privilege).
    Falls back to a securely restricted file within the private application directory with strict caching.
    Fails closed immediately if paths are misconfigured to guarantee system integrity.
    """
    global _cached_config_token
    if _cached_config_token is not None:
        return _cached_config_token

    # 1. Prioritize secure Environment-Based Secret Injection (Least Privilege)
    token = os.getenv("CONFIG_TOKEN")
    if token:
        _cached_config_token = token
        return token

    # 2. Secure file-based fallback (FAIL-CLOSED if directory is missing)
    if not settings.BRAIN_HEALTH_DIR:
        raise RuntimeError("CRITICAL FAIL-CLOSED: settings.BRAIN_HEALTH_DIR is unconfigured or missing. Access denied.")

    token_file = settings.BRAIN_HEALTH_DIR / "config_token.secret"

    if token_file.exists():
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                token = f.read().strip()
                if token:
                    _cached_config_token = token
                    return token
        except Exception as e:
            logging.error(f"Failed to read config token file: {e}")
            raise RuntimeError(f"CRITICAL FAIL-CLOSED: Secure config token unreadable: {e}")

    # Generate a secure fallback token in memory if no environment variable or file is present
    import secrets
    token = secrets.token_hex(32)
    try:
        import tempfile
        fd, temp_path = tempfile.mkstemp(dir=str(settings.BRAIN_HEALTH_DIR), prefix=".token.tmp")
        try:
            os.chmod(temp_path, 0o600)  # Restrict permissions immediately (race-free)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(token)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, token_file)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise
    except Exception as e:
        logging.error(f"Failed to store fallback config token: {e}")
        raise RuntimeError(f"CRITICAL FAIL-CLOSED: Failed to initialize secure configuration key: {e}")

    _cached_config_token = token
    return token


def verify_authorization(request: Request):
    """
    Enforces strict Bearer token authorization for configuration endpoints.
    Eliminates client-IP spoofing vulnerabilities by requiring cryptographic verification for all requests.
    """
    import secrets
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Missing or invalid Authorization header. Cryptographic Bearer token is required."
        )

    provided_token = auth_header.split(" ", 1)[1].strip()
    try:
        expected_token = get_or_create_config_token()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not expected_token or not secrets.compare_digest(provided_token, expected_token):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Invalid cryptographic authorization token."
        )

_signals_count_cache = 0
_signals_count_lock = asyncio.Lock()

async def update_signals_count_task():
    """Background task to scaleably and verifiably update the signals count without blocking the event loop."""
    global _signals_count_cache
    while True:
        try:
            if settings.BRAIN_HEALTH_DIR:
                routing_history_path = settings.BRAIN_HEALTH_DIR / "routing_history.jsonl"
                if routing_history_path.exists():
                    # Count lines in a non-blocking background thread (eliminates DoS blocking vector)
                    count = await asyncio.to_thread(_count_lines_sync, routing_history_path)
                    async with _signals_count_lock:
                        _signals_count_cache = count
        except Exception as e:
            logging.error(f"Error updating signals count: {e}")
        await asyncio.sleep(30)

def _count_lines_sync(file_path: Path) -> int:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

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

def _encrypt_setting(key: str, val: str) -> str:
    from tools.utils.secret_manager import encrypt_value
    if "KEY" in key or "TOKEN" in key or "SECRET" in key:
        if val and not val.startswith("enc:"):
            return "enc:" + encrypt_value(val)
    return val

class ConfigUpdateRequest(BaseModel):
    settings: Dict[str, str]

def execute_cli_command(command: str) -> str:
    """
    Safely executes a CLI command on the user's hardware.

    Hardened (chore/security-spring-cleaning):
      * No shell. ``shell=True`` has been removed.
      * Command is parsed with ``shlex.split`` and dispatched as an argv list.
      * argv[0] must be in ``tools.utils.safe_exec.ALLOWED_BINARIES``.
      * Shell metacharacters (``;``, ``&&``, ``|``, backtick, ``$()``, ``>``…)
        in the raw string cause an immediate refusal.

    The previous ``is_yolo_safe`` substring filter is intentionally NOT used:
    it inspected *shell* strings, which is fragile. The argv allowlist below
    is strictly stronger because the shell is never invoked.
    """
    import subprocess
    from tools.infrastructure.config import settings
    from tools.utils.safe_exec import safe_run, UnsafeCommandError

    try:
        res = safe_run(
            command,
            cwd=str(settings.PROJECT_ROOT),
            timeout=30.0,
        )
    except UnsafeCommandError as e:
        return f"❌ Security Violation: {e}"
    except subprocess.TimeoutExpired:
        return "❌ Error: Command execution timed out after 30 seconds."
    except FileNotFoundError as e:
        return f"❌ Error: Binary not found: {e}"
    except Exception as e:
        return f"❌ Error: Command execution failed: {e}"

    output = res.stdout or ""
    if res.stderr:
        output += f"\n{res.stderr}"
    if not output.strip():
        output = f"Command completed with exit code {res.returncode}."
    return f"```\n{output}\n```"



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
