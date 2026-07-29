import sqlite3
import json
import uuid
import datetime
import os
import logging
from typing import Optional
from tools.registry import sovereign_tool
from tools.infrastructure.config import settings

logger = logging.getLogger("kanban_tools")
LOCAL_DB_PATH = settings.INTELLIGENCE_DB_PATH

def _ensure_schema(conn):
    """Create the kanban tables if they don't exist. These were never migrated
    into the intelligence DB, so every kanban_* call failed with
    'no such table: kenbun_kanban_tasks'. Self-heal on connect."""
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS kenbun_kanban_tasks (
            id TEXT PRIMARY KEY,
            title TEXT,
            body TEXT,
            assignee TEXT,
            tenant TEXT,
            priority INTEGER DEFAULT 0,
            parent_id TEXT,
            status TEXT DEFAULT 'triage',
            max_retries INTEGER DEFAULT 3,
            comments TEXT DEFAULT '[]',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT,
            heartbeat TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS kenbun_kanban_runs (
            id TEXT PRIMARY KEY,
            task_id TEXT,
            run_number INTEGER,
            outcome TEXT,
            started_at TEXT,
            ended_at TEXT,
            duration_seconds REAL,
            summary TEXT,
            metadata TEXT,
            error TEXT
        )
    ''')
    conn.commit()

def get_db_connection():
    conn = sqlite3.connect(LOCAL_DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    _ensure_schema(conn)
    return conn

def resolve_task_id(task_id: str) -> str:
    """Resolves task_id fallback to env vars if not explicitly provided."""
    if task_id:
        return task_id.strip()
    env_id = os.environ.get("KENBUN_KANBAN_TASK")
    if env_id:
        return env_id.strip()
    raise ValueError("Task ID must be provided or set via KENBUN_KANBAN_TASK environment variable.")

@sovereign_tool(name="kanban_create", category="Strategy")
def kanban_create(
    title: str,
    body: str = "",
    assignee: str = "",
    tenant: str = "",
    priority: int = 0,
    parent_id: str = "",
    status: str = "triage",
    max_retries: int = 3
) -> str:
    """
    Create a new task on the Kanban board.
    
    Args:
        title: Short title summarizing the task.
        body: Markdown description of the goal, approach, and criteria.
        assignee: Worker persona/profile targeted for this task (e.g. coder, auditor, designer).
        tenant: Project or team domain name to isolate tasks.
        priority: Priority weight (higher is more urgent).
        parent_id: Optional ID of the parent task this depends on.
        status: Starting column ('triage', 'todo', 'ready', 'running', 'blocked', 'done').
        max_retries: Consecutive worker failures allowed before auto-blocking.
    """
    task_id = f"t_{uuid.uuid4().hex[:6]}"
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO kenbun_kanban_tasks 
            (id, title, body, assignee, tenant, priority, parent_id, status, max_retries, comments)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (task_id, title.strip(), body.strip(), assignee.strip(), tenant.strip(), priority, parent_id.strip() or None, status.strip(), max_retries, "[]"))
        conn.commit()
        
        result = {
            "status": "success",
            "id": task_id,
            "title": title,
            "assignee": assignee,
            "status_column": status
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error in kanban_create: {e}")
        return json.dumps({"status": "error", "message": str(e)}, indent=2)
    finally:
        conn.close()

@sovereign_tool(name="kanban_show", category="Strategy")
def kanban_show(task_id: str = "") -> str:
    """
    Retrieve details of a specific task, its run history, and parent handoff context.
    
    Args:
        task_id: The ID of the task to view. Defaults to KENBUN_KANBAN_TASK env var.
    """
    try:
        tid = resolve_task_id(task_id)
    except ValueError as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM kenbun_kanban_tasks WHERE id = ?", (tid,))
        task_row = cursor.fetchone()
        if not task_row:
            return json.dumps({"status": "error", "message": f"Task '{tid}' not found."}, indent=2)
            
        # Get column names
        col_names = [description[0] for description in cursor.description]
        task_data = dict(zip(col_names, task_row))
        
        # Parse comments
        try:
            task_data["comments"] = json.loads(task_data["comments"] or "[]")
        except Exception:
            task_data["comments"] = []
            
        # Retrieve Run History
        cursor.execute("SELECT * FROM kenbun_kanban_runs WHERE task_id = ? ORDER BY run_number ASC", (tid,))
        run_rows = cursor.fetchall()
        run_cols = [description[0] for description in cursor.description]
        runs = []
        for r in run_rows:
            run_data = dict(zip(run_cols, r))
            try:
                run_data["metadata"] = json.loads(run_data["metadata"] or "{}")
            except Exception:
                run_data["metadata"] = {}
            runs.append(run_data)
            
        # Retrieve Parent context
        parent_results = {}
        if task_data.get("parent_id"):
            pid = task_data["parent_id"]
            cursor.execute("SELECT title, status FROM kenbun_kanban_tasks WHERE id = ?", (pid,))
            p_row = cursor.fetchone()
            if p_row:
                p_title, p_status = p_row
                cursor.execute('''
                    SELECT outcome, summary, metadata FROM kenbun_kanban_runs 
                    WHERE task_id = ? AND outcome = 'completed'
                    ORDER BY run_number DESC LIMIT 1
                ''', (pid,))
                pr_row = cursor.fetchone()
                if pr_row:
                    pr_outcome, pr_summary, pr_meta_str = pr_row
                    try:
                        pr_meta = json.loads(pr_meta_str or "{}")
                    except Exception:
                        pr_meta = {}
                else:
                    pr_outcome, pr_summary, pr_meta = None, None, {}
                    
                parent_results[pid] = {
                    "title": p_title,
                    "status": p_status,
                    "last_completed_run": {
                        "outcome": pr_outcome,
                        "summary": pr_summary,
                        "metadata": pr_meta
                    }
                }
                
        # Build worker context
        worker_context = {
            "prior_attempts": [
                {
                    "run_number": r["run_number"],
                    "outcome": r["outcome"],
                    "summary": r["summary"],
                    "error": r["error"],
                    "metadata": r["metadata"],
                    "started_at": r["started_at"],
                    "ended_at": r["ended_at"]
                }
                for r in runs
            ],
            "parent_task_results": parent_results
        }
        
        task_data["worker_context"] = worker_context
        task_data["runs"] = runs
        
        return json.dumps(task_data, indent=2)
    except Exception as e:
        logger.error(f"Error in kanban_show: {e}")
        return json.dumps({"status": "error", "message": str(e)}, indent=2)
    finally:
        conn.close()

@sovereign_tool(name="kanban_list", category="Strategy")
def kanban_list(status: str = "", assignee: str = "", tenant: str = "") -> str:
    """
    List tasks on the Kanban board with optional filters.
    
    Args:
        status: Filter tasks by column (e.g. 'ready', 'running', 'blocked', 'done').
        assignee: Filter tasks assigned to a specific worker.
        tenant: Filter tasks belonging to a specific tenant/project.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM kenbun_kanban_tasks WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status.strip())
        if assignee:
            query += " AND assignee = ?"
            params.append(assignee.strip())
        if tenant:
            query += " AND tenant = ?"
            params.append(tenant.strip())
            
        query += " ORDER BY priority DESC, created_at ASC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        col_names = [description[0] for description in cursor.description]
        
        results = []
        for r in rows:
            task = dict(zip(col_names, r))
            try:
                task["comments"] = json.loads(task["comments"] or "[]")
            except Exception:
                task["comments"] = []
            results.append(task)
            
        return json.dumps(results, indent=2)
    except Exception as e:
        logger.error(f"Error in kanban_list: {e}")
        return json.dumps({"status": "error", "message": str(e)}, indent=2)
    finally:
        conn.close()

@sovereign_tool(name="kanban_complete", category="Strategy")
def kanban_complete(task_id: str = "", summary: str = "", metadata: str = "{}") -> str:
    """
    Mark a task as completed, recording the handoff summary and metadata.
    
    Args:
        task_id: The ID of the task. Defaults to KENBUN_KANBAN_TASK env var.
        summary: Clear summary of changes, decisions, or results.
        metadata: JSON string of structured metrics (e.g. changed files, tests run).
    """
    try:
        tid = resolve_task_id(task_id)
    except ValueError as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)
        
    if not summary:
        return json.dumps({"status": "error", "message": "Summary is required to complete a task."}, indent=2)
        
    # Validate metadata is valid JSON
    try:
        meta_dict = json.loads(metadata or "{}")
        metadata_str = json.dumps(meta_dict)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Invalid JSON in metadata: {e}"}, indent=2)
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Check task existence
        cursor.execute("SELECT status FROM kenbun_kanban_tasks WHERE id = ?", (tid,))
        task_row = cursor.fetchone()
        if not task_row:
            return json.dumps({"status": "error", "message": f"Task '{tid}' not found."}, indent=2)
            
        now_str = datetime.datetime.utcnow().isoformat() + "Z"
        
        # Update active run if exists
        cursor.execute('''
            SELECT id, started_at FROM kenbun_kanban_runs 
            WHERE task_id = ? AND outcome = 'active'
            ORDER BY run_number DESC LIMIT 1
        ''', (tid,))
        active_run = cursor.fetchone()
        
        if active_run:
            run_id, started_at_str = active_run
            # Calculate duration
            duration = 0.0
            try:
                # Remove Z and parse
                start_dt = datetime.datetime.fromisoformat(started_at_str.replace("Z", ""))
                end_dt = datetime.datetime.utcnow()
                duration = (end_dt - start_dt).total_seconds()
            except Exception:
                pass
                
            cursor.execute('''
                UPDATE kenbun_kanban_runs 
                SET outcome = 'completed', ended_at = ?, duration_seconds = ?, summary = ?, metadata = ?
                WHERE id = ?
            ''', (now_str, duration, summary, metadata_str, run_id))
            
        # Update task status
        cursor.execute('''
            UPDATE kenbun_kanban_tasks 
            SET status = 'done', updated_at = ?
            WHERE id = ?
        ''', (now_str, tid))
        
        conn.commit()
        return json.dumps({"status": "success", "message": f"Task '{tid}' marked as done."}, indent=2)
    except Exception as e:
        logger.error(f"Error in kanban_complete: {e}")
        return json.dumps({"status": "error", "message": str(e)}, indent=2)
    finally:
        conn.close()

@sovereign_tool(name="kanban_block", category="Strategy")
def kanban_block(task_id: str = "", reason: str = "", error: str = "") -> str:
    """
    Block a task and record the block reason or execution error.
    
    Args:
        task_id: The ID of the task. Defaults to KENBUN_KANBAN_TASK env var.
        reason: Plain text description of why the worker blocked (e.g. human feedback requested).
        error: Optional traceback or error string for technical failures.
    """
    try:
        tid = resolve_task_id(task_id)
    except ValueError as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)
        
    if not reason:
        return json.dumps({"status": "error", "message": "Reason is required to block a task."}, indent=2)
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM kenbun_kanban_tasks WHERE id = ?", (tid,))
        if not cursor.fetchone():
            return json.dumps({"status": "error", "message": f"Task '{tid}' not found."}, indent=2)
            
        now_str = datetime.datetime.utcnow().isoformat() + "Z"
        
        # Update active run if exists
        cursor.execute('''
            SELECT id, started_at FROM kenbun_kanban_runs 
            WHERE task_id = ? AND outcome = 'active'
            ORDER BY run_number DESC LIMIT 1
        ''', (tid,))
        active_run = cursor.fetchone()
        
        if active_run:
            run_id, started_at_str = active_run
            duration = 0.0
            try:
                start_dt = datetime.datetime.fromisoformat(started_at_str.replace("Z", ""))
                end_dt = datetime.datetime.utcnow()
                duration = (end_dt - start_dt).total_seconds()
            except Exception:
                pass
                
            cursor.execute('''
                UPDATE kenbun_kanban_runs 
                SET outcome = 'blocked', ended_at = ?, duration_seconds = ?, error = ?, summary = ?
                WHERE id = ?
            ''', (now_str, duration, error or reason, reason, run_id))
            
        # Update task status to blocked
        cursor.execute('''
            UPDATE kenbun_kanban_tasks 
            SET status = 'blocked', updated_at = ?
            WHERE id = ?
        ''', (now_str, tid))
        
        conn.commit()
        return json.dumps({"status": "success", "message": f"Task '{tid}' transitioned to blocked."}, indent=2)
    except Exception as e:
        logger.error(f"Error in kanban_block: {e}")
        return json.dumps({"status": "error", "message": str(e)}, indent=2)
    finally:
        conn.close()

@sovereign_tool(name="kanban_unblock", category="Strategy")
def kanban_unblock(task_id: str) -> str:
    """
    Unblock a blocked task, allowing the dispatcher to queue it again.
    
    Args:
        task_id: The ID of the task to unblock.
    """
    if not task_id:
        return json.dumps({"status": "error", "message": "Task ID is required."}, indent=2)
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT parent_id FROM kenbun_kanban_tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if not row:
            return json.dumps({"status": "error", "message": f"Task '{task_id}' not found."}, indent=2)
            
        parent_id = row[0]
        
        # Decide if status goes to ready or todo based on parents
        status = "ready"
        if parent_id:
            cursor.execute("SELECT status FROM kenbun_kanban_tasks WHERE id = ?", (parent_id,))
            p_row = cursor.fetchone()
            if p_row and p_row[0] != "done":
                status = "todo"
                
        now_str = datetime.datetime.utcnow().isoformat() + "Z"
        cursor.execute('''
            UPDATE kenbun_kanban_tasks 
            SET status = ?, updated_at = ?
            WHERE id = ?
        ''', (status, now_str, task_id))
        
        conn.commit()
        return json.dumps({"status": "success", "message": f"Task '{task_id}' unblocked and moved to '{status}'."}, indent=2)
    except Exception as e:
        logger.error(f"Error in kanban_unblock: {e}")
        return json.dumps({"status": "error", "message": str(e)}, indent=2)
    finally:
        conn.close()

@sovereign_tool(name="kanban_heartbeat", category="Strategy")
def kanban_heartbeat(task_id: str = "", note: str = "") -> str:
    """
    Record progress comments/notes for an active run.
    
    Args:
        task_id: The ID of the task. Defaults to KENBUN_KANBAN_TASK env var.
        note: Progress comment.
    """
    try:
        tid = resolve_task_id(task_id)
    except ValueError as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)
        
    if not note:
        return json.dumps({"status": "error", "message": "Note/comment is required."}, indent=2)
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Add comment to task's comments array
        cursor.execute("SELECT comments FROM kenbun_kanban_tasks WHERE id = ?", (tid,))
        row = cursor.fetchone()
        if not row:
            return json.dumps({"status": "error", "message": f"Task '{tid}' not found."}, indent=2)
            
        try:
            comments = json.loads(row[0] or "[]")
        except Exception:
            comments = []
            
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        comments.append({
            "timestamp": timestamp,
            "note": note
        })
        
        cursor.execute('''
            UPDATE kenbun_kanban_tasks 
            SET comments = ?, updated_at = ?
            WHERE id = ?
        ''', (json.dumps(comments), timestamp, tid))
        
        # Update active run's metadata heartbeats if run exists
        cursor.execute('''
            SELECT id, metadata FROM kenbun_kanban_runs 
            WHERE task_id = ? AND outcome = 'active'
            ORDER BY run_number DESC LIMIT 1
        ''', (tid,))
        active_run = cursor.fetchone()
        
        if active_run:
            run_id, meta_str = active_run
            try:
                metadata = json.loads(meta_str or "{}")
            except Exception:
                metadata = {}
            if "heartbeats" not in metadata:
                metadata["heartbeats"] = []
            metadata["heartbeats"].append({
                "timestamp": timestamp,
                "note": note
            })
            cursor.execute('''
                UPDATE kenbun_kanban_runs 
                SET metadata = ? 
                WHERE id = ?
            ''', (json.dumps(metadata), run_id))
            
        conn.commit()
        return json.dumps({"status": "success", "message": f"Heartbeat recorded for '{tid}'."}, indent=2)
    except Exception as e:
        logger.error(f"Error in kanban_heartbeat: {e}")
        return json.dumps({"status": "error", "message": str(e)}, indent=2)
    finally:
        conn.close()

@sovereign_tool(name="kanban_comment", category="Strategy")
def kanban_comment(task_id: str = "", comment: str = "") -> str:
    """
    Append a comment to a task's progress log.
    
    Args:
        task_id: The ID of the task. Defaults to KENBUN_KANBAN_TASK env var.
        comment: The comment message to append.
    """
    # Shares kanban_heartbeat's storage (both append to the task's comments
    # array), but relabel the response: replying "Heartbeat recorded" to a
    # comment call reads as though the comment text was dropped.
    raw = kanban_heartbeat(task_id, comment)
    try:
        payload = json.loads(raw)
    except Exception:
        return raw
    if payload.get("status") == "success":
        payload["message"] = payload.get("message", "").replace(
            "Heartbeat recorded", "Comment recorded")
    return json.dumps(payload, indent=2)

@sovereign_tool(name="kanban_link", category="Strategy")
def kanban_link(task_id: str, parent_id: str) -> str:
    """
    Establish a dependency relationship where task_id depends on parent_id.
    
    Args:
        task_id: The task that is dependent.
        parent_id: The parent task.
    """
    if not task_id or not parent_id:
        return json.dumps({"status": "error", "message": "Both task_id and parent_id are required."}, indent=2)
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Verify both exist
        cursor.execute("SELECT id FROM kenbun_kanban_tasks WHERE id = ?", (task_id,))
        if not cursor.fetchone():
            return json.dumps({"status": "error", "message": f"Task '{task_id}' not found."}, indent=2)
            
        cursor.execute("SELECT id FROM kenbun_kanban_tasks WHERE id = ?", (parent_id,))
        if not cursor.fetchone():
            return json.dumps({"status": "error", "message": f"Parent task '{parent_id}' not found."}, indent=2)
            
        now_str = datetime.datetime.utcnow().isoformat() + "Z"
        
        # Set dependency
        cursor.execute('''
            UPDATE kenbun_kanban_tasks 
            SET parent_id = ?, status = 'todo', updated_at = ?
            WHERE id = ?
        ''', (parent_id, now_str, task_id))
        
        conn.commit()
        return json.dumps({"status": "success", "message": f"Linked task '{task_id}' to parent '{parent_id}'."}, indent=2)
    except Exception as e:
        logger.error(f"Error in kanban_link: {e}")
        return json.dumps({"status": "error", "message": str(e)}, indent=2)
    finally:
        conn.close()
