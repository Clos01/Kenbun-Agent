"""Structural guarantees the orchestration layer kept losing silently.

Companion to test_pipeline_contracts.py: that file checks step↔tool kwarg
shapes; this one checks registry parity, shadowed definitions, and the
fail-loudly invariants documented in docs/ORCHESTRATION_INVARIANTS.md.

Each test here exists because the invariant it asserts was broken in production
and nothing noticed. They are cheap, import-only checks — no network, no LLM.
"""

import ast
import collections
import pathlib

import pytest

CORE = pathlib.Path(__file__).resolve().parents[1]
TOOLS = CORE / "tools"


# --------------------------------------------------------------------------
# 1. No shadowed top-level definitions
# --------------------------------------------------------------------------

def _redefinitions(path: pathlib.Path):
    """Top-level names defined more than once in a single module."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return []
    seen = collections.Counter()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            seen[node.name] += 1
    return [(name, count) for name, count in seen.items() if count > 1]


def test_no_shadowed_top_level_definitions():
    """A second `def` of the same name silently replaces the first.

    orchestrator.py carried two of these at once: `orchestrate` and
    `_analyze_bug`. In both cases the *dead* copy was the one later work had
    improved, so fixes appeared to land and changed nothing. Ruff's F811 does
    not catch this when the earlier definition is referenced in between, which
    it was — hence this check.
    """
    offenders = []
    for path in TOOLS.rglob("*.py"):
        for name, count in _redefinitions(path):
            offenders.append(f"{path.relative_to(CORE)}: {name} defined {count}x")
    assert not offenders, (
        "Shadowed top-level definitions found — the later one silently wins:\n  "
        + "\n  ".join(offenders)
    )


# --------------------------------------------------------------------------
# 2. Every entry point offers the same tools
# --------------------------------------------------------------------------

def test_orchestrate_entry_points_share_one_registry():
    """orchestrate() and swarm() must not build their own tool dicts.

    They previously did, and drifted to 24 and 19 tools against
    build_pipeline_tools' 35. Every kanban_* tool was missing from both, so a
    workflow step calling one received nothing and raised nothing — the step
    reported success having done no work.
    """
    import inspect
    from tools.infrastructure import orchestrator

    for fn_name in ("orchestrate", "swarm"):
        fn = getattr(orchestrator, fn_name)
        src = "".join(inspect.getsourcelines(fn)[0])
        assert "build_pipeline_tools" in src, (
            f"{fn_name}() no longer uses build_pipeline_tools(); it is building "
            f"its own tool dict, which is how the registries drifted apart before."
        )
        assert '"scan_repo":' not in src, (
            f"{fn_name}() appears to define a tool dict inline. Use "
            f"build_pipeline_tools() so there is exactly one registry."
        )


def test_mcp_fallback_registry_matches_pipeline_registry():
    """The inline-fallback registry must expose the same tool NAMES.

    When HTTP dispatch fails, server.py runs the pipeline in-process with its
    own registry. That registry legitimately wraps some tools (injecting the
    docs registry, Chroma host/port), so the callables differ by design — but
    the *names* must match, or a workflow behaves differently depending on
    whether dispatch happened to succeed.
    """
    from tools.infrastructure.orchestrator import build_pipeline_tools
    from tools.infrastructure.server import _build_orchestrate_registry

    canonical = set(build_pipeline_tools("."))
    fallback = set(_build_orchestrate_registry())

    missing = canonical - fallback
    assert not missing, (
        "Tools available via the normal path but MISSING from the inline "
        "fallback — these silently disappear when dispatch fails:\n  "
        + ", ".join(sorted(missing))
    )


# --------------------------------------------------------------------------
# 3. Loaders raise; they do not return error strings
# --------------------------------------------------------------------------

def test_scan_repo_raises_instead_of_returning_an_error_string():
    """A returned error string becomes LLM input indistinguishable from data.

    scan_repo used to return "❌ Path not found: ...". Callers store a step's
    return value in pipeline state and hand it to a reviewer as the repo map. An
    audit then inspected that sentence, found nothing wrong with it, and
    returned APPROVED — which is how a patch for a non-existent file was signed
    off. Failures must raise so the step is marked failed and downstream steps
    skip.
    """
    from tools.memory.repo_mapper import scan_repo

    with pytest.raises(FileNotFoundError):
        scan_repo("/nonexistent/path/that/should/never/exist/kenbun-test")


# --------------------------------------------------------------------------
# 4. No verdict without evidence
# --------------------------------------------------------------------------

@pytest.mark.parametrize("snippet", ["", "   ", "❌ Path not found: /tmp/x"])
def test_supervisor_never_approves_without_reviewable_code(snippet):
    """An audit with no source must be INCONCLUSIVE, never APPROVED.

    The adversarial court reports "the prosecution identified no concrete
    flaws" when handed nothing — true, and it rendered as APPROVED. An
    approval nobody earned is worse than a crash: it is indistinguishable from
    a real verdict.
    """
    import asyncio
    from tools.audit.supervisor_agent import run_supervisor_audit

    result = asyncio.run(run_supervisor_audit(
        user_proposal="Review this code change for correctness.",
        code_snippet=snippet,
    ))
    assert result["status"] != "APPROVED", (
        f"Supervisor returned {result['status']} with no reviewable source: "
        f"{str(result.get('critique'))[:200]}"
    )
    assert result["status"] == "INCONCLUSIVE"
