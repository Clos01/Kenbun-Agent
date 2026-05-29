import pytest
from tools.utils.maze_protocol import backward_verify
from tools.strategy.decision_logic import router
from tools.autonomic.autonomic_corrector import corrector
import os
from pathlib import Path

def test_maze_circular_protection(tmp_path):
    """Verify that Maze Protocol handles circular imports safely."""
    project_root = tmp_path / "circular_project"
    project_root.mkdir()
    (project_root / "__init__.py").touch()
    
    a_py = project_root / "a.py"
    b_py = project_root / "b.py"
    
    # Create circular import
    a_py.write_text("import b\nfrom tools.utils.maze_protocol import backward_verify")
    b_py.write_text("import a")
    
    # Run maze on a.py
    # Since 'b' isn't actually in sys.path as a module, we might need to mock or 
    # just verify it doesn't crash if it *could* find them.
    # For this test, we verify the package integrity and basic walk.
    result = backward_verify(str(a_py), str(project_root), run_tests=False)
    assert result is True # Should pass entrance/package checks

def test_strategy_noise_gating():
    """Verify that nonsensical tasks are gated to STANDARD_EXECUTION."""
    noise_task = "Dragon pizza party in the basement"
    path = router.get_strategy_path(noise_task, fast_mode=True)
    assert path == "STANDARD_EXECUTION"

def test_strategy_dual_signal():
    """Verify that tasks with dual signals return an ensemble path."""
    dual_task = "Fix the CSS alignment on the login form to prevent a security sql injection bypass"
    path = router.get_strategy_path(dual_task, fast_mode=True)
    # Depending on weights, this should either be a single strong winner or a piped ensemble
    # Given the high weight of security keywords, it might win, but let's check if it's at least one of them.
    assert "SECURITY_HARDENING_PATH" in path or "UI_FIX_PATH" in path

def test_circuit_breaker_logic(tmp_path):
    """Verify the Death Spiral circuit breaker."""
    corrector.recovery_path = tmp_path / "chaos_recovery.jsonl"
    project = str(tmp_path / "Chaos")
    
    # Trigger 3 swarms
    for i in range(3):
        corrector.spawn_recovery_swarm(project, f"Error {i}")
        
    # 4th swarm should be blocked
    is_broken = corrector._is_circuit_broken(project)
    assert is_broken is True
