import os
import sqlite3
import tempfile
import json
from unittest.mock import patch
import pytest

from tools.strategy.blueprint_tool import blueprint

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

def test_blueprint_list():
    res = blueprint(action="list")
    blueprints = json.loads(res)
    assert len(blueprints) >= 3
    names = [bp["name"] for bp in blueprints]
    assert "morning-brief" in names
    assert "important-mail" in names
    assert "weekly-review" in names

def test_blueprint_get():
    res = blueprint(action="get", name="morning-brief")
    bp = json.loads(res)
    assert bp["name"] == "morning-brief"
    assert bp["default_schedule"] == "0 8 * * *"
    assert len(bp["inputs"]) == 2

def test_blueprint_schedule(test_db):
    with patch("tools.strategy.cronjob_tool.LOCAL_DB_PATH", test_db):
        res = blueprint(
            action="schedule",
            name="morning-brief",
            params="time=08:00,deliver=slack",
            job_name="my_morning_job"
        )
        data = json.loads(res)
        assert data["status"] == "success"
        assert data["schedule"] == "0 8 * * *"
        
        # Verify it created a cronjob in the test database
        from tools.strategy.cronjob_tool import cronjob
        res_list = cronjob(action="list")
        jobs = json.loads(res_list)
        assert len(jobs) == 1
        assert jobs[0]["name"] == "my_morning_job"
        assert "slack" in jobs[0]["delivery_targets"]
        assert "Perform the Morning Briefing" in jobs[0]["prompt"]
