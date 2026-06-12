"""Layer 2 — Tool-rot regression. Pin the public behavior of every MCP tool.

The 2026-06-12 audit (docs/TOOL_AUDIT.md) found four MCP tools silently
broken even though their modules imported cleanly. Type-checking and the
import smoke test couldn't see those bugs because they only surface when
the tool is actually CALLED. This file is the cheap call.

Each test invokes one MCP-exposed function the same way an LLM would, on
the same workspace files, and asserts the response shape. Tests for tools
that depend on external state (Docker daemon, LM Studio, Gemini API) skip
gracefully so this suite always returns a clean signal: green = the local
contract holds; failures point at real rot.

Run:  uv run pytest core/tests/test_tool_surface.py -v
"""
import json
import pytest

from core.tools.infrastructure import server as srv

pytestmark = pytest.mark.tool_rot


def _ok(result):
    """Server tools always return strings; non-empty + no error marker means alive."""
    assert isinstance(result, str), f"expected str, got {type(result).__name__}: {result!r}"
    assert result.strip(), "empty response"
    lowered = result.lower()
    error_markers = ("traceback", "exception:", "validation error", "fatal:")
    assert not any(m in lowered for m in error_markers), result[:200]
    return result


# ── Tools with NO external dependency — must always work ──────────────────

def test_audit_guardrail_blocks_dangerous_code():
    out = _ok(srv.audit_guardrail("import os; os.system(input())", "probe"))
    assert "rejected" in out.lower() or "reject" in out.lower(), out[:200]


def test_audit_guardrail_passes_safe_code():
    out = _ok(srv.audit_guardrail("def add(a, b): return a + b", "probe"))
    assert "approved" in out.lower() or "ok" in out.lower(), out[:200]


def test_think_about_tools_returns_plan():
    out = _ok(srv.think_about_tools("audit cli for tool rot"))
    assert any(kw in out.lower() for kw in ("strategy", "step", "plan", "tool")), out[:200]


def test_scan_repo_returns_repo_map():
    out = _ok(srv.scan_repo("/Users/carlosrivas/Dev/kenbun-agent/core/tools/cli"))
    assert "files" in out.lower() and "engine.py" in out.lower(), out[:300]


def test_list_checkpoints_returns_registry():
    out = _ok(srv.list_checkpoints())
    assert "checkpoint" in out.lower(), out[:200]


# ── Hivemind round-trip — saves + recall must use the same backend ──────────

def test_hivemind_save_search_delete_roundtrip():
    saved = _ok(srv.save_to_hivemind(
        title="tool-rot probe",
        content="probe for test_tool_surface — safe to delete",
        tags="probe,test,disposable",
    ))
    # Extract concept ID from "ID: concept_xxx"
    assert "concept_" in saved, saved
    cid = saved.split("concept_", 1)[1].split()[0].rstrip(".,'\"")
    cid = "concept_" + cid
    try:
        found = _ok(srv.search_hivemind_concepts("tool-rot probe"))
        assert "probe" in found.lower(), "save+search disagreed about backend"
    finally:
        srv.delete_from_hivemind(concept_id=cid)


def test_recall_fix_returns_history_or_empty_marker():
    out = _ok(srv.recall_fix("AttributeError NoneType"))
    # Either it found something or it cleanly said it didn't
    assert "fix" in out.lower() or "no similar" in out.lower(), out[:200]


# ── REGRESSIONS PINNED BY AUDIT ─────────────────────────────────────────────

def test_reflect_on_task_returns_string_not_dict():
    """Audit 2026-06-12: this returned a dict and crashed the MCP schema layer."""
    out = srv.reflect_on_task(task="probe", tool_logs="scan_repo: ok")
    assert isinstance(out, str), (
        f"reflect_on_task must return str (MCP schema requires it), got {type(out).__name__}. "
        "Fix: json.dumps(...) the dict payload on the way out."
    )
    _ok(out)


