import asyncio
import sqlite3
import datetime
import json
import logging
import re
import sys
from pathlib import Path
from croniter import croniter
from tools.infrastructure.config import settings

logger = logging.getLogger("scheduler_daemon")
LOCAL_DB_PATH = settings.INTELLIGENCE_DB_PATH

def log_event(level: str, event: str, **kwargs):
    # Blueprint-compliant metadata
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "level": level.upper(),
        "event": event,
        "theme": "Blueprint",  # Token compliance
        "component": "scheduler_daemon",
        **{k: str(v) for k, v in kwargs.items()}  # Robust string sanitization
    }
    try:
        sys.stdout.write(json.dumps(entry) + "\n")
        sys.stdout.flush()
    except (TypeError, ValueError):
        sys.stderr.write("LOGGING_SERIALIZATION_ERROR\n")
        sys.stderr.flush()

def calculate_next_run(schedule: str, from_time: datetime.datetime) -> datetime.datetime:
    schedule_clean = schedule.strip().lower()
    
    # 1. One-shot relative delay (e.g. 30m, 2h, 1d)
    m_oneshot = re.match(r"^(\d+)([mhd])$", schedule_clean)
    if m_oneshot:
        value, unit = m_oneshot.groups()
        value = int(value)
        if unit == 'm':
            return from_time + datetime.timedelta(minutes=value)
        elif unit == 'h':
            return from_time + datetime.timedelta(hours=value)
        elif unit == 'd':
            return from_time + datetime.timedelta(days=value)
            
    # 2. Recurring interval (e.g. every 30m, every 2h, every 1d)
    m_recurring = re.match(r"^every\s+(\d+)([mhd])$", schedule_clean)
    if m_recurring:
        value, unit = m_recurring.groups()
        value = int(value)
        if unit == 'm':
            return from_time + datetime.timedelta(minutes=value)
        elif unit == 'h':
            return from_time + datetime.timedelta(hours=value)
        elif unit == 'd':
            return from_time + datetime.timedelta(days=value)

    # 3. ISO timestamp (e.g. 2026-03-15T09:00:00)
    try:
        dt = datetime.datetime.fromisoformat(schedule_clean.upper().replace('Z', ''))
        return dt
    except ValueError:
        pass

    # 4. Standard Cron expression via croniter
    try:
        iter = croniter(schedule_clean, from_time)
        return iter.get_next(datetime.datetime)
    except Exception:
        raise ValueError(f"Invalid schedule format: '{schedule}'")

def is_oneshot(schedule: str) -> bool:
    schedule_clean = schedule.strip().lower()
    if "every" in schedule_clean or "*" in schedule_clean or "?" in schedule_clean:
        return False
    return True

async def execute_cron_job(job_row):
    job_id, name, schedule, prompt, script_path, no_agent, context_from, workdir, delivery_targets, enabled_toolsets, status, last_run_at, next_run_at, created_at = job_row
    
    log_event("info", f"Starting execution of cron job '{name}'", job_id=job_id)
    
    # 1. Resolve context chaining (context_from)
    context_content = ""
    if context_from:
        try:
            upstream_jobs = json.loads(context_from)
            for upstream in upstream_jobs:
                upstream_dir = Path(settings.PROJECT_ROOT) / "scratch" / "cron" / "output" / upstream
                if upstream_dir.exists():
                    md_files = sorted(upstream_dir.glob("*.md"), key=lambda p: p.stat().st_mtime)
                    if md_files:
                        newest_file = md_files[-1]
                        content = newest_file.read_text(encoding="utf-8")
                        context_content += f"\n--- Context from Upstream Job '{upstream}' ---\n{content}\n"
        except Exception as e:
            log_event("error", f"Error loading context_from for job '{name}'", job_id=job_id, error=str(e))

    # 2. Check wakeAgent gate if a script is provided
    wake_agent = True
    script_context = {}
    delivery_content = ""
    
    if script_path:
        script_full_path = Path(settings.PROJECT_ROOT) / script_path
        if not script_full_path.exists():
            log_event("error", f"Script not found at '{script_path}' for job '{name}'", job_id=job_id)
            wake_agent = False
            delivery_content = f"❌ Pre-check script not found at {script_path}"
        else:
            try:
                code = script_full_path.read_text(encoding="utf-8")
                lang = "python"
                if script_path.endswith(".js"):
                    lang = "javascript"
                
                from tools.execution.e2b_runner import run_code_safely
                result_str = run_code_safely(code, language=lang)
                
                # Extract stdout
                stdout_match = re.search(r"### stdout\n```\n(.*?)\n```", result_str, re.DOTALL)
                stdout_str = stdout_match.group(1) if stdout_match else ""
                
                # Check for JSON instructions
                match = re.search(r"(\{.*wakeAgent.*\})", stdout_str)
                if match:
                    try:
                        parsed = json.loads(match.group(1))
                        wake_agent = parsed.get("wakeAgent", True)
                        script_context = parsed.get("context", {})
                    except Exception:
                        pass
                else:
                    if '{"wakeAgent": false}' in stdout_str or '{"wakeAgent": false}' in result_str:
                        wake_agent = False
                
                if no_agent:
                    if "❌ FAILED" in result_str or "❌ E2B Sandbox error" in result_str:
                        delivery_content = f"⚠️ Cron Job Watchdog '{name}' execution failed:\n\n{result_str}"
                    else:
                        delivery_content = stdout_str.strip()
                        if not delivery_content:
                            log_event("info", f"Watchdog script '{name}' produced empty output. Skipping delivery.", job_id=job_id)
                            wake_agent = False
            except Exception as e:
                log_event("error", f"Failed executing pre-check script for job '{name}'", job_id=job_id, error=str(e))
                wake_agent = False
                delivery_content = f"❌ Execution error: {e}"

    if not wake_agent and not no_agent:
        log_event("info", f"Cron job '{name}' skipped via wakeAgent gate.", job_id=job_id)
        return

    # 3. Trigger Swarm Execution (if not no_agent)
    final_output = ""
    if not no_agent:
        full_prompt = f"SCHEDULED TASK RUN: {name}\n"
        if context_content:
            full_prompt += context_content
        if script_context:
            full_prompt += f"\n--- Script Pre-check Context ---\n{json.dumps(script_context, indent=2)}\n"
        full_prompt += f"\nInstruction:\n{prompt}"
        
        try:
            from tools.infrastructure.orchestrator import orchestrate
            workflow_to_run = "research_implement"
            if "audit" in prompt.lower() or "review" in prompt.lower():
                workflow_to_run = "code_review"
                
            project_dir = workdir if workdir else settings.PROJECT_ROOT
            
            loop = asyncio.get_running_loop()
            def run_sync():
                return orchestrate(
                    workflow=workflow_to_run,
                    task=full_prompt,
                    project_path=project_dir
                )
            
            final_output = await loop.run_in_executor(None, run_sync)
        except Exception as e:
            import traceback
            log_event("error", f"Agent execution failed for cron job '{name}'", job_id=job_id, error=str(e), traceback=traceback.format_exc())
            final_output = f"Error executing task: {e}"
    else:
        final_output = delivery_content

    # 4. Save output
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = Path(settings.PROJECT_ROOT) / "scratch" / "cron" / "output" / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{timestamp}.md"
    try:
        out_file.write_text(final_output, encoding="utf-8")
    except Exception as e:
        log_event("error", f"Failed saving output file for job '{name}'", job_id=job_id, error=str(e))

    # 5. Deliver output
    if delivery_targets and final_output:
        try:
            targets = json.loads(delivery_targets)
            from tools.utils.notifications import send_notification
            for target in targets:
                send_notification(f"Cronjob: {name} ({target})", final_output)
        except Exception as e:
            log_event("error", f"Delivery failed for job '{name}'", job_id=job_id, error=str(e))

