"""
Test Suite: Sparse L1 Tool Context Gating (ESL Ch. 3 & 18)
==========================================================
Validates the soft-thresholding operator, the task-conditioned tool selection
built on it, and — critically — that the gate is actually wired into the prompt
path that pays for the tokens.
"""

import importlib
import unittest
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


class TestSparseToolGating(unittest.TestCase):

    def test_soft_threshold_zeroes_small_values(self):
        self.assertEqual(soft_threshold(0.1, 0.15), 0.0)
        self.assertEqual(soft_threshold(-0.1, 0.15), 0.0)
        self.assertEqual(soft_threshold(0.15, 0.15), 0.0)

    def test_soft_threshold_shrinks_toward_zero_preserving_sign(self):
        self.assertAlmostEqual(soft_threshold(0.5, 0.15), 0.35, places=4)
        self.assertAlmostEqual(soft_threshold(-0.5, 0.15), -0.35, places=4)

    def test_extract_text_features_drops_single_chars_and_lowercases(self):
        tokens = extract_text_features("Fix the CSS a b Grid_Layout")
        self.assertIn("css", tokens)
        self.assertIn("grid_layout", tokens)
        self.assertNotIn("a", tokens)

    def test_gate_isolates_task_domain(self):
        cases = [
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
        ]
        for task, expected_present, expected_absent in cases:
            active = filter_active_toolset(task, TOOL_CATALOG_FIXTURE, max_active_tools=4)
            self.assertTrue(expected_present <= set(active), f"{task}: missing {expected_present - set(active)}")
            self.assertFalse(bool(expected_absent & set(active)), f"{task}: leaked {expected_absent & set(active)}")

    def test_gate_respects_max_active_tools(self):
        active = filter_active_toolset("Build a responsive CSS grid layout", TOOL_CATALOG_FIXTURE, max_active_tools=3)
        self.assertLessEqual(len(active), 3)

    def test_gate_returns_everything_when_catalog_is_already_small(self):
        small = {"a": "alpha", "b": "beta"}
        self.assertEqual(filter_active_toolset("anything", small, max_active_tools=6), small)

    def test_core_tools_survive_an_unrelated_task(self):
        ranked = compute_sparse_tool_weights("translate this poem into Latin", TOOL_CATALOG_FIXTURE, max_active_tools=6)
        selected = {tid for tid, _ in ranked}
        self.assertTrue(CORE_DEFAULT_TOOLS <= selected)

    def test_empty_task_does_not_crash(self):
        ranked = compute_sparse_tool_weights("", TOOL_CATALOG_FIXTURE, max_active_tools=4)
        self.assertLessEqual(len(ranked), 4)

    def test_render_tool_catalog_lists_every_tool(self):
        text = render_tool_catalog({"a": "does a", "b": "does b"}, "TOOLS:")
        self.assertIn("a — does a", text)
        self.assertIn("b — does b", text)

    def test_gated_catalog_measures_real_savings(self):
        with patch(f"{GATING_PATH}.build_registry_tool_map", return_value=TOOL_CATALOG_FIXTURE):
            text, stats = gated_tool_catalog("Fix the CSS grid on the navbar", max_active_tools=4)

        self.assertIsNotNone(text)
        self.assertEqual(stats["total_tools"], 12)
        self.assertLessEqual(stats["active_tools"], 4)
        self.assertLess(stats["gated_chars"], stats["full_chars"])
        self.assertGreater(stats["savings_pct"], 0)
        self.assertNotIn("webull_place_order", text)

    def test_gated_catalog_falls_back_when_registry_unavailable(self):
        with patch(f"{GATING_PATH}.build_registry_tool_map", return_value={}):
            text, stats = gated_tool_catalog("anything")
        self.assertIsNone(text)
        self.assertEqual(stats["total_tools"], 0)

    def test_think_about_tools_uses_the_gate(self):
        workspace = importlib.import_module(WORKSPACE_PATH)
        with patch(f"{GATING_PATH}.build_registry_tool_map", return_value=TOOL_CATALOG_FIXTURE):
            catalog = workspace._catalog_for_task("Fix the CSS grid on the navbar")

        self.assertIn("L1-gated", catalog)
        self.assertNotIn("webull_place_order", catalog)

    def test_catalog_falls_back_to_static_on_failure(self):
        workspace = importlib.import_module(WORKSPACE_PATH)
        with patch(f"{GATING_PATH}.gated_tool_catalog", side_effect=RuntimeError("registry down")):
            catalog = workspace._catalog_for_task("anything at all")

        self.assertEqual(catalog, workspace.TOOL_CATALOG)


if __name__ == "__main__":
    unittest.main()