def test_get_brain_health_reports_real_metrics_not_zeros():
    """Audit 2026-06-12: parser couldn't read BENCHMARKS.json; reported 0% across the board."""
    out = _ok(srv.get_brain_health())
    # If BENCHMARKS.json has any data, this should not be all zeros
    from pathlib import Path
    benchmarks_path = Path(__file__).resolve().parents[2] / "brain_health" / "BENCHMARKS.json"
    if benchmarks_path.exists() and benchmarks_path.stat().st_size > 100:
        zeros_signal = out.count("0%") + out.count("0.00") + out.count("unknown")
        assert zeros_signal < 4, (
            f"get_brain_health reported {zeros_signal} zero/unknown fields despite a populated "
            f"BENCHMARKS.json — parser is blind to the current report shape:\n{out[:400]}"
        )


def test_get_intelligence_stats_reads_local_db_when_remote_is_down():
    """Audit 2026-06-12: 'no intelligence data' despite 45-tool local DB."""
    from pathlib import Path
    import sqlite3
    db = Path(__file__).resolve().parents[2] / "brain_health" / "kenbun_intelligence.db"
    if not db.exists():
        pytest.skip("no local intelligence DB to fall back to")
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM intelligence WHERE success_count > 0 OR failure_count > 0"
        ).fetchone()[0]
    finally:
        conn.close()
    if rows == 0:
        pytest.skip("local DB has no recorded outcomes yet")
    out = _ok(srv.get_intelligence_stats())
    assert "no intelligence data" not in out.lower(), (
        f"local DB has {rows} tools with outcomes but get_intelligence_stats sees nothing — "
        f"remote-only read path needs a local SQLite fallback. Got: {out[:200]}"
    )


def test_audit_package_safety_description_matches_behaviour():
    """Audit 2026-06-12: description says 'Supports: npm, pip' but pip path is a stub."""
    out = _ok(srv.audit_package_safety(package_name="requests", ecosystem="pip"))
    if "not yet supported" in out.lower():
        pytest.fail(
            "audit_package_safety advertises pip support in its description but rejects pip "
            "calls. Either implement pip or update the description to npm-only."
        )


# ── Tools that depend on external state — must skip gracefully ──────────────

def test_run_code_safely_works_or_skips_cleanly():
    out = srv.run_code_safely("print(2+2)", language="python", timeout=10)
    if "docker is not running" in out.lower():
        pytest.skip("docker daemon down — external dependency, not tool rot")
    _ok(out)
    assert "4" in out, out[:200]


def test_autofix_linter_respects_real_workspace_root():
    """In-process check: source must honour settings.PROJECT_ROOT.

    Note: when a user invokes this via the MCP wrapper from a session connected
    to a *different* kenbun install (e.g. their personal install rooted in
    /Users/.../Kenbun while editing kenbun-agent), the response will be
    'outside the authorized project workspace' — that's correct cross-project
    isolation, not a bug. Use a per-project MCP server.
    """
    from core.tools.infrastructure.config import settings
    out = srv.autofix_linter(
        file_path=str(settings.PROJECT_ROOT / "test_ghost.py"),
        project_path=str(settings.PROJECT_ROOT),
    )
    if "outside the authorized project workspace" in out.lower():
        pytest.fail(
            f"autofix_linter rejects a path inside settings.PROJECT_ROOT={settings.PROJECT_ROOT}. "
            "The source contract is broken — the test process's own PROJECT_ROOT is being "
            "rejected. (This is a real source bug, distinct from the cross-project MCP scope "
            "issue documented in docs/TOOL_AUDIT.md.)"
        )


def test_save_checkpoint_respects_real_workspace_root():
    """Same in-process contract as autofix_linter — see that test's docstring."""
    from core.tools.infrastructure.config import settings
    out = srv.save_checkpoint(file_path=str(settings.PROJECT_ROOT / "test_ghost.py"), label="probe")
    if "outside secure workspace" in out.lower():
        pytest.fail(
            f"save_checkpoint rejects a path inside settings.PROJECT_ROOT={settings.PROJECT_ROOT}. "
            "Source contract broken in-process."
        )
    assert "checkpoint" in out.lower() or "saved" in out.lower(), out[:200]
