import os
import sqlite3
import datetime
import tempfile
import json
from unittest.mock import patch, MagicMock
import pytest

from tools.strategy.cronjob_tool import cronjob, calculate_next_run
from services.scheduler_daemon import ChronosDaemon, is_oneshot

@pytest.fixture(scope="module")
def test_db():
    # Setup isolated temp database
    temp_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(temp_fd)
    
    # Pre-initialize table
    conn = sqlite3.connect(db_path)
    from tools.strategy.cronjob_tool import ensure_cron_table_exists
    ensure_cron_table_exists(conn)
    conn.close()
    
    yield db_path
    
    # Teardown
    try:
        os.unlink(db_path)
    except Exception:
        pass

def test_schedule_calculations():
    now = datetime.datetime(2026, 6, 23, 12, 0, 0)
    
    # 1. One-shot relative delays
    dt_30m = calculate_next_run("30m", now)
    assert dt_30m == now + datetime.timedelta(minutes=30)
    
    dt_2h = calculate_next_run("2h", now)
    assert dt_2h == now + datetime.timedelta(hours=2)
    
    dt_1d = calculate_next_run("1d", now)
    assert dt_1d == now + datetime.timedelta(days=1)
    
    # 2. Recurring intervals
    dt_every_15m = calculate_next_run("every 15m", now)
    assert dt_every_15m == now + datetime.timedelta(minutes=15)
    
    dt_every_3h = calculate_next_run("every 3h", now)
    assert dt_every_3h == now + datetime.timedelta(hours=3)
    
    dt_every_2d = calculate_next_run("every 2d", now)
    assert dt_every_2d == now + datetime.timedelta(days=2)
    
    # 3. ISO timestamps
    iso_str = "2026-06-25T15:30:00"
    dt_iso = calculate_next_run(iso_str, now)
    assert dt_iso == datetime.datetime(2026, 6, 25, 15, 30, 0)
    
    # 4. Cron expression
    dt_cron = calculate_next_run("0 9 * * *", now)
    assert dt_cron.hour == 9
    assert dt_cron.minute == 0
    assert dt_cron.second == 0
    assert dt_cron > now

def test_is_oneshot():
    assert is_oneshot("30m") is True
    assert is_oneshot("2h") is True
    assert is_oneshot("2026-06-25T15:30:00") is True
    assert is_oneshot("every 30m") is False
    assert is_oneshot("0 9 * * *") is False

def test_cronjob_lifecycle(test_db):
    with patch("tools.strategy.cronjob_tool.LOCAL_DB_PATH", test_db):
        # 1. Create a job
        res_create = cronjob(
            action="create",
            name="Test Watchdog",
            schedule="every 30m",
            prompt="Check memory state",
            delivery_targets="slack,discord",
            enabled_toolsets="web,file"
        )
        data_create = json.loads(res_create)
        assert data_create["status"] == "success"
        job_id = data_create["job_id"]
        assert job_id.startswith("kb_")
        
        # 2. List jobs
        res_list = cronjob(action="list")
        jobs = json.loads(res_list)
        assert len(jobs) >= 1
        test_job = [j for j in jobs if j["id"] == job_id][0]
        assert test_job["name"] == "Test Watchdog"
        assert test_job["schedule"] == "every 30m"
        assert test_job["status"] == "active"
        assert "slack" in test_job["delivery_targets"]
        assert "web" in test_job["enabled_toolsets"]
        
        # 3. Update job
        res_update = cronjob(
            action="update",
            job_id=job_id,
            prompt="Revised check memory state",
            schedule="every 1h"
        )
        assert "success" in res_update
        
        res_list2 = cronjob(action="list")
        jobs2 = json.loads(res_list2)
        test_job2 = [j for j in jobs2 if j["id"] == job_id][0]
        assert test_job2["prompt"] == "Revised check memory state"
        assert test_job2["schedule"] == "every 1h"
        
        # 4. Pause job
        res_pause = cronjob(action="pause", job_id=job_id)
        assert "success" in res_pause
        
        res_list3 = cronjob(action="list")
        test_job3 = [j for j in json.loads(res_list3) if j["id"] == job_id][0]
        assert test_job3["status"] == "paused"
        
        # 5. Resume job
        res_resume = cronjob(action="resume", job_id=job_id)
        assert "success" in res_resume
        
        res_list4 = cronjob(action="list")
        test_job4 = [j for j in json.loads(res_list4) if j["id"] == job_id][0]
        assert test_job4["status"] == "active"
        
        # 6. Run job (forces immediate execution next tick)
        res_run = cronjob(action="run", job_id=job_id)
        assert "success" in res_run
        
        # 7. Remove job
        res_remove = cronjob(action="remove", job_id=job_id)
        assert "success" in res_remove
        
        res_list5 = cronjob(action="list")
        jobs5 = json.loads(res_list5)
        assert len([j for j in jobs5 if j["id"] == job_id]) == 0

@pytest.mark.asyncio
async def test_scheduler_daemon_tick(test_db):
    # Setup a job that is due to run
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO kenbun_cron_jobs (
            id, name, schedule, prompt, status, next_run_at
        ) VALUES ('kb_test_due', 'Due Task', '30m', 'Do something', 'active', '1970-01-01T00:00:00Z')
    ''')
    conn.commit()
    conn.close()
    
    # Mock loop and daemon
    mock_loop = MagicMock()
    daemon = ChronosDaemon(mock_loop)
    
    # Run the tick in patched DB
    with patch("services.scheduler_daemon.LOCAL_DB_PATH", test_db):
        with patch("services.scheduler_daemon.execute_cron_job") as mock_exec:
            await daemon.tick()
            
            # Verify database was updated and execute called
            conn = sqlite3.connect(test_db)
            cursor = conn.cursor()
            cursor.execute("SELECT status, next_run_at FROM kenbun_cron_jobs WHERE id = 'kb_test_due'")
            row = cursor.fetchone()
            assert row[0] == 'completed'
            assert row[1] is None
            conn.close()
