"""
Cron Scheduler Router & Daemon
==============================
Provides endpoints for CRUD operations on scheduled cron jobs,
and runs a background execution loop to trigger jobs.
"""

import os
import json
import uuid
import time
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Request, Depends, HTTPException

from tools.infrastructure.config import settings
from tools.infrastructure.server_deps import verify_authorization

router = APIRouter()
logger = logging.getLogger(__name__)

DB_FILE = settings.BRAIN_HEALTH_DIR / "cron_jobs.json"
LOCK_FILE = settings.BRAIN_HEALTH_DIR / "cron_jobs.lock"

# ── Pydantic Request Models ──────────────────────────────────────────────────

class CronJobCreate(BaseModel):
    name: Optional[str] = Field("Untitled Cron Job", description="Name of the job")
    prompt: str = Field(..., description="Prompt directive to execute")
    schedule: str = Field(..., description="Standard 5-field cron expression")
    deliver: str = Field("local", description="Delivery target: local, telegram, email")

# ── Lock Protection ──────────────────────────────────────────────────────────

def _acquire_lock(timeout: float = 3.0) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            return True
        except FileExistsError:
            time.sleep(0.05)
    return False

def _release_lock():
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception as e:
        logger.error(f"Error releasing cron lock: {e}")

def _load_jobs() -> List[Dict]:
    if not DB_FILE.exists():
        return []
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else []
    except Exception as e:
        logger.error(f"Failed to load cron jobs: {e}")
        return []

def _save_jobs(jobs: List[Dict]) -> bool:
    temp_file = DB_FILE.with_suffix(".tmp")
    try:
        settings.BRAIN_HEALTH_DIR.mkdir(parents=True, exist_ok=True)
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        if temp_file.exists():
            temp_file.replace(DB_FILE)
        return True
    except Exception as e:
        logger.error(f"Failed to save cron jobs: {e}")
        if temp_file.exists():
            temp_file.unlink()
        return False

def load_jobs_safe() -> List[Dict]:
    if _acquire_lock():
        try:
            return _load_jobs()
        finally:
            _release_lock()
    return []

def save_jobs_safe(jobs: List[Dict]) -> bool:
    if _acquire_lock():
        try:
            return _save_jobs(jobs)
        finally:
            _release_lock()
    return False

# ── Scheduler Executor ───────────────────────────────────────────────────────

async def execute_cron_job_task(job: Dict):
    """Asynchronously runs the agent workflow for a scheduled cron job."""
    logger.info(f"[CRON] Executing job '{job['name']}' (ID: {job['id']})")
    try:
        from tools.utils import chat_history_manager
        from tools.utils.llm_router import call_llm_gateway
        
        # 1. Create a dedicated chat session
        session = chat_history_manager.create_session(title=f"Cron: {job['name']}")
        session_id = session["id"]
        chat_history_manager.add_message_to_session(session_id, "user", job["prompt"])
        
        # 2. Compile system prompt
        from scripts.terminal_chat import build_system_prompt
        system_prompt = build_system_prompt("cloud", "Cron-Scheduler-Daemon")
        
        # 3. Call LLM gateway in threadpool
        loop = asyncio.get_running_loop()
        response_text = await loop.run_in_executor(
            None,
            lambda: call_llm_gateway(
                system_prompt=system_prompt,
                user_message=job["prompt"],
                temperature=0.3
            )
        )
        
        if response_text:
            chat_history_manager.add_message_to_session(session_id, "kenbun", response_text)
            logger.info(f"[CRON] Job '{job['name']}' execution completed. Session: {session_id}")
            
            # Deliver to target if specified
            if job["deliver"] == "telegram":
                token = None
                chat_id = None
                if settings.TelegramSettings:
                    token = settings.TelegramSettings.bot_token.get_secret_value() if settings.TelegramSettings.bot_token else None
                    chat_id = settings.TelegramSettings.chat_id.get_secret_value() if settings.TelegramSettings.chat_id else None
                
                if token and chat_id:
                    import requests
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    requests.post(url, json={"chat_id": chat_id, "text": f"🔔 *Kenbun Cron Job: {job['name']}*\n\n{response_text}"}, timeout=10)
    except Exception as e:
        logger.error(f"[CRON] Error executing job '{job['name']}': {e}", exc_info=True)

# ── Background Scheduler Loop ───────────────────────────────────────────────

