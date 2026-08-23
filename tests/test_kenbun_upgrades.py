"""
Unit Tests for Kenbun 2.0 Architectural Upgrades:
- PhantomDrive (OpenViking File-Based Memory System)
- SwitchYard (Local-First Cost Escalation Router)
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from core.tools.memory.phantom_drive import PhantomDrive
from core.tools.strategy.switchyard_router import ModelTier, SwitchyardRouter


class TestPhantomDrive(unittest.TestCase):
    """Test file-based memory operations, search, and context assembly."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.drive = PhantomDrive(base_path=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_and_read_domain_context(self):
        path = self.drive.write_domain_context("database_layer", "# PostgreSQL & Supabase RLS")
        self.assertTrue(os.path.exists(path))
        
        content = self.drive.read_domain_context("database_layer")
        self.assertIsNotNone(content)
        self.assertIn("PostgreSQL & Supabase RLS", content)

    def test_record_decision_and_anti_pattern(self):
        dec_path = self.drive.record_decision(
            "002",
            "SwitchYard Escalation Router Adoption",
            "Need to minimize token expenditure across swarm.",
            "Adopt 3-tier local-first escalation routing.",
            "80% reduction in cloud LLM costs."
        )
        self.assertTrue(os.path.exists(dec_path))

        ap_path = self.drive.record_anti_pattern(
            "002",
            "Hardcoded Port Bindings",
            "Binding to fixed port 8080 caused collisions.",
            "Use environment variable overrides and port scanners.",
            reference_id="ref_99218"
        )
        self.assertTrue(os.path.exists(ap_path))

    def test_search_memory(self):
        self.drive.write_domain_context("security", "Zero-trust authentication and JWT validation.")
        results = self.drive.search_memory("Zero-trust")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["category"], "domains")

    def test_get_active_context_bundle(self):
        self.drive.record_anti_pattern("003", "Test Pitfall", "Mistake made", "Fix applied")
        bundle = self.drive.get_active_context_bundle()
        self.assertIn("KENBUN PHANTOM DRIVE MEMORY BUNDLE", bundle)
        self.assertIn("Test Pitfall", bundle)


class TestSwitchyardRouter(unittest.TestCase):
    """Test model tier classification and cost escalation routing."""

    def setUp(self):
        self.router = SwitchyardRouter(local_vlm_url="http://127.0.0.1:9999/v1")  # Unreachable local URL for escalation test

    def test_tier_classification(self):
        tier_visual = self.router.classify_initial_tier("Click the start menu icon", is_visual=True)
        self.assertEqual(tier_visual, ModelTier.TIER_0_LOCAL)

        tier_arch = self.router.classify_initial_tier("Refactor architecture and security consensus")
        self.assertEqual(tier_arch, ModelTier.TIER_2_ARCHITECT)

        tier_routine = self.router.classify_initial_tier("Summarize this README file")
        self.assertEqual(tier_routine, ModelTier.TIER_1_TURBO)

    def test_escalation_on_unavailable_tier0(self):
        # Visual task should attempt Tier 0, discover mock URL is down, and escalate to Tier 1
        res = self.router.route_and_execute("Click on the Firefox icon")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["escalated"])
        self.assertIn(ModelTier.TIER_0_LOCAL.value, res["attempted_tiers"])
        self.assertIn(ModelTier.TIER_1_TURBO.value, res["attempted_tiers"])


if __name__ == "__main__":
    unittest.main()
