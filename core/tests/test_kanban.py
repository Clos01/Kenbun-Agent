import os
import sqlite3
import datetime
import tempfile
import json
import asyncio
from unittest.mock import patch, MagicMock
import pytest

from tools.strategy.kanban_tools import (
    kanban_create, kanban_show, kanban_list, kanban_complete,
    kanban_block, kanban_unblock, kanban_heartbeat, kanban_comment, kanban_link
)
from services.kanban_dispatcher import KanbanDispatcher

@pytest.fixture(scope="function")
def test_db():
    # Setup isolated temp database
    temp_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(temp_fd)
    
    # Pre-initialize tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kenbun_kanban_tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT,
            assignee TEXT,
            tenant TEXT,
            priority INTEGER DEFAULT 0,
            parent_id TEXT,
            status TEXT DEFAULT 'triage',
            max_retries INTEGER DEFAULT 3,
            comments TEXT DEFAULT '[]',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kenbun_kanban_runs (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            run_number INTEGER NOT NULL,
            outcome TEXT NOT NULL,
            assignee TEXT,
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            ended_at TEXT,
            duration_seconds REAL,
            summary TEXT,
            metadata TEXT,
            error TEXT,
            pid INTEGER,
            FOREIGN KEY(task_id) REFERENCES kenbun_kanban_tasks(id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Teardown
    try:
        os.unlink(db_path)
    except Exception:
        pass

def test_kanban_create_and_show(test_db):
    with patch("tools.strategy.kanban_tools.LOCAL_DB_PATH", test_db):
        # 1. Create a task
        res = kanban_create(
            title="Design database schema",
            body="Create migration scripts for Kanban",
            assignee="coder",
            tenant="auth",
            priority=5
        )
        data = json.loads(res)
        assert data["status"] == "success"
        task_id = data["id"]
        assert task_id.startswith("t_")
        
        # 2. Show the task
        res_show = kanban_show(task_id)
        task_data = json.loads(res_show)
        assert task_data["id"] == task_id
        assert task_data["title"] == "Design database schema"
        assert task_data["assignee"] == "coder"
        assert task_data["priority"] == 5
        assert task_data["status"] == "triage"
        assert task_data["worker_context"]["prior_attempts"] == []

def test_kanban_complete_and_runs(test_db):
    with patch("tools.strategy.kanban_tools.LOCAL_DB_PATH", test_db):
        res = kanban_create(title="API Implementation", assignee="coder", status="running")
        task_id = json.loads(res)["id"]
        
        # Create an active run manually for completion mapping
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        run_id = "r_123"
        cursor.execute('''
            INSERT INTO kenbun_kanban_runs (id, task_id, run_number, outcome, assignee, started_at)
            VALUES (?, ?, 1, 'active', 'coder', ?)
        ''', (run_id, task_id, datetime.datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        
        # Complete task
        res_complete = kanban_complete(
            task_id=task_id,
            summary="API registers endpoints and passes all mock tests",
            metadata=json.dumps({"changed_files": ["api.py"]})
        )
        assert json.loads(res_complete)["status"] == "success"
        
        # Show task & verify run is updated
        res_show = kanban_show(task_id)
        task_data = json.loads(res_show)
        assert task_data["status"] == "done"
        assert len(task_data["runs"]) == 1
        assert task_data["runs"][0]["outcome"] == "completed"
        assert task_data["runs"][0]["summary"] == "API registers endpoints and passes all mock tests"
        assert task_data["runs"][0]["metadata"]["changed_files"] == ["api.py"]

def test_kanban_block_and_unblock(test_db):
    with patch("tools.strategy.kanban_tools.LOCAL_DB_PATH", test_db):
        res = kanban_create(title="Write documentation", assignee="coder", status="running")
        task_id = json.loads(res)["id"]
        
        # Create active run
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO kenbun_kanban_runs (id, task_id, run_number, outcome, started_at) VALUES ('r_blk', ?, 1, 'active', '2026-06-23T12:00:00')", (task_id,))
        conn.commit()
        conn.close()
        
        # Block
        res_block = kanban_block(task_id=task_id, reason="Missing product specs")
        assert json.loads(res_block)["status"] == "success"
        
        res_show = json.loads(kanban_show(task_id))
        assert res_show["status"] == "blocked"
        assert res_show["runs"][0]["outcome"] == "blocked"
        assert res_show["runs"][0]["summary"] == "Missing product specs"
        
        # Unblock
        res_unblock = kanban_unblock(task_id)
        assert json.loads(res_unblock)["status"] == "success"
        assert json.loads(kanban_show(task_id))["status"] == "ready"

def test_kanban_heartbeat(test_db):
    with patch("tools.strategy.kanban_tools.LOCAL_DB_PATH", test_db):
        res = kanban_create(title="Deploy pipeline", assignee="coder", status="running")
        task_id = json.loads(res)["id"]
        
        # Write active run
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO kenbun_kanban_runs (id, task_id, run_number, outcome, started_at) VALUES ('r_hb', ?, 1, 'active', '2026-06-23T12:00:00')", (task_id,))
        conn.commit()
        conn.close()
        
        # Record heartbeat
        res_hb = kanban_heartbeat(task_id=task_id, note="Docker image is building...")
        assert json.loads(res_hb)["status"] == "success"
        
        res_show = json.loads(kanban_show(task_id))
        assert len(res_show["comments"]) == 1
        assert res_show["comments"][0]["note"] == "Docker image is building..."
        assert res_show["runs"][0]["metadata"]["heartbeats"][0]["note"] == "Docker image is building..."

def test_kanban_link_and_dependencies(test_db):
    with patch("tools.strategy.kanban_tools.LOCAL_DB_PATH", test_db):
        res_parent = kanban_create(title="Parent Schema", assignee="coder", status="done")
        parent_id = json.loads(res_parent)["id"]
        
        res_child = kanban_create(title="Child Code", assignee="coder", status="todo")
        child_id = json.loads(res_child)["id"]
        
        # Link child to parent
        res_link = kanban_link(task_id=child_id, parent_id=parent_id)
        assert json.loads(res_link)["status"] == "success"
        
        # Unblock should move it directly to ready because parent is done
        res_unblock = kanban_unblock(child_id)
        assert json.loads(res_show := kanban_show(child_id))["status"] == "ready"

def test_dispatcher_dependency_promotion(test_db):
    with patch("services.kanban_dispatcher.LOCAL_DB_PATH", test_db):
        # Create parent (not done yet) and child
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO kenbun_kanban_tasks (id, title, status) VALUES ('parent', 'Parent Task', 'running')")
        cursor.execute("INSERT INTO kenbun_kanban_tasks (id, title, status, parent_id) VALUES ('child', 'Child Task', 'todo', 'parent')")
        conn.commit()
        conn.close()
        
        dispatcher = KanbanDispatcher(MagicMock())
        
        # 1. Tick: Child stays in todo because parent is not done
        dispatcher._promote_dependencies()
        
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM kenbun_kanban_tasks WHERE id = 'child'")
        assert cursor.fetchone()[0] == "todo"
        
        # 2. Mark parent done, tick dispatcher
        cursor.execute("UPDATE kenbun_kanban_tasks SET status = 'done' WHERE id = 'parent'")
        conn.commit()
        conn.close()
        
        dispatcher._promote_dependencies()
        
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM kenbun_kanban_tasks WHERE id = 'child'")
        assert cursor.fetchone()[0] == "ready"
        conn.close()

def test_dispatcher_crash_recovery_and_circuit_breaker(test_db):
    with patch("services.kanban_dispatcher.LOCAL_DB_PATH", test_db):
        # Create a task currently running on a mock process PID that does not exist
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO kenbun_kanban_tasks (id, title, status, max_retries) VALUES ('task_crash', 'Crash Task', 'running', 2)")
        
        # Insert run 1 with dead PID 999999
        cursor.execute('''
            INSERT INTO kenbun_kanban_runs (id, task_id, run_number, outcome, started_at, pid)
            VALUES ('run_1', 'task_crash', 1, 'active', '2026-06-23T12:00:00', 999999)
        ''')
        conn.commit()
        conn.close()
        
        dispatcher = KanbanDispatcher(MagicMock())
        
        # 1. Tick: Detect crash on run 1, promote back to ready because run_count (1) < max_retries (2)
        dispatcher._recover_crashed_workers()
        
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM kenbun_kanban_tasks WHERE id = 'task_crash'")
        assert cursor.fetchone()[0] == "ready"
        cursor.execute("SELECT outcome FROM kenbun_kanban_runs WHERE id = 'run_1'")
        assert cursor.fetchone()[0] == "crashed"
        
        # Let's move it to running again with run 2 (active on dead PID 999999)
        cursor.execute("UPDATE kenbun_kanban_tasks SET status = 'running' WHERE id = 'task_crash'")
        cursor.execute('''
            INSERT INTO kenbun_kanban_runs (id, task_id, run_number, outcome, started_at, pid)
            VALUES ('run_2', 'task_crash', 2, 'active', '2026-06-23T12:00:00', 999999)
        ''')
        conn.commit()
        conn.close()
        
        # 2. Tick: Detect crash on run 2, since run_count (2) >= max_retries (2), block it (circuit breaker)
        dispatcher._recover_crashed_workers()
        
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM kenbun_kanban_tasks WHERE id = 'task_crash'")
        assert cursor.fetchone()[0] == "blocked"
        
        cursor.execute("SELECT outcome FROM kenbun_kanban_runs WHERE task_id = 'task_crash' ORDER BY run_number DESC LIMIT 1")
        assert cursor.fetchone()[0] == "gave_up"
        conn.close()
