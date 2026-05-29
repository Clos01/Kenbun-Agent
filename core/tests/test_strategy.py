import pytest
from tools.strategy.decision_logic import router

def test_keyword_matching():
    """Verify that System 4b correctly identifies core categories."""
    # UI Task
    ui_task = "Fix the flexbox alignment on the landing page"
    features = router.analyze_task(ui_task)
    assert features["ui_conf"] > 0
    assert "flexbox" in features["matched_all"]
    
    # Security Task
    sec_task = "Check for potential SQL injection in the login form"
    features = router.analyze_task(sec_task)
    assert features["sec_conf"] > 0
    assert "sql" in features["matched_all"]
    
    # Complex Architecture Task
    arch_task = "Refactor the entire module to be more scalable and implement a new strategy"
    features = router.analyze_task(arch_task)
    assert features["arch_conf"] > 0
    assert features["is_complex"] is True

def test_routing_logic():
    """Verify that System 4b routes to the correct sovereign paths."""
    router.recent_paths.clear()
    
    # UI Routing
    ui_task = "Center the div and change the background to glassmorphic"
    path = router.get_strategy_path(ui_task, fast_mode=True)
    assert path in ["UI_COMPONENT_BUILD", "UI_FIX_PATH"]
    
    # Security Routing
    sec_task = "Harden the JWT authentication and prevent data leaks"
    path = router.get_strategy_path(sec_task, fast_mode=True)
    assert path == "SECURITY_HARDENING_PATH"

def test_model_recommendation(monkeypatch):
    """Verify that System 4c recommends appropriate intelligence tiers."""
    recorded_contexts = []
    def mock_select_arm(context):
        recorded_contexts.append(context)
        if context == "SIMPLE":
            return "gemini-3.1-flash-lite-preview"
        else:
            return "gemini-3.1-pro-preview"
            
    monkeypatch.setattr(router.bandit, "select_arm", mock_select_arm)

    # Lite Model
    simple_task = "Fix a typo in the README"
    model = router.recommend_model(simple_task)
    assert "flash" in model # Should be flash or flash-lite
    assert recorded_contexts[-1] == "SIMPLE"
    
    # Pro Model
    complex_task = "Perform a deep security audit of the authentication microservice, check for sql injection and data leaks, then suggest a full architectural rewrite for infinite scalability and modular infrastructure"
    model = router.recommend_model(complex_task)
    assert "pro" in model
    assert recorded_contexts[-1] == "COMPLEX"

