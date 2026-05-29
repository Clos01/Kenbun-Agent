import unittest
import os
import json
import threading
import shutil
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from tools.strategy.token_governor import TokenGovernor
from tools.infrastructure.config import settings

class TestTokenGovernor(unittest.TestCase):
    def setUp(self):
        # Configure a test usage stats file in the brain health directory
        self.test_log_dir = settings.BRAIN_HEALTH_DIR / "test_runs"
        self.test_log_dir.mkdir(parents=True, exist_ok=True)
        self.test_log_file = self.test_log_dir / "test_usage_stats.json"
        
        # If it already exists, clear it
        if self.test_log_file.exists():
            self.test_log_file.unlink()
            
        # Instantiate governor with a $5.00 daily budget for testing
        self.governor = TokenGovernor(daily_budget=5.00)
        self.governor.log_file = self.test_log_file
        self.governor._ensure_log_exists()

    def tearDown(self):
        # Clean up test directories
        if self.test_log_dir.exists():
            shutil.rmtree(self.test_log_dir)

    def test_initialization(self):
        """Verifies stats are correctly initialized with baseline seeded values."""
        stats = self.governor._get_stats_unlocked()
        self.assertEqual(stats["daily_total"], 0.0)
        self.assertEqual(stats["monthly_total"], 0.0)
        self.assertEqual(stats["total_spend"], 0.0)
        self.assertEqual(stats["date"], str(datetime.now(timezone.utc).date()))

    def test_daily_rollover(self):
        """Verifies that changing dates resets daily totals but preserves monthly/lifetime spends."""
        stats = self.governor._get_stats_unlocked()
        stats["daily_total"] = 2.50
        stats["monthly_total"] = 5.00
        stats["total_spend"] = 20.00
        # Set date to yesterday in UTC
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        stats["date"] = str(yesterday.date())
        self.governor._save_stats_unlocked(stats)

        # Call get stats - should trigger rollover
        new_stats = self.governor._get_stats_unlocked()
        self.assertEqual(new_stats["daily_total"], 0.0) # Reset
        self.assertEqual(new_stats["monthly_total"], 5.00) # Preserved (same month)
        self.assertEqual(new_stats["total_spend"], 20.00) # Preserved
        self.assertEqual(new_stats["date"], str(datetime.now(timezone.utc).date()))

    def test_monthly_rollover(self):
        """Verifies that changing months resets monthly totals."""
        stats = self.governor._get_stats_unlocked()
        stats["daily_total"] = 2.50
        stats["monthly_total"] = 5.00
        stats["total_spend"] = 20.00
        # Set date to 32 days ago in UTC
        last_month = datetime.now(timezone.utc) - timedelta(days=32)
        stats["date"] = str(last_month.date())
        self.governor._save_stats_unlocked(stats)

        # Call get stats - should trigger daily and monthly rollovers
        new_stats = self.governor._get_stats_unlocked()
        self.assertEqual(new_stats["daily_total"], 0.0) # Reset
        self.assertEqual(new_stats["monthly_total"], 0.0) # Reset
        self.assertEqual(new_stats["total_spend"], 20.00) # Preserved
        self.assertEqual(new_stats["date"], str(datetime.now(timezone.utc).date()))

    def test_tracking_and_budget_checks(self):
        """Verifies that tracking usage correctly computes costs, tokens, and can_spend limits."""
        # 1M input tokens on Gemini 3.1 Pro is $1.25, 1M output is $5.00
        cost = self.governor.track_usage(
            model="gemini-3.1-pro-preview",
            input_tokens=1_000_000,
            output_tokens=500_000,
            task_id="test_task"
        )
        self.assertEqual(cost, 3.75) # 1.25 + 2.50 = 3.75
        
        # Total daily spend should be 3.75, daily budget is 5.00
        self.assertTrue(self.governor.can_spend(estimated_cost=0.50)) # 4.25 <= 5.00
        self.assertFalse(self.governor.can_spend(estimated_cost=1.50)) # 5.25 > 5.00
        self.assertAlmostEqual(self.governor.get_remaining_budget(), 1.25)
        
        # Validate that actual token counters were recorded and saved
        stats = self.governor._get_stats_unlocked()
        self.assertEqual(stats["daily_input_tokens"], 1_000_000)
        self.assertEqual(stats["daily_output_tokens"], 500_000)
        self.assertEqual(stats["monthly_input_tokens"], 1_000_000)
        self.assertEqual(stats["monthly_output_tokens"], 500_000)
        self.assertEqual(stats["total_input_tokens"], 1_000_000)
        self.assertEqual(stats["total_output_tokens"], 500_000)

    def test_dynamic_downgrade(self):
        """Verifies that model selection downgrades as budget depletes."""
        # 1. At 100% budget, Pro remains Pro
        model = self.governor.get_budget_aware_model("gemini-3.1-pro-preview", task_critical=False)
        self.assertEqual(model, "gemini-3.1-pro-preview")
        
        # 2. Consume 60% budget ($3.00 out of $5.00 budget) -> Low Budget (Pro downgrades to 3.5 Flash)
        self.governor.track_usage(
            model="gemini-3.1-pro-preview",
            input_tokens=3_000_000,
            output_tokens=0,
            task_id="spend_3"
        )
        model = self.governor.get_budget_aware_model("gemini-3.1-pro-preview", task_critical=False)
        self.assertEqual(model, "gemini-3.5-flash")

        # 3. Consume more or call on 3.5-flash -> Low budget downgrades 3.5-flash to flash-preview
        model_flash = self.governor.get_budget_aware_model("gemini-3.5-flash", task_critical=False)
        self.assertEqual(model_flash, "gemini-3-flash-preview")
        
        # Critical tasks should not downgrade at 60%
        model_crit = self.governor.get_budget_aware_model("gemini-3.1-pro-preview", task_critical=True)
        self.assertEqual(model_crit, "gemini-3.1-pro-preview")
        
        # 4. Consume up to 92% budget ($4.60 out of $5.00) -> Critical Depletion (Forced LOCAL mode)
        self.governor.track_usage(
            model="gemini-3.1-pro-preview",
            input_tokens=1_600_000,
            output_tokens=0,
            task_id="spend_1_6"
        )
        model_crit_depleted = self.governor.get_budget_aware_model("gemini-3.1-pro-preview", task_critical=True)
        self.assertEqual(model_crit_depleted, "local")

    def test_concurrency_stress(self):
        """Spawns 10 parallel threads tracking usage to guarantee zero race conditions and exact arithmetic."""
        num_threads = 10
        calls_per_thread = 20
        token_count = 10_000 # Cost per call is 10k * (1.00 / 1M) = 0.01
        
        threads = []
        for i in range(num_threads):
            t = threading.Thread(
                target=self._run_concurrent_tracks,
                args=(calls_per_thread, token_count)
            )
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        # Verify final values in stats file
        stats = self.governor._get_stats_unlocked()
        expected_cost = num_threads * calls_per_thread * 0.0125 # 10 * 20 * 0.0125 = 2.50
        
        self.assertAlmostEqual(stats["daily_total"], expected_cost, places=5)
        # Verify total lifetime spend matches base seeded spend (0.0) + 2.50
        self.assertAlmostEqual(stats["total_spend"], expected_cost, places=5)
        # Verify history was successfully truncated to the 100 limit to prevent memory bloat
        self.assertEqual(len(stats["history"]), 100)

    def _run_concurrent_tracks(self, count, tokens):
        for _ in range(count):
            self.governor.track_usage(
                model="gemini-3.1-pro-preview",
                input_tokens=tokens,
                output_tokens=0,
                task_id="stress_test"
            )

    def test_read_write_lock_concurrency_stress(self):
        """Spawns concurrent read threads and write threads to prove zero deadlocks and correct read/write operations."""
        num_write_threads = 5
        num_read_threads = 5
        calls_per_thread = 20
        token_count = 10_000 # 0.0125 per write call
        
        threads = []
        stop_reads = threading.Event()
        
        # 1. Start writer threads
        for i in range(num_write_threads):
            t = threading.Thread(
                target=self._run_concurrent_tracks,
                args=(calls_per_thread, token_count)
            )
            threads.append(t)
            t.start()
            
        # 2. Start reader threads
        def _run_concurrent_reads():
            while not stop_reads.is_set():
                # Perform various reads
                self.governor.can_spend(estimated_cost=0.01)
                self.governor.get_remaining_budget()
                self.governor.get_budget_aware_model("gemini-3.1-pro-preview", task_critical=False)
                # Brief sleep to avoid starvation
                time.sleep(0.01)
                
        read_threads = []
        for i in range(num_read_threads):
            t = threading.Thread(target=_run_concurrent_reads)
            read_threads.append(t)
            t.start()
            
        # 3. Wait for all writers to complete
        for t in threads:
            t.join()
            
        # 4. Stop readers and wait for them to finish
        stop_reads.set()
        for t in read_threads:
            t.join()
            
        # 5. Verify final write values
        stats = self.governor._get_stats_unlocked()
        expected_cost = num_write_threads * calls_per_thread * 0.0125
        self.assertAlmostEqual(stats["daily_total"], expected_cost, places=5)

if __name__ == "__main__":
    unittest.main()
