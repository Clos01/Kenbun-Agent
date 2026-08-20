"""
Test Suite: Sparse L1 Tool Context Gating (ESL Ch. 3 & 18)
==========================================================
Validates the soft-thresholding operator, the task-conditioned tool selection
built on it, and — critically — that the gate is actually wired into the prompt
path that pays for the tokens.
"""

import importlib

import pytest
from unittest.mock import patch

try:
    from tools.utils.sparse_gating import (
        soft_threshold,
        extract_text_features,
        compute_sparse_tool_weights,
        filter_active_toolset,
        render_tool_catalog,
        gated_tool_catalog,
        CORE_DEFAULT_TOOLS,
    )
    GATING_PATH = "tools.utils.sparse_gating"
    WORKSPACE_PATH = "tools.infrastructure.workspace_tools"
except ImportError:
    from core.tools.utils.sparse_gating import (
        soft_threshold,
        extract_text_features,
        compute_sparse_tool_weights,
        filter_active_toolset,
        render_tool_catalog,
        gated_tool_catalog,
        CORE_DEFAULT_TOOLS,
    )
    GATING_PATH = "core.tools.utils.sparse_gating"
    WORKSPACE_PATH = "core.tools.infrastructure.workspace_tools"


# A catalog spanning clearly disjoint domains, so a correct gate is unambiguous.
TOOL_CATALOG_FIXTURE = {
    "ask_ui_expert": "Expert UI and CSS flexbox styling assistant",
    "get_design_tokens": "Fetches color tokens, typography themes, and CSS radii",
    "generate_wireframe": "Renders UI layout mockups and wireframes",
    "webull_place_order": "Submits equity swing trades to Webull broker API",
    "webull_get_positions": "Inspects active stock positions and PnL",
    "fetch_git_pushes": "Fetches recent Git commits from remote origin repository",
    "apply_git_patch": "Applies diff patch and merges branches in local repository",
    "create_bitbucket_pr": "Creates pull request in Git repository",
    "elevenlabs_tts": "Generates voice audio speech synthesis",
    "transcribe_audio": "Transcribes incoming audio streams to text",
    "consult_supervisor": "System 2 security and architecture review",
    "run_code_safely": "Executes code inside isolated sandbox container",
}


# ------------------------------------------------------------------
# soft_threshold — the L1 operator itself
# ------------------------------------------------------------------

def test_soft_threshold_zeroes_small_values():
    assert soft_threshold(0.1, 0.15) == 0.0
    assert soft_threshold(-0.1, 0.15) == 0.0
    assert soft_threshold(0.15, 0.15) == 0.0


def test_soft_threshold_shrinks_toward_zero_preserving_sign():
    assert soft_threshold(0.5, 0.15) == pytest.approx(0.35)
    assert soft_threshold(-0.5, 0.15) == pytest.approx(-0.35)


def test_extract_text_features_drops_single_chars_and_lowercases():
    tokens = extract_text_features("Fix the CSS a b Grid_Layout")
    assert "css" in tokens
    assert "grid_layout" in tokens
    assert "a" not in tokens


# ------------------------------------------------------------------
# task-conditioned selection
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "task,expected_present,expected_absent",
    [
        (
            "Create a sleek dark-mode navigation bar with glassmorphism CSS",
            {"ask_ui_expert", "get_design_tokens"},
            {"webull_place_order", "elevenlabs_tts"},
        ),
        (
            "Commit feature branch changes and create a PR for review",
            {"create_bitbucket_pr"},
            {"webull_place_order", "elevenlabs_tts", "ask_ui_expert"},
        ),
        (
            "Submit a limit buy order for 10 shares of NVDA on Webull",
            {"webull_place_order"},
            {"ask_ui_expert", "elevenlabs_tts"},
        ),
    ],
)
def test_gate_isolates_task_domain(task, expected_present, expected_absent):
    active = filter_active_toolset(task, TOOL_CATALOG_FIXTURE, max_active_tools=4)
    assert expected_present <= set(active), f"{task}: missing {expected_present - set(active)}"
    assert not (expected_absent & set(active)), f"{task}: leaked {expected_absent & set(active)}"


def test_gate_respects_max_active_tools():
    active = filter_active_toolset(
        "Build a responsive CSS grid layout", TOOL_CATALOG_FIXTURE, max_active_tools=3
    )
    assert len(active) <= 3


def test_gate_returns_everything_when_catalog_is_already_small():
    small = {"a": "alpha", "b": "beta"}
    assert filter_active_toolset("anything", small, max_active_tools=6) == small


def test_core_tools_survive_an_unrelated_task():
    """consult_supervisor / run_code_safely must never be gated out — the planner
    needs them regardless of domain."""
    ranked = compute_sparse_tool_weights(
        "translate this poem into Latin", TOOL_CATALOG_FIXTURE, max_active_tools=6
    )
    selected = {tid for tid, _ in ranked}
    assert CORE_DEFAULT_TOOLS <= selected


def test_empty_task_does_not_crash():
    ranked = compute_sparse_tool_weights("", TOOL_CATALOG_FIXTURE, max_active_tools=4)
    assert len(ranked) <= 4


# ------------------------------------------------------------------
# the catalog actually injected into prompts
# ------------------------------------------------------------------

def test_render_tool_catalog_lists_every_tool():
    text = render_tool_catalog({"a": "does a", "b": "does b"}, "TOOLS:")
    assert "a — does a" in text
    assert "b — does b" in text


def test_gated_catalog_measures_real_savings():
    with patch(f"{GATING_PATH}.build_registry_tool_map", return_value=TOOL_CATALOG_FIXTURE):
        text, stats = gated_tool_catalog("Fix the CSS grid on the navbar", max_active_tools=4)

    assert text is not None
    assert stats["total_tools"] == 12
    assert stats["active_tools"] <= 4
    # Savings must be measured from rendered characters, not asserted from a ratio.
    assert stats["gated_chars"] < stats["full_chars"]
    assert stats["savings_pct"] > 0
    assert "webull_place_order" not in text


def test_gated_catalog_falls_back_when_registry_unavailable():
    with patch(f"{GATING_PATH}.build_registry_tool_map", return_value={}):
        text, stats = gated_tool_catalog("anything")
    assert text is None
    assert stats["total_tools"] == 0


# ------------------------------------------------------------------
# WIRING — the gate must be reachable from production, not just from tests
# ------------------------------------------------------------------

def test_think_about_tools_uses_the_gate():
    """Regression guard for the original defect: the module existed, passed its
    tests, and was called by nobody.

    Deliberately a hard import, not importorskip: if the production module
    cannot load, the wiring is broken and this must go red, not green-with-a-skip.
    """
    workspace = importlib.import_module(WORKSPACE_PATH)

    with patch(f"{GATING_PATH}.build_registry_tool_map", return_value=TOOL_CATALOG_FIXTURE):
        catalog = workspace._catalog_for_task("Fix the CSS grid on the navbar")

    assert "L1-gated" in catalog
    assert "webull_place_order" not in catalog


def test_catalog_falls_back_to_static_on_failure():
    workspace = importlib.import_module(WORKSPACE_PATH)

    with patch(f"{GATING_PATH}.gated_tool_catalog", side_effect=RuntimeError("registry down")):
        catalog = workspace._catalog_for_task("anything at all")

    assert catalog == workspace.TOOL_CATALOG
