"""
Log Streaming Router
====================
Provides Server-Sent Events (SSE) endpoints for real-time tailing and streaming
of Kenbun logs (stdout, core_api, dashboard, etc.).
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse

from tools.infrastructure.config import settings
from tools.infrastructure.server_deps import verify_authorization

router = APIRouter()
logger = logging.getLogger(__name__)

# Security Whitelist of permitted log filenames
ALLOWED_LOG_FILES = {
    "stdout.log": "stdout.log",
    "stderr.log": "stderr.log",
    "core_api.log": "core_api.log",
    "dashboard.log": "dashboard.log",
    "mcp_debug.log": "mcp_debug.log"
}

async def log_generator(filepath: Path, initial_lines: int, level_filter: Optional[str]):
    """Asynchronous generator that tails a file and yields SSE formatted data events."""
    if not filepath.exists():
        yield f"data: Log file {filepath.name} does not exist yet.\n\n"
        # Wait for file creation
        while not filepath.exists():
            await asyncio.sleep(1.0)

    # 1. Read initial lines
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            tail_lines = lines[-initial_lines:]
            for line in tail_lines:
                if not level_filter or level_filter.upper() in line.upper():
                    yield f"data: {line.strip()}\n\n"
    except Exception as e:
        yield f"data: Error reading initial log lines: {str(e)}\n\n"

    # 2. Tail file dynamically
    file_size = filepath.stat().st_size if filepath.exists() else 0
    try:
        while True:
            await asyncio.sleep(0.5)
            if not filepath.exists():
                continue
                
            current_size = filepath.stat().st_size
            if current_size < file_size:
                # File rotated or truncated
                file_size = current_size
                yield "data: [Log File Rotated]\n\n"
                continue
                
            if current_size > file_size:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(file_size)
                    new_data = f.read()
                    file_size = current_size
                    for line in new_data.splitlines():
                        if line.strip():
                            if not level_filter or level_filter.upper() in line.upper():
                                yield f"data: {line.strip()}\n\n"
    except asyncio.CancelledError:
        logger.debug(f"Client disconnected from log stream for {filepath.name}")
    except Exception as e:
        yield f"data: Error tailing log file: {str(e)}\n\n"

@router.get("/api/v1/logs/stream", dependencies=[Depends(verify_authorization)])
async def stream_logs(
    request: Request,
    file: str = "core_api.log",
    level: Optional[str] = None,
    lines: int = 100
):
    """
    Streams log file contents in real-time using Server-Sent Events (SSE).
    """
    if file not in ALLOWED_LOG_FILES:
        raise HTTPException(status_code=400, detail="Invalid or unauthorized log file request.")

    log_path = settings.PROJECT_ROOT / ALLOWED_LOG_FILES[file]
    
    return StreamingResponse(
        log_generator(log_path, lines, level),
        media_type="text/event-stream"
    )