async def cron_scheduler_loop():
    """Infinite daemon loop checking and executing cron jobs using croniter."""
    from croniter import croniter
    logger.info("Initializing Kenbun Cron Scheduler daemon loop.")
    
    while True:
        await asyncio.sleep(10.0) # Check every 10 seconds
        
        jobs = load_jobs_safe()
        if not jobs:
            continue
            
        now = datetime.now(timezone.utc)
        updated = False
        
        for job in jobs:
            if not job.get("enabled", True):
                continue
                
            schedule_expr = job["schedule"]
            last_run_str = job.get("last_run")
            
            # Initialize or parse last run datetime
            if last_run_str:
                last_run_dt = datetime.fromisoformat(last_run_str)
            else:
                last_run_dt = now
                job["last_run"] = now.isoformat()
                updated = True
                continue
                
            try:
                # Calculate next execution time using croniter
                c_iter = croniter(schedule_expr, last_run_dt)
                next_run_dt = c_iter.get_next(datetime)
                # Ensure next_run_dt has timezone info matching now
                if next_run_dt.tzinfo is None:
                    next_run_dt = next_run_dt.replace(tzinfo=timezone.utc)
                
                if next_run_dt <= now:
                    # Update job timestamp to prevent double trigger
                    job["last_run"] = now.isoformat()
                    updated = True
                    # Run execution task in the background
                    asyncio.create_task(execute_cron_job_task(job))
            except Exception as e:
                logger.error(f"[CRON] Invalid cron expression or calculation error for '{job['name']}': {e}")
                
        if updated:
            save_jobs_safe(jobs)

# ── API Routes ───────────────────────────────────────────────────────────────

@router.get("/api/v1/cron/jobs", dependencies=[Depends(verify_authorization)])
async def get_cron_jobs():
    """Lists all registered cron jobs."""
    return load_jobs_safe()

@router.post("/api/v1/cron/jobs", dependencies=[Depends(verify_authorization)])
async def create_cron_job(payload: CronJobCreate):
    """Registers a new scheduled cron job."""
    from croniter import croniter
    
    # Validate cron expression
    try:
        croniter(payload.schedule)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {str(e)}")

    jobs = load_jobs_safe()
    new_job = {
        "id": f"cron_{uuid.uuid4().hex[:12]}",
        "name": payload.name,
        "prompt": payload.prompt,
        "schedule": payload.schedule,
        "deliver": payload.deliver,
        "enabled": True,
        "last_run": datetime.now(timezone.utc).isoformat()
    }
    jobs.append(new_job)
    if save_jobs_safe(jobs):
        return {"status": "success", "job": new_job}
    raise HTTPException(status_code=500, detail="Failed to save new cron job.")

@router.delete("/api/v1/cron/jobs/{job_id}", dependencies=[Depends(verify_authorization)])
async def delete_cron_job(job_id: str):
    """Deletes a scheduled cron job by ID."""
    jobs = load_jobs_safe()
    filtered = [j for j in jobs if j["id"] != job_id]
    if len(filtered) == len(jobs):
        raise HTTPException(status_code=404, detail="Job not found.")
    if save_jobs_safe(filtered):
        return {"status": "success", "message": f"Job {job_id} deleted."}
    raise HTTPException(status_code=500, detail="Failed to delete cron job.")

@router.post("/api/v1/cron/jobs/{job_id}/trigger", dependencies=[Depends(verify_authorization)])
async def trigger_cron_job(job_id: str):
    """Triggers the cron job immediately in the background."""
    jobs = load_jobs_safe()
    for job in jobs:
        if job["id"] == job_id:
            asyncio.create_task(execute_cron_job_task(job))
            return {"status": "success", "message": f"Job {job_id} triggered."}
    raise HTTPException(status_code=404, detail="Job not found.")

@router.post("/api/v1/cron/jobs/{job_id}/pause", dependencies=[Depends(verify_authorization)])
async def pause_cron_job(job_id: str):
    """Pauses execution of a cron job."""
    jobs = load_jobs_safe()
    for job in jobs:
        if job["id"] == job_id:
            job["enabled"] = False
            if save_jobs_safe(jobs):
                return {"status": "success", "message": f"Job {job_id} paused."}
    raise HTTPException(status_code=404, detail="Job not found.")

@router.post("/api/v1/cron/jobs/{job_id}/resume", dependencies=[Depends(verify_authorization)])
async def resume_cron_job(job_id: str):
    """Resumes a paused cron job."""
    jobs = load_jobs_safe()
    for job in jobs:
        if job["id"] == job_id:
            job["enabled"] = True
            job["last_run"] = datetime.now(timezone.utc).isoformat() # Reset clock
            if save_jobs_safe(jobs):
                return {"status": "success", "message": f"Job {job_id} resumed."}
    raise HTTPException(status_code=404, detail="Job not found.")