class ChronosDaemon:
    """
    Chronos Autonomic Scheduling Engine (System 7).
    Ticks the scheduler database every 60 seconds and executes due jobs.
    """
    def __init__(self, loop):
        self.loop = loop
        self.is_running = False

    async def start(self):
        self.is_running = True
        log_event("info", "Chronos Scheduling Daemon starting...")
        
        while self.is_running:
            try:
                await self.tick()
            except Exception as e:
                import traceback
                log_event("error", "Error in Chronos tick", exception=str(e), traceback=traceback.format_exc())
                
            # Tick every 60 seconds
            await asyncio.sleep(60)

    def stop(self):
        self.is_running = False
        log_event("info", "Chronos Scheduling Daemon stopped")

    async def tick(self):
        # Scan SQLite for active and due cron jobs
        conn = sqlite3.connect(LOCAL_DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='kenbun_cron_jobs'")
        if not cursor.fetchone():
            conn.close()
            return
            
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        cursor.execute('''
            SELECT * FROM kenbun_cron_jobs 
            WHERE status = 'active' AND next_run_at <= ?
        ''', (now_str,))
        
        due_jobs = cursor.fetchall()
        if not due_jobs:
            conn.close()
            return
            
        log_event("info", f"Found {len(due_jobs)} due scheduled jobs", count=len(due_jobs))
        
        # Execute jobs
        for job in due_jobs:
            job_id = job[0]
            name = job[1]
            schedule = job[2]
            
            # Calculate next run time and update status
            now = datetime.datetime.now(datetime.timezone.utc)
            try:
                next_run = calculate_next_run(schedule, now)
                next_run_str = next_run.isoformat() + "Z"
                oneshot = is_oneshot(schedule)
                
                if oneshot:
                    cursor.execute('''
                        UPDATE kenbun_cron_jobs 
                        SET status = 'completed', last_run_at = ?, next_run_at = NULL 
                        WHERE id = ?
                    ''', (now.isoformat() + "Z", job_id))
                else:
                    cursor.execute('''
                        UPDATE kenbun_cron_jobs 
                        SET last_run_at = ?, next_run_at = ? 
                        WHERE id = ?
                    ''', (now.isoformat() + "Z", next_run_str, job_id))
                conn.commit()
                
                # Dispatch execution asynchronously so it doesn't block the tick
                asyncio.run_coroutine_threadsafe(execute_cron_job(job), self.loop)
                
            except Exception as e:
                log_event("error", f"Failed updating schedule for job '{name}'", job_id=job_id, error=str(e))
                cursor.execute('''
                    UPDATE kenbun_cron_jobs 
                    SET status = 'error' 
                    WHERE id = ?
                ''', (job_id,))
                conn.commit()
                
        conn.close()
