import asyncio
import sqlite3
import datetime
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from tools.infrastructure.config import settings

logger = logging.getLogger("kanban_dispatcher")
LOCAL_DB_PATH = settings.INTELLIGENCE_DB_PATH

def log_event(level: str, event: str, **kwargs):
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "level": level.upper(),
        "event": event,
        "theme": "Blueprint",
        "component": "kanban_dispatcher",
        **{k: str(v) for k, v in kwargs.items()}
    }
    try:
        sys.stdout.write(json.dumps(entry) + "\n")
        sys.stdout.flush()
    except Exception:
        sys.stderr.write("LOGGING_SERIALIZATION_ERROR\n")
        sys.stderr.flush()

class KanbanDispatcher:
    """
    Kanban Autonomic Dispatcher Service.
    Manages dependency promotion, claims tasks, spawns worker agents,
    handles crash recovery, and implements a circuit breaker.
    """
    def __init__(self, loop):
        self.loop = loop
        self.is_running = False
        self.active_processes = {}  # task_id -> asyncio.subprocess.Process

    async def start(self):
        self.is_running = True
        log_event("info", "Kanban Dispatcher Service starting...")
        
        while self.is_running:
            try:
                await self.tick()
            except Exception as e:
                import traceback
                log_event("error", "Error in Kanban Dispatcher tick", exception=str(e), traceback=traceback.format_exc())
                
            # Tick every 10 seconds
            await asyncio.sleep(10)

    def stop(self):
        self.is_running = False
        log_event("info", "Kanban Dispatcher Service stopped")

    def _get_connection(self):
        conn = sqlite3.connect(LOCAL_DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    async def tick(self):
        # Verify schema table exists in thread
        def schema_exists():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='kenbun_kanban_tasks'")
                return cursor.fetchone() is not None

        if not await asyncio.to_thread(schema_exists):
            return

        # Perform stages of Kanban dispatch in background threads to avoid blocking event loop
        await asyncio.to_thread(self._recover_crashed_workers)
        await asyncio.to_thread(self._promote_decomposed_parents)
        await asyncio.to_thread(self._promote_dependencies)
        await asyncio.to_thread(self._auto_decompose_triage)
        await self._dispatch_ready_tasks()

    def _recover_crashed_workers(self):
        """Detect and recover workers whose processes crashed or died mid-flight."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.id, t.title, t.max_retries, r.id, r.pid, r.run_number 
                FROM kenbun_kanban_tasks t
                JOIN kenbun_kanban_runs r ON t.id = r.task_id
                WHERE t.status = 'running' AND r.outcome = 'active'
            ''')
            running_tasks = cursor.fetchall()
            
            for task_id, title, max_retries, run_id, pid, run_num in running_tasks:
                is_alive = False
                if pid:
                    try:
                        os.kill(pid, 0)
                        is_alive = True
                    except OSError:
                        is_alive = False
                
                if not is_alive:
                    log_event("warning", f"Detected crashed/dead worker for task '{title}'", task_id=task_id, pid=pid)
                    
                    # Count total runs so far
                    cursor.execute("SELECT COUNT(*) FROM kenbun_kanban_runs WHERE task_id = ?", (task_id,))
                    total_runs = cursor.fetchone()[0]
                    
                    now_str = datetime.datetime.utcnow().isoformat() + "Z"
                    
                    # Close the crashed run
                    cursor.execute('''
                        UPDATE kenbun_kanban_runs 
                        SET outcome = 'crashed', ended_at = ?, error = 'Worker process pid gone/crashed'
                        WHERE id = ?
                    ''', (now_str, run_id))
                    
                    if total_runs >= max_retries:
                        # Circuit breaker trips
                        log_event("error", f"Task '{title}' failed after {total_runs} attempts. Tripping circuit breaker.", task_id=task_id)
                        cursor.execute('''
                            UPDATE kenbun_kanban_tasks 
                            SET status = 'blocked', updated_at = ?
                            WHERE id = ?
                        ''', (now_str, task_id))
                        
                        # Create gave_up run entry
                        gave_up_id = f"r_{uuid.uuid4().hex[:6]}"
                        cursor.execute('''
                            INSERT INTO kenbun_kanban_runs (id, task_id, run_number, outcome, started_at, ended_at, error)
                            VALUES (?, ?, ?, 'gave_up', ?, ?, 'Circuit breaker tripped: Max retries exceeded')
                        ''', (gave_up_id, task_id, total_runs + 1, now_str, now_str))
                    else:
                        # Retry: promote back to ready
                        log_event("info", f"Retrying task '{title}' (attempt {total_runs + 1}/{max_retries})", task_id=task_id)
                        cursor.execute('''
                            UPDATE kenbun_kanban_tasks 
                            SET status = 'ready', updated_at = ?
                            WHERE id = ?
                        ''', (now_str, task_id))
                    
                    conn.commit()

    def _promote_decomposed_parents(self):
        """Promote parent tasks from 'waiting_on_children' to 'ready' when all children are 'done'."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title FROM kenbun_kanban_tasks WHERE status = 'waiting_on_children'")
            parents = cursor.fetchall()
            
            for parent_id, title in parents:
                # Count unfinished child tasks
                cursor.execute("SELECT COUNT(*) FROM kenbun_kanban_tasks WHERE parent_id = ? AND status != 'done'", (parent_id,))
                unfinished = cursor.fetchone()[0]
                
                if unfinished == 0:
                    log_event("info", f"All children complete. Promoting parent task '{title}' to ready.", task_id=parent_id)
                    now_str = datetime.datetime.utcnow().isoformat() + "Z"
                    cursor.execute("UPDATE kenbun_kanban_tasks SET status = 'ready', updated_at = ? WHERE id = ?", (now_str, parent_id))
                    conn.commit()

    def _promote_dependencies(self):
        """Promote 'todo' tasks to 'ready' if they have no parent or if their parent is 'done' or 'waiting_on_children'."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, parent_id FROM kenbun_kanban_tasks WHERE status = 'todo'")
            todos = cursor.fetchall()
            
            for task_id, title, parent_id in todos:
                should_promote = False
                if not parent_id:
                    should_promote = True
                else:
                    cursor.execute("SELECT status FROM kenbun_kanban_tasks WHERE id = ?", (parent_id,))
                    p_row = cursor.fetchone()
                    if p_row:
                        p_status = p_row[0]
                        if p_status in ('done', 'waiting_on_children'):
                            should_promote = True
                
                if should_promote:
                    log_event("info", f"Dependency satisfied. Promoting task '{title}' to ready.", task_id=task_id)
                    now_str = datetime.datetime.utcnow().isoformat() + "Z"
                    cursor.execute("UPDATE kenbun_kanban_tasks SET status = 'ready', updated_at = ? WHERE id = ?", (now_str, task_id))
                    conn.commit()

    def _auto_decompose_triage(self):
        """Auto-decompose tasks in the 'triage' column using the LLM Queen."""
        # Query triage tasks
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, body, assignee, tenant, priority, max_retries FROM kenbun_kanban_tasks WHERE status = 'triage'")
            triage_tasks = cursor.fetchall()
        
        for task_id, title, body, assignee, tenant, priority, max_retries in triage_tasks:
            log_event("info", f"Auto-decomposing triage task '{title}'", task_id=task_id)
            
            prompt = (
                f"Task Title: {title}\n"
                f"Task Description: {body}\n\n"
                "You are the Kenbun Queen. Decompose this task into a JSON list of 2-4 subtasks "
                "necessary to fulfill the goal. Assign each subtask to the best assignee "
                "(coder, auditor, designer). Format output exactly as a JSON list:\n"
                '[{"title": "...", "body": "...", "assignee": "..."}]'
            )
            
            try:
                from tools.audit.gemini_reviewer import call_gemini_pro
                raw_out = call_gemini_pro(prompt)
                
                start = raw_out.find("[")
                end = raw_out.rfind("]") + 1
                if start != -1 and end != -1:
                    json_str = raw_out[start:end]
                    subtasks = json.loads(json_str)
                    
                    with self._get_connection() as conn:
                        cursor = conn.cursor()
                        for st in subtasks:
                            st_id = f"t_{uuid.uuid4().hex[:6]}"
                            st_title = st.get("title", "Subtask")
                            st_body = st.get("body", "")
                            st_assignee = st.get("assignee", "coder")
                            
                            cursor.execute('''
                                INSERT INTO kenbun_kanban_tasks 
                                (id, title, body, assignee, tenant, priority, parent_id, status, max_retries, comments)
                                VALUES (?, ?, ?, ?, ?, ?, ?, 'todo', ?, '[]')
                            ''', (st_id, st_title, st_body, st_assignee, tenant, priority, task_id, max_retries))
                            
                        now_str = datetime.datetime.utcnow().isoformat() + "Z"
                        cursor.execute("UPDATE kenbun_kanban_tasks SET status = 'waiting_on_children', updated_at = ? WHERE id = ?", (now_str, task_id))
                        conn.commit()
                        
                    log_event("info", f"Successfully decomposed parent task '{title}' into {len(subtasks)} subtasks.", task_id=task_id)
                else:
                    raise ValueError("No JSON array found in Queen's response.")
            except Exception as e:
                log_event("warning", f"Failed to decompose task '{title}': {e}. Promoting to todo directly.", task_id=task_id)
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    now_str = datetime.datetime.utcnow().isoformat() + "Z"
                    cursor.execute("UPDATE kenbun_kanban_tasks SET status = 'todo', updated_at = ? WHERE id = ?", (now_str, task_id))
                    conn.commit()

    async def _dispatch_ready_tasks(self):
        """Claim and spawn workers for tasks in 'ready' status."""
        def fetch_ready():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, title, assignee, max_retries FROM kenbun_kanban_tasks WHERE status = 'ready'")
                return cursor.fetchall()
                
        ready_tasks = await asyncio.to_thread(fetch_ready)
        
        for task_id, title, assignee, max_retries in ready_tasks:
            # Check running count to throttle pool
            def check_running():
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM kenbun_kanban_tasks WHERE status = 'running' AND assignee = ?", (assignee,))
                    return cursor.fetchone()[0]
                    
            running_count = await asyncio.to_thread(check_running)
            if running_count >= 2:
                continue
                
            log_event("info", f"Claiming and dispatching task '{title}' to assignee '{assignee}'", task_id=task_id)
            
            # Claim task and register run
            def claim_task():
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    now_str = datetime.datetime.utcnow().isoformat() + "Z"
                    cursor.execute("UPDATE kenbun_kanban_tasks SET status = 'running', updated_at = ? WHERE id = ?", (now_str, task_id))
                    
                    cursor.execute("SELECT COUNT(*) FROM kenbun_kanban_runs WHERE task_id = ?", (task_id,))
                    run_count = cursor.fetchone()[0]
                    run_number = run_count + 1
                    
                    run_id = f"r_{uuid.uuid4().hex[:6]}"
                    cursor.execute('''
                        INSERT INTO kenbun_kanban_runs (id, task_id, run_number, outcome, assignee, started_at)
                        VALUES (?, ?, ?, 'active', ?, ?)
                    ''', (run_id, task_id, run_number, assignee, now_str))
                    conn.commit()
                    return run_id, run_number
                    
            run_id, run_number = await asyncio.to_thread(claim_task)
            
            # Spawn worker subprocess
            try:
                env = os.environ.copy()
                env["KENBUN_KANBAN_TASK"] = task_id
                env["KENBUN_KANBAN_TASK"] = task_id
                script_path = str(settings.PROJECT_ROOT / "scripts" / "kanban_worker.py")
                
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, script_path,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                self.active_processes[task_id] = proc
                log_event("info", f"Worker process successfully spawned for task '{title}'", task_id=task_id, pid=proc.pid)
                
                def update_pid():
                    with self._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE kenbun_kanban_runs SET pid = ? WHERE id = ?", (proc.pid, run_id))
                        conn.commit()
                        
                await asyncio.to_thread(update_pid)
                
            except Exception as e:
                log_event("error", f"Failed to spawn worker for task '{title}'", task_id=task_id, error=str(e))
                
                def handle_spawn_failure():
                    with self._get_connection() as conn:
                        cursor = conn.cursor()
                        now_str = datetime.datetime.utcnow().isoformat() + "Z"
                        cursor.execute('''
                            UPDATE kenbun_kanban_runs 
                            SET outcome = 'spawn_failed', ended_at = ?, error = ?
                            WHERE id = ?
                        ''', (now_str, str(e), run_id))
                        
                        if run_number >= max_retries:
                            cursor.execute("UPDATE kenbun_kanban_tasks SET status = 'blocked', updated_at = ? WHERE id = ?", (now_str, task_id))
                            gave_up_id = f"r_{uuid.uuid4().hex[:6]}"
                            cursor.execute('''
                                INSERT INTO kenbun_kanban_runs (id, task_id, run_number, outcome, started_at, ended_at, error)
                                VALUES (?, ?, ?, 'gave_up', ?, ?, 'Circuit breaker tripped: Worker spawn failed repeatedly')
                            ''', (gave_up_id, task_id, run_number + 1, now_str, now_str))
                        else:
                            cursor.execute("UPDATE kenbun_kanban_tasks SET status = 'ready', updated_at = ? WHERE id = ?", (now_str, task_id))
                        conn.commit()
                        
                await asyncio.to_thread(handle_spawn_failure)
