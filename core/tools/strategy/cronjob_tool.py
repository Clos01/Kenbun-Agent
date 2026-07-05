import sqlite3
import json
import uuid
import datetime
import re
from croniter import croniter
from tools.registry import sovereign_tool
from tools.infrastructure.config import settings

LOCAL_DB_PATH = settings.INTELLIGENCE_DB_PATH

def ensure_cron_table_exists(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kenbun_cron_jobs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            schedule TEXT NOT NULL,
            prompt TEXT,
            script_path TEXT,
            no_agent INTEGER DEFAULT 0,
            context_from TEXT,
            workdir TEXT,
            delivery_targets TEXT,
            enabled_toolsets TEXT,
            status TEXT DEFAULT 'active',
            last_run_at TEXT,
            next_run_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

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
        raise ValueError(f"Invalid schedule format: '{schedule}'. Supported formats: "
                         f"'30m', 'every 2h', '2026-03-15T09:00:00', or standard cron '0 9 * * *'")

def lookup_job(cursor, job_ref: str):
    """Lookup a job by ID or Name. Prefers ID, handles ambiguous names."""
    # Try ID lookup first
    cursor.execute("SELECT * FROM kenbun_cron_jobs WHERE id = ?", (job_ref,))
    row = cursor.fetchone()
    if row:
        return row
        
    # Try Name lookup
    cursor.execute("SELECT * FROM kenbun_cron_jobs WHERE LOWER(name) = ?", (job_ref.lower(),))
    rows = cursor.fetchall()
    if len(rows) == 1:
        return rows[0]
    elif len(rows) > 1:
        candidates = ", ".join([r[0] for r in rows])
        raise ValueError(f"Ambiguous name '{job_ref}' matches multiple jobs: [{candidates}]. Please use the exact job ID.")
        
    raise ValueError(f"Job '{job_ref}' not found.")

def parse_list_arg(val: str) -> str:
    """Helper to convert string/list args into a clean JSON string array."""
    if not val:
        return "[]"
    val_clean = val.strip()
    if val_clean.startswith("[") and val_clean.endswith("]"):
        try:
            parsed = json.loads(val_clean)
            if isinstance(parsed, list):
                return json.dumps(parsed)
        except json.JSONDecodeError:
            pass
    # Comma separated fallback
    parts = [p.strip() for p in val_clean.split(",") if p.strip()]
    return json.dumps(parts)

@sovereign_tool(name="cronjob", category="Strategy")
def cronjob(
    action: str,
    job_id: str = "",
    name: str = "",
    schedule: str = "",
    prompt: str = "",
    script_path: str = "",
    no_agent: bool = False,
    context_from: str = "",
    workdir: str = "",
    delivery_targets: str = "",
    enabled_toolsets: str = "",
) -> str:
    """
    Manage scheduled tasks (cron jobs) inside Kenbun.
    
    Supported Actions:
      - 'create': Create a new scheduled task.
      - 'list': List all scheduled tasks.
      - 'update': Modify an existing scheduled task.
      - 'pause': Suspend execution of a scheduled task.
      - 'resume': Resume execution of a paused task.
      - 'run': Force trigger the task to run on the next tick.
      - 'remove': Delete the task permanently.
      
    Args:
      action: The scheduler operation to perform ('create', 'list', 'update', 'pause', 'resume', 'run', 'remove').
      job_id: The unique ID or name of the target job (required for update, pause, resume, run, remove).
      name: Desired human-readable name of the job.
      schedule: The run frequency. Supports 'every 2h', '30m' (one-shot delay), ISO timestamp, or cron '0 9 * * *'.
      prompt: The instruction prompt for the agent to execute.
      script_path: Path to a local script to execute (inside sandbox).
      no_agent: If True, executes script stdout verbatim, skipping the LLM entirely.
      context_from: JSON array or comma-separated list of upstream job IDs/names to load outputs from.
      workdir: Absolute directory inside sandbox to use as the working directory.
      delivery_targets: Comma-separated list or JSON array of delivery channels (e.g., 'slack', 'discord', 'telegram').
      enabled_toolsets: Comma-separated list or JSON array of toolsets the job is allowed to use.
    """
    action_clean = action.strip().lower()
    
    # 1. Connect to SQLite DB and ensure table is present
    conn = sqlite3.connect(LOCAL_DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    ensure_cron_table_exists(conn)
    cursor = conn.cursor()
    
    try:
        if action_clean == "create":
            if not name:
                raise ValueError("Parameter 'name' is required when creating a job.")
            if not schedule:
                raise ValueError("Parameter 'schedule' is required when creating a job.")
            if not prompt and not script_path:
                raise ValueError("Either 'prompt' or 'script_path' must be provided.")
                
            # Verify name doesn't collide
            cursor.execute("SELECT id FROM kenbun_cron_jobs WHERE LOWER(name) = ?", (name.lower(),))
            if cursor.fetchone():
                raise ValueError(f"A cron job with name '{name}' already exists. Please choose a unique name.")
                
            job_uuid = "kb_" + uuid.uuid4().hex[:12]
            now = datetime.datetime.utcnow()
            next_run = calculate_next_run(schedule, now)
            
            ctx = parse_list_arg(context_from)
            deliv = parse_list_arg(delivery_targets)
            tools = parse_list_arg(enabled_toolsets)
            
            cursor.execute('''
                INSERT INTO kenbun_cron_jobs (
                    id, name, schedule, prompt, script_path, no_agent,
                    context_from, workdir, delivery_targets, enabled_toolsets,
                    status, last_run_at, next_run_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
            ''', (
                job_uuid, name, schedule, prompt, script_path, 1 if no_agent else 0,
                ctx, workdir, deliv, tools, 'active', next_run.isoformat() + "Z"
            ))
            conn.commit()
            
            return json.dumps({
                "status": "success",
                "message": f"Successfully created scheduled task '{name}' (ID: {job_uuid})",
                "job_id": job_uuid,
                "next_run_at": next_run.isoformat() + "Z"
            }, indent=2)
            
        elif action_clean == "list":
            cursor.execute("SELECT * FROM kenbun_cron_jobs")
            columns = [col[0] for col in cursor.description]
            jobs = []
            for row in cursor.fetchall():
                jobs.append(dict(zip(columns, row)))
            return json.dumps(jobs, indent=2)
            
        elif action_clean == "update":
            if not job_id:
                raise ValueError("Parameter 'job_id' (or name) is required for update.")
                
            row = lookup_job(cursor, job_id)
            target_id = row[0]
            
            updates = []
            params = []
            
            if name:
                updates.append("name = ?")
                params.append(name)
            if schedule:
                updates.append("schedule = ?")
                params.append(schedule)
                now = datetime.datetime.utcnow()
                next_run = calculate_next_run(schedule, now)
                updates.append("next_run_at = ?")
                params.append(next_run.isoformat() + "Z")
            if prompt is not None and prompt != "":
                updates.append("prompt = ?")
                params.append(prompt)
            if script_path is not None and script_path != "":
                updates.append("script_path = ?")
                params.append(script_path)
            if no_agent is not None:
                updates.append("no_agent = ?")
                params.append(1 if no_agent else 0)
            if context_from != "":
                updates.append("context_from = ?")
                params.append(parse_list_arg(context_from))
            if workdir != "":
                updates.append("workdir = ?")
                params.append(workdir)
            if delivery_targets != "":
                updates.append("delivery_targets = ?")
                params.append(parse_list_arg(delivery_targets))
            if enabled_toolsets != "":
                updates.append("enabled_toolsets = ?")
                params.append(parse_list_arg(enabled_toolsets))
                
            if not updates:
                return json.dumps({"status": "noop", "message": "No changes specified for update."}, indent=2)
                
            params.append(target_id)
            sql = f"UPDATE kenbun_cron_jobs SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, tuple(params))
            conn.commit()
            
            return json.dumps({
                "status": "success",
                "message": f"Successfully updated job '{row[1]}' (ID: {target_id})"
            }, indent=2)
            
        elif action_clean == "pause":
            if not job_id:
                raise ValueError("Parameter 'job_id' (or name) is required to pause.")
            row = lookup_job(cursor, job_id)
            cursor.execute("UPDATE kenbun_cron_jobs SET status = 'paused' WHERE id = ?", (row[0],))
            conn.commit()
            return json.dumps({"status": "success", "message": f"Paused scheduled task '{row[1]}' (ID: {row[0]})"}, indent=2)
            
        elif action_clean == "resume":
            if not job_id:
                raise ValueError("Parameter 'job_id' (or name) is required to resume.")
            row = lookup_job(cursor, job_id)
            now = datetime.datetime.utcnow()
            next_run = calculate_next_run(row[2], now)
            cursor.execute("UPDATE kenbun_cron_jobs SET status = 'active', next_run_at = ? WHERE id = ?", (next_run.isoformat() + "Z", row[0]))
            conn.commit()
            return json.dumps({
                "status": "success", 
                "message": f"Resumed scheduled task '{row[1]}' (ID: {row[0]})",
                "next_run_at": next_run.isoformat() + "Z"
            }, indent=2)
            
        elif action_clean == "run":
            if not job_id:
                raise ValueError("Parameter 'job_id' (or name) is required to trigger immediately.")
            row = lookup_job(cursor, job_id)
            epoch = datetime.datetime.utcfromtimestamp(0).isoformat() + "Z"
            cursor.execute("UPDATE kenbun_cron_jobs SET next_run_at = ? WHERE id = ?", (epoch, row[0]))
            conn.commit()
            return json.dumps({"status": "success", "message": f"Job '{row[1]}' triggered to run on next tick."}, indent=2)
            
        elif action_clean == "remove":
            if not job_id:
                raise ValueError("Parameter 'job_id' (or name) is required to remove.")
            row = lookup_job(cursor, job_id)
            cursor.execute("DELETE FROM kenbun_cron_jobs WHERE id = ?", (row[0],))
            conn.commit()
            return json.dumps({"status": "success", "message": f"Permanently removed job '{row[1]}' (ID: {row[0]})"}, indent=2)
            
        else:
            raise ValueError(f"Unknown action '{action}'. Action must be one of: create, list, update, pause, resume, run, remove.")
            
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)
    finally:
        conn.close()
