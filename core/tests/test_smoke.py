"""
Layer 1 — Smoke tests. Guarantees the core engine imports cleanly.
This file would have caught the import drift fixed in 2026-05-04 audit.
Run on every commit: `pytest -m smoke`

Modules are auto-discovered by walking the core package, so new files are
covered automatically — a hand-curated list is exactly what let the
orchestrator ↔ router_logic circular import slip through (fixed 2026-06-12).
"""
import importlib
import pkgutil
import pytest

import core

# Modules that must never be imported by the test runner itself.
EXCLUDED_PREFIXES = (
    "core.tests",                                  # the tests themselves
    "core.tools.infrastructure.native_ears",       # calls sys.exit() on import when macOS Speech libs are absent
)

# Optional third-party dependencies: a ModuleNotFoundError for exactly these
# distributions is an acceptable skip (extra features), anything else fails.
OPTIONAL_THIRD_PARTY = {
    "watchdog",   # core.tools.execution.shadow_tester
    "telegram",   # core.tools.infrastructure.assembly_voice
    "pypdf",      # core.tools.memory.pdf_ingestor
}


def _discover_modules():
    return sorted(
        m.name
        for m in pkgutil.walk_packages(core.__path__, prefix="core.")
        if not m.name.startswith(EXCLUDED_PREFIXES)
    )


@pytest.mark.smoke
@pytest.mark.parametrize("module_name", _discover_modules())
def test_module_imports(module_name):
    """Every module under core/ must import without raising."""
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        if e.name in OPTIONAL_THIRD_PARTY:
            pytest.skip(f"optional dependency '{e.name}' not installed")
        raise


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