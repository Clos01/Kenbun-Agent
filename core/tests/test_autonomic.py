import pytest
import json
import os
import time
from pathlib import Path
from tools.autonomic.autonomic_corrector import corrector
from tools.utils.workspace_manager import workspace_manager

def test_autonomic_monitoring(tmp_path):
    """Verify that the corrector detects error signatures in logs."""
    # Setup mock project and log
    mock_project = tmp_path / "mock_project"
    mock_project.mkdir()
    log_dir = mock_project / "logs"
    log_dir.mkdir()
    error_log = log_dir / "error.log"
    
    # Inject 500 error
    error_log.write_text("2026-05-06 22:00:00 [ERROR] 500 Internal Server Error in /api/v1/auth\n")
    
    # Register mock project by mocking get_projects
    from unittest.mock import patch
    with patch.object(workspace_manager, "get_projects", return_value=[str(mock_project)]):
        # Mock the recovery log path to a temp file
        corrector.recovery_path = tmp_path / "recovery_events.jsonl"
        
        # Run cycle
        corrector.monitor_workspace_logs()
    
    # Verify event was triggered
    assert corrector.recovery_path.exists()
    with open(corrector.recovery_path, "r") as f:
        event = json.loads(f.readline())
        assert event["project_path"] == str(mock_project)
        assert "500 Internal Server Error" in event["error_signal"]
        assert event["status"] == "triggered"

def test_recent_recovery_throttle(tmp_path):
    """Verify that the corrector prevents rapid re-spawning of swarms for the same error."""
    mock_path = str(tmp_path / "Mock")
    error = "500 Error"
    
    corrector.recovery_path = tmp_path / "throttle_events.jsonl"
    
    # Trigger first event
    corrector.spawn_recovery_swarm(mock_path, error)
    
    # Try to trigger again immediately
    throttle = corrector._is_recent_recovery(mock_path, error)
    assert throttle is True
