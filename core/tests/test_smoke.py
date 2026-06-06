"""
Layer 1 — Smoke tests. Guarantees the core engine imports cleanly.
This file would have caught the import drift fixed in 2026-05-04 audit.
Run on every commit: `pytest -m smoke`
"""
import importlib
import pytest

CRITICAL_MODULES = [
    # Core engine
    "core.tools.infrastructure.orchestrator",
    "core.tools.infrastructure.server",
    "core.tools.infrastructure.api_server",
    "core.tools.infrastructure.agents",
    "core.tools.infrastructure.config",
    "core.tools.infrastructure.design_bridge",
    # Memory layer
    "core.tools.memory.knowledge_manager",
    "core.tools.memory.code_indexer",
    "core.tools.memory.chroma_db_connect",
    "core.tools.memory.repo_mapper",
    # Audit layer
    "core.tools.audit.gemini_reviewer",
    "core.tools.audit.supervisor_agent",
    "core.tools.audit.guardrail_agent",
    "core.tools.audit.reflection_agent",
    "core.tools.audit.discovery_agent",
    # Strategy layer
    "core.tools.strategy.decision_logic",
    "core.tools.strategy.token_governor",
    "core.tools.strategy.strategy_manager",
    # Execution
    "core.tools.execution.sandbox_runner",
    # Utils
    "core.tools.utils.error_memory",
    "core.tools.utils.backtracker",
    "core.tools.utils.maze_protocol",
    "core.tools.utils.path_utils",
    "core.tools.utils.telemetry",
    "core.tools.utils.bayesian",
]


@pytest.mark.smoke
@pytest.mark.parametrize("module_name", CRITICAL_MODULES)
def test_module_imports(module_name):
    """Every critical module must import without raising."""
    importlib.import_module(module_name)


@pytest.mark.smoke
def test_no_shim_files_exist():
    """Regression guard: ensure deleted shims stay deleted."""
    from core.tools.infrastructure.config import settings
    root = settings.PROJECT_ROOT
    forbidden = [
        root / "tools" / "orchestrator.py",
        root / "tools" / "server.py",
        root / "tools" / "memory" / "error_memory.py",
    ]
    for path in forbidden:
        assert not path.exists(), (
            f"{path.relative_to(root)} was deleted in the 2026-05-04 audit "
            "and must not be recreated. See ARCHITECTURE_AUDIT.md."
        )


@pytest.mark.smoke
def test_error_memory_is_real_implementation():
    """The orchestrator's error memory must be the real ChromaDB-backed one, not a stub."""
    from core.tools.utils import error_memory
    # Real impl has these signatures with full param lists; stub had only (error_message, fix_code)
    import inspect
    sig = inspect.signature(error_memory.remember_fix)
    params = list(sig.parameters.keys())
    assert "solution" in params, "error_memory.remember_fix must accept 'solution' (real impl)"
    assert "file_context" in params, "error_memory.remember_fix must accept 'file_context' (real impl)"


@pytest.mark.smoke
def test_decision_router_loads():
    """Router singleton must initialize and expose expected API."""
    from core.tools.strategy.decision_logic import router
    assert hasattr(router, "get_strategy_path")
    assert hasattr(router, "analyze_task")
    # Should not crash on minimal input
    path = router.get_strategy_path("fix the bug in login.py")
    assert isinstance(path, str)
    assert len(path) > 0