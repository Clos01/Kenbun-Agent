import json
import tempfile
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Insert scripts/ directory into sys.path to import terminal_chat
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
import terminal_chat

@pytest.fixture
def temp_brain_health():
    with tempfile.TemporaryDirectory() as tmpdir:
        original = terminal_chat.active_brain_health_dir
        terminal_chat.active_brain_health_dir = Path(tmpdir)
        yield Path(tmpdir)
        terminal_chat.active_brain_health_dir = original

def test_goal_state_persistence(temp_brain_health):
    # Verify that get_goal_state_path resolves correctly
    path = terminal_chat.get_goal_state_path()
    assert path is not None
    assert path.name == "goal_state.json"
    
    # Verify load returns None when file does not exist
    assert terminal_chat.load_goal_state() is None
    
    # Save a test state
    state = {
        "active_goal": "Test Goal",
        "turns_used": 2,
        "max_turns": 20,
        "status": "active",
        "subgoals": ["subgoal A"],
        "contract": {"outcome": "done"}
    }
    terminal_chat.save_goal_state(state)
    
    # Load and verify
    loaded = terminal_chat.load_goal_state()
    assert loaded == state

def test_is_pid_running():
    import os
    current_pid = os.getpid()
    assert terminal_chat.is_pid_running(current_pid) is True
    # PID 999999 is highly unlikely to be running
    assert terminal_chat.is_pid_running(999999) is False

@patch("requests.post")
def test_call_auxiliary_llm(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"done": true, "reason": "Test reason"}'
                }
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp
    
    res = terminal_chat.call_auxiliary_llm(
        llm_url="http://localhost:1234/v1",
        llm_model="test-model",
        system_prompt="Test System",
        user_message="Test User"
    )
    assert res == '{"done": true, "reason": "Test reason"}'
    mock_post.assert_called_once()

@patch("requests.post")
def test_run_goal_judge(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"done": true, "reason": "Goal satisfied."}'
                }
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp
    
    goal_state = {
        "active_goal": "Test Goal",
        "subgoals": [],
        "contract": {}
    }
    
    verdict = terminal_chat.run_goal_judge(
        goal_state,
        last_response="I have finished creating the note.",
        llm_url="http://localhost:1234/v1",
        llm_model="test-model",
        model_tier="standard"
    )
    assert verdict["done"] is True
    assert verdict["reason"] == "Goal satisfied."

@patch("requests.post")
def test_draft_completion_contract(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "active_goal": "Migrate auth",
                        "contract": {
                            "outcome": "JWT auth working",
                            "verification": "pytest tests/auth.py",
                            "constraints": "Keep login shape",
                            "boundaries": "services/auth",
                            "stop_when": "migration needed"
                        }
                    })
                }
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp
    
    draft = terminal_chat.draft_completion_contract("Migrate auth to JWT", "http://localhost:1234/v1", "test-model")
    assert draft["active_goal"] == "Migrate auth"
    assert draft["contract"]["outcome"] == "JWT auth working"
    assert draft["contract"]["verification"] == "pytest tests/auth.py"
