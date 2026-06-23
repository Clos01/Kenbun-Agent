"""Pipeline ↔ tool kwarg contract tests.

Catches the class of ghost bug where a pipeline step's ``input`` lambda
passes a kwarg the bound tool does not accept (the orchestrator only sees
the failure at runtime, and only when ``skip_if`` doesn't mask the step).

The canonical example is the one this test was written for: the
``analyze_review_request`` step in ``code_review.py`` passed ``tech_key`` to
``_analyze_bug``, which did not accept it. The orchestrator's pipeline
runner calls ``step["tool"](**input_fn(state))``, so any kwarg mismatch
becomes a ``TypeError`` at step-execution time.

This test walks every registered pipeline, evaluates each step's input
lambda against a synthetic state with every reasonable key populated, and
asserts ``input_kwargs ⊆ signature.parameters`` (or the receiver accepts
``**kwargs``).
"""
from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, Iterable

import pytest

from tools.infrastructure.server import _build_orchestrate_registry
from tools.registry import registry

# Side-effect import: registers every pipeline (bug_fix, code_review,
# research_implement, shadow_test, design_ui) into ``registry``.
import tools.infrastructure.orchestrator  # noqa: F401


# A maximalist state dict — every key any pipeline lambda might read.
# When a key isn't relevant, the value is intentionally truthy so that
# skip_if guards don't mask the step we're trying to inspect. The goal
# is to surface the kwarg shape, not to run real work.
_SYNTHETIC_STATE: Dict[str, Any] = {
    "task": "synthetic task for contract test",
    "project_path": "/tmp/synthetic_project",
    "file_path": "/tmp/synthetic_project/example.py",
    "code_snippet": "print('hello')",
    "tech_key": "python",
    "fast": False,
    "repo_map": "synthetic repo map",
    "past_fixes": "synthetic past fixes",
    "research_result": "synthetic research",
    "gemini_analysis": "synthetic analysis",
    "review_result": "synthetic review",
    "sandbox_result": "synthetic sandbox",
    "supervisor_result": "synthetic supervisor",
    "checkpoint_result": "synthetic checkpoint",
    "memory_result": "synthetic memory",
    "backtrack_count": 0,
    "artifact_result": "synthetic artifact",
    "test_draft": "def test_x(): pass",
    "file_content": "print('hello')",
    "full_log": "",
}


def _accepts_var_keyword(func: Callable) -> bool:
    """True if ``func`` accepts ``**kwargs`` (silently absorbs extras)."""
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return True  # Builtins / C funcs: we can't introspect, assume permissive
    return any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )


def _accepted_param_names(func: Callable) -> set[str]:
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return set()
    return {
        p.name
        for p in sig.parameters.values()
        if p.kind
        in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
            inspect.Parameter.POSITIONAL_ONLY,
        )
    }


def _iter_pipeline_steps() -> Iterable[tuple[str, dict]]:
    """Yield ``(workflow_name, step_dict)`` for every step of every pipeline."""
    tools = _build_orchestrate_registry()
    pipelines = registry.get_all_pipelines()
    assert pipelines, "No pipelines registered — orchestrator import failed?"
    for name, entry in pipelines.items():
        try:
            steps = entry.builder(tools)
        except Exception as e:  # pragma: no cover — surface as fail, not skip
            pytest.fail(f"Pipeline `{name}` failed to build: {e!r}")
        for step in steps:
            yield name, step


@pytest.mark.parametrize(
    "workflow,step",
    [pytest.param(w, s, id=f"{w}::{s['id']}") for w, s in _iter_pipeline_steps()],
)
def test_pipeline_step_kwargs_match_tool_signature(workflow: str, step: dict) -> None:
    """Every kwarg the input lambda produces must be accepted by the tool."""
    tool = step["tool"]
    assert tool is not None, (
        f"[{workflow}::{step['id']}] step has no tool bound — the registry "
        f"lookup returned None (most likely a missing/renamed registry key)."
    )

    input_fn = step["input"]
    try:
        tool_input = input_fn(_SYNTHETIC_STATE)
    except Exception as e:
        pytest.fail(
            f"[{workflow}::{step['id']}] input lambda raised on synthetic "
            f"state: {e!r}. The state probably needs a new key — extend "
            f"_SYNTHETIC_STATE in this test."
        )

    assert isinstance(tool_input, dict), (
        f"[{workflow}::{step['id']}] input lambda returned "
        f"{type(tool_input).__name__}, expected dict."
    )

    if _accepts_var_keyword(tool):
        # **kwargs absorbs anything; nothing more to check.
        return

    accepted = _accepted_param_names(tool)
    extras = set(tool_input) - accepted
    assert not extras, (
        f"[{workflow}::{step['id']}] contract drift: input lambda passes "
        f"{sorted(extras)} but tool {getattr(tool, '__name__', repr(tool))!r} "
        f"only accepts {sorted(accepted)}. Either remove the extra kwargs "
        f"from the lambda or widen the tool with **kwargs."
    )


def test_every_pipeline_step_has_required_keys() -> None:
    """A step must have id, label, tool, and input — without these the
    pipeline runner crashes with a less informative KeyError."""
    required = {"id", "label", "tool", "input"}
    for workflow, step in _iter_pipeline_steps():
        missing = required - set(step)
        assert not missing, (
            f"[{workflow}] step is missing required keys: {sorted(missing)} "
            f"(step={step.get('id', '<unnamed>')!r})"
        )


def test_known_regression_analyze_bug_absorbs_tech_key() -> None:
    """Regression guard for the ghost bug this suite was created for.

    ``_analyze_bug`` historically did not accept ``tech_key`` and crashed any
    pipeline step that passed it. We widened it with ``**kwargs`` so spurious
    kwargs are silently dropped. This test pins that contract.
    """
    from tools.infrastructure.orchestrator import _analyze_bug

    assert _accepts_var_keyword(_analyze_bug), (
        "_analyze_bug must accept **kwargs so spurious kwargs (e.g. tech_key) "
        "don't crash the orchestrator. See orchestrator.py docstring."
    )
