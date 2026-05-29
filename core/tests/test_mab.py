import unittest
import os
import tempfile
from pathlib import Path
from tools.strategy.decision_logic import ContextualModelBandit, DecisionRouter

class TestContextualModelBandit(unittest.TestCase):
    def setUp(self):
        # Create a temporary file to hold MAB stats so we don't interfere with real database stats
        self.temp_dir = tempfile.TemporaryDirectory()
        self.stats_path = Path(self.temp_dir.name) / "mab_stats_test.json"
        self.bandit = ContextualModelBandit(self.stats_path)
        self.router = DecisionRouter()
        # Direct the router's bandit to our test stats to avoid corrupting production stats
        self.router.bandit = self.bandit

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_ensure_stats_exist(self):
        """Verify that basic stats template with all six model arms is initialized."""
        self.assertTrue(self.stats_path.exists())
        stats = self.bandit.load_stats()
        self.assertEqual(stats["total_selections"], 0)
        self.assertIn("SIMPLE", stats["contexts"])
        self.assertIn("COMPLEX", stats["contexts"])
        
        for ctx in ["SIMPLE", "COMPLEX"]:
            arms = stats["contexts"][ctx]["arms"]
            self.assertIn("gemini-3.5-flash", arms)
            self.assertIn("gemini-3.1-flash-lite", arms)
            self.assertIn("gemini-3.1-flash-lite-preview", arms)
            self.assertIn("gemini-3-flash-preview", arms)
            self.assertIn("gemini-3.1-pro-preview", arms)
            self.assertIn("local", arms)

    def test_cold_start_prioritization(self):
        """Verify that any arm with 0 plays is played during cold start to build baseline priors."""
        # Clean start (all 6 have 0 plays)
        selected = []
        for _ in range(6):
            arm = self.bandit.select_arm("SIMPLE")
            selected.append(arm)
            # Record feedback of 1 play
            self.bandit.record_feedback("SIMPLE", arm, success=True, latency=1.0, cost=0.0)

        # All 6 unique arms should have been played once
        self.assertEqual(len(set(selected)), 6)

    def test_feedback_updates(self):
        """Verify that feedback successfully updates rewards and statistics."""
        # Try a successful play
        self.bandit.record_feedback("SIMPLE", "local", success=True, latency=1.5, cost=0.0)
        stats = self.bandit.load_stats()
        local_arm = stats["contexts"]["SIMPLE"]["arms"]["local"]
        
        self.assertEqual(local_arm["selections"], 1)
        self.assertEqual(local_arm["successes"], 1)
        self.assertEqual(local_arm["total_latency"], 1.5)
        self.assertEqual(local_arm["total_cost"], 0.0)
        # Verify utility reward calculation: local has cost=0 (cost_score=1.0), latency=1.5 (latency_score=0.85)
        # reward = 0.2 * 1.0 + 0.5 * 1.0 + 0.3 * 0.85 = 0.2 + 0.5 + 0.255 = 0.955
        self.assertAlmostEqual(local_arm["average_reward"], 0.955, places=3)

        # Try a failed play (penalty = 0.0)
        self.bandit.record_feedback("SIMPLE", "local", success=False, latency=2.0, cost=0.0)
        stats = self.bandit.load_stats()
        local_arm = stats["contexts"]["SIMPLE"]["arms"]["local"]
        
        self.assertEqual(local_arm["selections"], 2)
        # Average reward should be updated incrementally: (0.955 + 0.0) / 2 = 0.4775
        self.assertAlmostEqual(local_arm["average_reward"], 0.4775, places=4)

    def test_simple_vs_complex_routing(self):
        """Verify that tasks are routed to the correct context (SIMPLE or COMPLEX)."""
        # Simple task
        self.assertEqual(self.router.get_task_context("Fix a typo in the README file"), "SIMPLE")
        # Complex task (contains security/architecture signals)
        self.assertEqual(self.router.get_task_context("Audit login route to prevent SQL injection"), "COMPLEX")
        # Long word count task
        long_task = " ".join(["word"] * 160)
        self.assertEqual(self.router.get_task_context(long_task), "COMPLEX")

    def test_mab_convergence(self):
        """Simulate real trials and verify UCB1 converges to the highest-utility model."""
        # Let's seed 1 play for each to pass the cold start phase
        active_arms = [
            "gemini-3.5-flash",
            "gemini-3.1-pro-preview",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite",
            "gemini-3.1-flash-lite-preview",
            "local"
        ]
        for arm in active_arms:
            self.bandit.record_feedback("SIMPLE", arm, success=True, latency=1.0, cost=0.001)

        # Now simulate 40 trials for SIMPLE task routing.
        # local is the best arm (success=100%, latency=1.0s, cost=$0)
        # gemini-3.1-pro-preview is a bad arm for simple (success=100% but latency=8s, cost=$0.01)
        for _ in range(40):
            recommended = self.bandit.select_arm("SIMPLE")
            
            # Simulate real model response properties
            if recommended == "local":
                self.bandit.record_feedback("SIMPLE", "local", success=True, latency=1.0, cost=0.0)
            elif recommended == "gemini-3.1-flash-lite":
                self.bandit.record_feedback("SIMPLE", "gemini-3.1-flash-lite", success=True, latency=1.1, cost=0.00025)
            elif recommended == "gemini-3.1-flash-lite-preview":
                self.bandit.record_feedback("SIMPLE", "gemini-3.1-flash-lite-preview", success=True, latency=1.2, cost=0.000125)
            elif recommended == "gemini-3-flash-preview":
                self.bandit.record_feedback("SIMPLE", "gemini-3-flash-preview", success=True, latency=1.5, cost=0.00025)
            elif recommended == "gemini-3.5-flash":
                self.bandit.record_feedback("SIMPLE", "gemini-3.5-flash", success=True, latency=0.8, cost=0.0015)
            else:
                self.bandit.record_feedback("SIMPLE", "gemini-3.1-pro-preview", success=True, latency=8.0, cost=0.01)

        stats = self.bandit.load_stats()
        simple_arms = stats["contexts"]["SIMPLE"]["arms"]

        # local should have significantly more selections than pro-preview due to higher utility
        self.assertGreater(simple_arms["local"]["selections"], simple_arms["gemini-3.1-pro-preview"]["selections"])
        print(f"🎉 Convergence Test passed. Local selections: {simple_arms['local']['selections']} | Pro selections: {simple_arms['gemini-3.1-pro-preview']['selections']}")

if __name__ == "__main__":
    unittest.main()
