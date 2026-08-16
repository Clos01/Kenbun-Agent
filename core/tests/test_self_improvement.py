import pytest
import uuid
from services.self_improvement_daemon import (
    optimize_agent_prompt,
    run_self_improvement_cycle,
    get_agent_prompt
)
from tools.memory.hardware_bridge import hardware_bridge

@pytest.mark.unit
def test_optimize_agent_prompt(monkeypatch):
    # Mock call_gemini_pro to return a dummy prompt
    expected_prompt = "You are a highly optimized coding agent that uses detailed reasoning loops."
    
    def mock_call_gemini_pro(prompt, temperature=0.5):
        return f"```markdown\n{expected_prompt}\n```"
        
    monkeypatch.setattr("services.self_improvement_daemon.call_gemini_pro", mock_call_gemini_pro)

    result = optimize_agent_prompt(
        agent_id="coder",
        original_prompt="You are a coder.",
        failed_task="Implement JWT token auth.",
        failed_output="def auth(): pass",
        eval_score=0.5,
        feedback="The implementation is empty and lacks validation logic."
    )
    
    assert result == expected_prompt

@pytest.mark.unit
def test_run_self_improvement_cycle(monkeypatch):
    # Force has_postgres to False for simple SQLite isolation
    original_detect = hardware_bridge.detect_capabilities
    def mock_detect():
        c = original_detect().copy()
        c["has_postgres"] = False
        return c
    monkeypatch.setattr(hardware_bridge, "detect_capabilities", mock_detect)

    # Mock call_gemini_pro
    expected_prompt = "You are an optimized coder agent."
    monkeypatch.setattr(
        "services.self_improvement_daemon.call_gemini_pro",
        lambda prompt, temperature=0.5: f"```markdown\n{expected_prompt}\n```"
    )

    # 1. Insert a poor evaluation (score: 0.6) for coder agent
    run_id = f"test-improve-run-{uuid.uuid4()}"
    eval_data = {
        "agent_id": "coder",
        "task_id": "Implement login feature",
        "run_id": run_id,
        "prompt_hash": "hash-old",
        "score": 0.6,
        "speed_sec": 2.5,
        "token_cost": 0.01,
        "compliance_score": 1.0,
        "eval_feedback": "The login validation was missing secure hashing algorithms."
    }
    hardware_bridge.save_evaluation(eval_data)

    # Mock TokenGovernor budget
    from tools.strategy.token_governor import token_governor
    monkeypatch.setattr(token_governor, "get_remaining_budget", lambda: 10.0)

    # Run improvement cycle
    count = run_self_improvement_cycle()
    assert count >= 1

    # Verify updated prompt is now the latest for coder
    latest_prompt = get_agent_prompt("coder")
    assert latest_prompt == expected_prompt
