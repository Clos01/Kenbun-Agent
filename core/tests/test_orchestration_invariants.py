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


def test_inline_fallback_uses_the_one_canonical_registry():
    """There must be exactly one place that builds the pipeline toolset.

    This used to compare two registries: the canonical build_pipeline_tools and
    a second dict server.py maintained for the inline-fallback path, which had
    drifted to 24 tools against the canonical 35. The duplicate was removed and
    both paths now go through build_pipeline_tools — so the invariant to guard
    is no longer "the two agree" but "there is still only one".

    Re-introducing a second registry is what the drift was; asserting the
    consolidation catches that directly.
    """
    from tools.infrastructure.orchestrator import build_pipeline_tools
    from tools.strategy import orchestration_tools

    canonical = build_pipeline_tools("")
    assert canonical, "build_pipeline_tools returned no tools"

    # The inline fallback must reach the pipeline through the shared entry
    # point rather than assembling its own toolset.
    source = pathlib.Path(orchestration_tools.__file__).read_text(encoding="utf-8")
    assert "run_orchestration_pipeline" in source, (
        "the inline fallback no longer routes through the shared orchestrate "
        "entry point — it may have grown its own tool registry again"
    )

    competing = [
        path
        for path in TOOLS.rglob("*.py")
        if path.name != "orchestrator.py"
        and "def _build_orchestrate_registry" in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert not competing, (
        "a second pipeline tool registry has reappeared in: "
        + ", ".join(str(p.relative_to(TOOLS)) for p in competing)
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


# --------------------------------------------------------------------------
# 5. An omitted project never becomes the container's own repo
# --------------------------------------------------------------------------

def test_orchestrate_project_path_defaults_to_empty():
    """`project_path="."` resolves to /app — Kenbun reviewing itself.

    Both orchestrate entry points must default to "", not ".". A caller who
    passes code inline and never names a project got scan_repo mapping /app
    (3,897 files) and that listing presented as their project.
    """
    import inspect

    from tools.infrastructure.orchestrator import orchestrate as pipeline_orchestrate
    from tools.strategy.orchestration_tools import orchestrate as mcp_orchestrate

    for fn in (pipeline_orchestrate, mcp_orchestrate):
        default = inspect.signature(fn).parameters["project_path"].default
        assert default == "", (
            f"{fn.__module__}.{fn.__name__} defaults project_path to {default!r}; "
            f'"." resolves to the container\'s own repo'
        )


def test_orchestrate_endpoint_does_not_substitute_a_repo_for_an_omitted_path():
    """`payload.get("project_path", ".") or "."` turned "" into ".".

    The MCP tool always sends project_path, empty when the caller omits it, so
    the `or "."` fallback fired on the most common call shape of all.
    """
    source = (TOOLS / "infrastructure" / "routers" / "swarm.py").read_text(encoding="utf-8")
    # Comments in this area quote the old expression on purpose — only real
    # code counts.
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    assert 'payload.get("project_path", ".")' not in code
    assert 'payload.get("project_path", "") or ""' in code


def test_load_review_target_returns_nothing_when_no_project_named():
    """With no project and no code, there is nothing to review — say nothing.

    _project_root used to fall back to Path("."), so this call read Kenbun's
    own working-tree diff and handed it to the reviewers as the caller's code.
    """
    from tools.utils.review_targets import load_review_target

    assert load_review_target(
        project_path="",
        file_path="",
        code_snippet="",
        task="Audit the quote calculator in src/lib/pricing-sop.ts",
    ) == ""


def test_load_review_target_passes_inline_code_through():
    """The inline path is the only one that works for code the container cannot see."""
    from tools.utils.review_targets import load_review_target

    snippet = "export function calculateTurnkeyEstimate() { return 42; }"
    assert load_review_target(code_snippet=snippet) == snippet


def test_code_review_reviewers_require_real_code():
    """No reviewer may run on the repo_map, and none may run on nothing.

    The supervisor step used to fall back to `repo_map` — a signatures-only
    listing — which is both a useless review and what pushed it past its 120s
    timeout on a large repo.
    """
    from tools.infrastructure.orchestrator import build_pipeline_tools
    from tools.infrastructure.pipelines.code_review import build_code_review_pipeline

    steps = {s["id"]: s for s in build_code_review_pipeline(build_pipeline_tools(""))}

    for step_id in ("supervisor_review", "gemini_review"):
        step = steps.get(step_id)
        if step is None:
            continue  # gemini_review is IDE-conditional
        assert step["skip_if"]({"code_snippet": ""}), f"{step_id} runs with no code"
        assert step["skip_if"]({"code_snippet": "", "repo_map": "x" * 1000}), (
            f"{step_id} falls back to the repo map"
        )

    supervisor_input = steps["supervisor_review"]["input"]
    fed = supervisor_input({"task": "t", "code_snippet": "", "repo_map": "MAP"})
    assert fed["code_snippet"] == "", "supervisor still receives the repo map"


def test_code_review_reports_when_it_had_nothing_to_review():
    """Silence reads as success. An empty review must state why it was empty."""
    from tools.infrastructure.orchestrator import build_pipeline_tools
    from tools.infrastructure.pipelines.code_review import build_code_review_pipeline

    steps = {s["id"]: s for s in build_code_review_pipeline(build_pipeline_tools(""))}
    assert "no_source" in steps, "code_review has no no-source report step"

    step = steps["no_source"]
    assert step["skip_if"]({"code_snippet": "real code"}), "no_source fires despite having code"
    assert not step["skip_if"]({"code_snippet": ""}), "no_source skipped when there is no code"

    report = step["tool"](**step["input"]({"task": "Audit the calculator"}))
    assert "code_snippet" in report
    assert "No source loaded" in report


# --------------------------------------------------------------------------
# 6. A budget stop must not masquerade as a broken API
# --------------------------------------------------------------------------

def test_gemini_client_refuses_the_local_sentinel():
    """`get_budget_aware_model` returns "local" when the daily budget is spent.

    That is an instruction to route away from the cloud. llm_router honours it
    by swapping in a local endpoint and a real local model; gemini_reviewer has
    no local endpoint to swap to and used to pass the sentinel straight through
    as a model name, calling `models/local` and getting
    `404 NOT_FOUND ... is not found for API version v1beta` every time. A spent
    budget was indistinguishable from a broken API key.
    """
    from tools.audit import gemini_reviewer

    source = pathlib.Path(gemini_reviewer.__file__).read_text(encoding="utf-8")
    assert hasattr(gemini_reviewer, "BudgetExhaustedError")
    assert gemini_reviewer.LOCAL_SENTINEL == "local"
    assert "if model_to_use == LOCAL_SENTINEL:" in source, (
        "gemini_reviewer no longer guards the budget sentinel — it will call "
        "Gemini with a placeholder model name"
    )


def test_llm_router_swaps_the_sentinel_for_a_real_local_model():
    """The other sentinel consumer must resolve it to a model that exists.

    An earlier version substituted llama3.2:1b, which OLLAMA_PULL_MODELS never
    pulls, so the emergency downgrade 404'd against a real Ollama too.
    """
    source = (TOOLS / "utils" / "llm_router.py").read_text(encoding="utf-8")
    # Comments here name the old broken model on purpose — only code counts.
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    assert 'primary_model == "local"' in code, "llm_router stopped handling the sentinel"
    assert "llama3.2:1b" not in code, "llm_router downgrades to a model Ollama does not pull"
    assert 'primary_model = "qwen2.5:1.5b"' in code, (
        "llm_router no longer substitutes a real pulled local model"
    )
