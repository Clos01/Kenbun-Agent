import pytest
import json
import time
from pathlib import Path
import sys
import os

from tools.infrastructure.config import settings

from tools.strategy.decision_logic import router, LOG_DIR, DecisionRouter
from tools.audit.supervisor_agent import run_supervisor_audit

def test_router_corruption_recovery():
    """Test 1: Corrupt Weight File Recovery"""
    weight_file = LOG_DIR / "keyword_weights.json"
    original_weights = None
    if weight_file.exists():
        original_weights = weight_file.read_text()
    
    try:
        # Inject corruption
        weight_file.write_text("{ INVALID JSON : --- [")
        
        # Should initialize without crashing
        new_router = DecisionRouter()
        assert new_router is not None
    finally:
        # Restore original weights
        if original_weights:
            weight_file.write_text(original_weights)

def test_router_large_input():
    """Test 2: Memory Stress with large prompt"""
    nuclear_task = "fix " + ("a" * 100000) # 100kb is enough for a unit test
    start = time.time()
    result = router.get_strategy_path(nuclear_task)
    duration = time.time() - start
    assert result is not None
    assert duration < 5.0 # Should be fast and resilient to concurrency noise

@pytest.mark.parametrize("task, expected, label", [
    ("asdfghjkl qwerty uiop", "STANDARD_EXECUTION", "Pure Gibberish"),
    ("I want to order a pepperoni pizza with extra cheese.", "STANDARD_EXECUTION", "Out-of-Domain (Pizza)"),
    ("Tell me a story about a dragon who loves CSS.", "STANDARD_EXECUTION", "Mixed Context (Story)"),
    ("SECURELY BREAK EVERYTHING NOW", "STANDARD_EXECUTION", "Aggressive Signal"),
    ("Make the button color feel like a Friday afternoon.", "STANDARD_EXECUTION", "Abstract UI Concept"),
    ("!!!!!!!!!!!!!!!!!!!!!!!!!!!!", "STANDARD_EXECUTION", "Punctuation Only"),
])
def test_adversarial_routing(task, expected, label):
    """Hallucination & Adversarial Stress Test"""
    router.recent_paths.clear()
    actual = router.get_strategy_path(task)
    assert actual == expected, f"Hallucination in {label}: expected {expected}, got {actual}"

@pytest.mark.asyncio
async def test_supervisor_json_retry():
    """Test the new JSON retry logic in supervisor_agent.py"""
    # We can mock _call_lm_studio to return malformed JSON first, then valid JSON
    import tools.audit.supervisor_agent as supervisor
    
    original_call = supervisor._call_local_senior
    calls = 0
    
    def mock_call(system, user):
        nonlocal calls
        calls += 1
        if calls == 1:
            return "This is not JSON at all, it's just text.", None
        return '{"status": "approved", "risk_level": "low", "critique": "Corrected JSON", "improvement_instruction": "None"}', None
    
    # Mock ensemble to force escalation
    original_ensemble = supervisor.ensemble
    class MockEnsemble:
        async def run_audit(self, prop, code): return {"verdict": "HUNG_JURY"}
    supervisor.ensemble = MockEnsemble()
    # Mock tier 2 to force fallback to Tier 3
    original_cloud = supervisor._tier_2_cloud
    async def mock_cloud(*args, **kwargs): return None
    supervisor._tier_2_cloud = mock_cloud
    
    # Mock adversarial court to None to bypass it in unit test
    original_court = supervisor.adversarial_court
    supervisor.adversarial_court = None
    
    supervisor._call_local_senior = mock_call
    try:
        result = await run_supervisor_audit("Test proposal")
        assert result["status"].upper() == "APPROVED"
        assert calls == 2 # Verify it retried
    finally:
        supervisor._call_local_senior = original_call
        supervisor.ensemble = original_ensemble
        supervisor._tier_2_cloud = original_cloud
        supervisor.adversarial_court = original_court

@pytest.mark.asyncio
async def test_supervisor_fallback():
    """Test the new Gemini fallback in supervisor_agent.py"""
    import tools.audit.supervisor_agent as supervisor
    
    # Mock LM Studio failure
    def mock_fail(system, user):
        return None, "Connection Refused"
    
    # Mock Gemini success
    def mock_gemini(*args, **kwargs):
        return '{"status": "rejected", "risk_level": "high", "critique": "Gemini Fallback Worked", "improvement_instruction": "Use local if possible"}'
    
    original_call = supervisor._call_local_senior
    # Temporarily override the imported gemini_code_review in the module
    original_gemini = supervisor.gemini_code_review
    
    # Mock ensemble to force escalation
    original_ensemble = supervisor.ensemble
    class MockEnsemble:
        async def run_audit(self, prop, code): return {"verdict": "HUNG_JURY"}
    supervisor.ensemble = MockEnsemble()
    
    # Mock adversarial court to None to bypass it in unit test
    original_court = supervisor.adversarial_court
    supervisor.adversarial_court = None
    
    supervisor._call_local_senior = mock_fail
    supervisor.gemini_code_review = mock_gemini
    
    try:
        result = await run_supervisor_audit("Test fallback")
        assert result["status"].upper() == "REJECTED"
        assert "Gemini Fallback" in result["critique"]
    finally:
        supervisor._call_local_senior = original_call
        supervisor.gemini_code_review = original_gemini
        supervisor.ensemble = original_ensemble
        supervisor.adversarial_court = original_court
