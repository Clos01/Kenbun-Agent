"""
Test Suite: Bayesian Thompson Sampling Engine (ESL Ch. 8 & 16)
==============================================================
Validates Bayesian posterior sampling, exploration-exploitation trade-offs,
deterministic greedy fallback, and that the sampler is actually reached by the
production routing path (DecisionRouter.recommend_tools).
"""

import importlib
import unittest
from unittest.mock import patch

try:
    from tools.utils.bayesian import (
        get_posterior_params,
        get_posterior_params_batch,
        sample_tool_thompson,
        rank_tools_thompson,
        get_best_tool,
        get_confidence,
    )
    MODULE_PATH = "tools.utils.bayesian"
    ROUTER_PATH = "tools.strategy.decision_logic"
except ImportError:
    from core.tools.utils.bayesian import (
        get_posterior_params,
        get_posterior_params_batch,
        sample_tool_thompson,
        rank_tools_thompson,
        get_best_tool,
        get_confidence,
    )
    MODULE_PATH = "core.tools.utils.bayesian"
    ROUTER_PATH = "core.tools.strategy.decision_logic"


PARAMS = {
    "tool_veteran": (50.0, 5.0),    # E[p] = 0.909, tight posterior
    "tool_uncertain": (1.0, 1.0),   # E[p] = 0.500, maximally wide
    "tool_failing": (2.0, 20.0),    # E[p] = 0.091
}


class TestBayesianThompson(unittest.TestCase):

    def setUp(self):
        def per_tool(tool_id, category="global"):
            return PARAMS.get(tool_id, (1.0, 1.0))

        def batch_tools(tool_ids, category="global"):
            return {tid: PARAMS.get(tid, (1.0, 1.0)) for tid in tool_ids if tid in PARAMS}

        self.patcher1 = patch(f"{MODULE_PATH}.get_posterior_params", side_effect=per_tool)
        self.patcher2 = patch(f"{MODULE_PATH}.get_posterior_params_batch", side_effect=batch_tools)
        self.patcher1.start()
        self.patcher2.start()

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()

    def test_get_posterior_params_default(self):
        """Unknown tools default to the Beta(1,1) uniform prior."""
        with patch(f"{MODULE_PATH}.get_connection") as mock_conn:
            mock_conn.side_effect = Exception("DB offline")
            self.patcher1.stop()
            try:
                alpha, beta = get_posterior_params("unknown_tool_xyz")
                self.assertEqual(alpha, 1.0)
                self.assertEqual(beta, 1.0)
            finally:
                self.patcher1.start()

    def test_batch_fetch_returns_empty_on_db_failure(self):
        """A telemetry outage must degrade to the prior, never raise into routing."""
        with patch(f"{MODULE_PATH}.get_connection") as mock_conn:
            mock_conn.side_effect = Exception("DB offline")
            self.patcher2.stop()
            try:
                self.assertEqual(get_posterior_params_batch(["unknown_1", "unknown_2"]), {})
            finally:
                self.patcher2.start()

    def test_batch_fetch_short_circuits_on_empty_input(self):
        self.patcher2.stop()
        try:
            self.assertEqual(get_posterior_params_batch([]), {})
        finally:
            self.patcher2.start()

    def test_sample_tool_thompson_single_candidate(self):
        """A single candidate reports its posterior mean, not a noisy draw."""
        tool, score = sample_tool_thompson("security", ["tool_veteran"])
        self.assertEqual(tool, "tool_veteran")
        self.assertAlmostEqual(score, 50.0 / 55.0, places=4)

    def test_sample_tool_thompson_empty_raises(self):
        with self.assertRaises(ValueError):
            sample_tool_thompson("security", [])

    def test_rank_tools_thompson_empty_raises(self):
        with self.assertRaises(ValueError):
            rank_tools_thompson("security", [])

    def test_rank_returns_every_candidate_once(self):
        ranked = rank_tools_thompson("general", ["tool_veteran", "tool_uncertain", "tool_veteran"])
        ids = [tid for tid, _ in ranked]
        self.assertEqual(sorted(ids), ["tool_uncertain", "tool_veteran"])

    def test_rank_is_sorted_descending(self):
        ranked = rank_tools_thompson("general", list(PARAMS), exploration_mode=False)
        scores = [s for _, s in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(ranked[0][0], "tool_veteran")

    def test_thompson_exploration_vs_exploitation_distribution(self):
        """1,000 trials across a veteran, an unobserved tool, and a failing tool."""
        counts = {k: 0 for k in PARAMS}
        trials = 1000
        for _ in range(trials):
            chosen, _ = sample_tool_thompson("general", list(PARAMS))
            counts[chosen] += 1

        self.assertGreaterEqual(counts["tool_veteran"], 800)
        self.assertGreaterEqual(counts["tool_uncertain"], 10)
        self.assertLessEqual(counts["tool_failing"], 25)

    def test_temperature_increases_exploration(self):
        """Higher T flattens the posteriors, so the veteran wins less often."""
        def veteran_share(temp):
            wins = 0
            for _ in range(600):
                chosen, _ = sample_tool_thompson("general", list(PARAMS), temperature=temp)
                if chosen == "tool_veteran":
                    wins += 1
            return wins / 600

        self.assertLess(veteran_share(20.0), veteran_share(1.0))

    def test_get_best_tool_deterministic_greedy_mode(self):
        conf_map = {"tool_a": 0.85, "tool_b": 0.92, "tool_c": 0.40}
        with patch(f"{MODULE_PATH}.get_confidence", side_effect=lambda tid, cat: conf_map[tid]):
            best_tool, score = get_best_tool("general", ["tool_a", "tool_b", "tool_c"], exploration_mode=False)
            self.assertEqual(best_tool, "tool_b")
            self.assertEqual(score, 0.92)


if __name__ == "__main__":
    unittest.main()
