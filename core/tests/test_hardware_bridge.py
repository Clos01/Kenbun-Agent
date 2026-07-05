import pytest
import uuid
import time
from tools.memory.hardware_bridge import hardware_bridge

@pytest.mark.unit
def test_hardware_detection():
    caps = hardware_bridge.detect_capabilities()
    assert isinstance(caps, dict)
    assert "gpu_available" in caps
    assert "ram_gb" in caps
    assert "has_chroma" in caps
    assert "has_postgres" in caps
    assert "tier" in caps

@pytest.mark.unit
def test_sqlite_fallback_evaluations(monkeypatch):
    # Force has_postgres to False to test SQLite fallback path
    original_detect = hardware_bridge.detect_capabilities
    def mock_detect():
        c = original_detect().copy()
        c["has_postgres"] = False
        return c
    monkeypatch.setattr(hardware_bridge, "detect_capabilities", mock_detect)

    run_id = f"test-run-{uuid.uuid4()}"
    eval_data = {
        "agent_id": "test-coder",
        "task_id": "test-task-1",
        "run_id": run_id,
        "prompt_hash": "hash123",
        "score": 0.95,
        "speed_sec": 1.2,
        "token_cost": 0.005,
        "compliance_score": 1.0,
        "eval_feedback": "Excellent code implementation."
    }

    # Save evaluation
    saved = hardware_bridge.save_evaluation(eval_data)
    assert saved is True

    # Retrieve evaluations
    evals = hardware_bridge.get_evaluations("test-coder")
    assert len(evals) > 0
    matched = [e for e in evals if e["run_id"] == run_id]
    assert len(matched) == 1
    assert matched[0]["score"] == 0.95
    assert matched[0]["eval_feedback"] == "Excellent code implementation."

@pytest.mark.unit
def test_sqlite_fallback_prompts(monkeypatch):
    # Force has_postgres to False to test SQLite fallback path
    original_detect = hardware_bridge.detect_capabilities
    def mock_detect():
        c = original_detect().copy()
        c["has_postgres"] = False
        return c
    monkeypatch.setattr(hardware_bridge, "detect_capabilities", mock_detect)

    prompt_hash = f"hash-{uuid.uuid4()}"
    system_prompt = "You are a test coder agent."
    meta_data = {"version": "1.0", "author": "test"}

    # Save prompt
    saved = hardware_bridge.save_prompt(prompt_hash, "test-coder", system_prompt, meta_data)
    assert saved is True

    # Get prompt by hash
    retrieved = hardware_bridge.get_prompt(prompt_hash)
    assert retrieved is not None
    assert retrieved["system_prompt"] == system_prompt
    assert retrieved["meta_data"]["version"] == "1.0"

    # Get latest prompt
    latest = hardware_bridge.get_latest_prompt("test-coder")
    assert latest is not None
    assert latest["system_prompt"] == system_prompt
