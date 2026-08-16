"""
test_antigravity_integration.py — Unit tests for Antigravity 2.0 platform scoping and Hivemind memory.
"""
import os
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

# Add core path to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.utils.ide_context import (
    get_caller_ide,
    is_antigravity_ide,
    is_claude_ide,
    uses_external_review,
    get_ide_capabilities,
    log_ide_context,
)
from hivemind_memory.hive_memory import hive_memory


class TestAntigravityIntegration(unittest.TestCase):

    def test_explicit_antigravity(self):
        """Test explicit KENBUN_CALLER_IDE=antigravity context."""
        with patch.dict(os.environ, {"KENBUN_CALLER_IDE": "antigravity"}):
            self.assertEqual(get_caller_ide(), "antigravity")
            self.assertTrue(is_antigravity_ide())
            self.assertFalse(is_claude_ide())
            self.assertFalse(uses_external_review())

            caps = get_ide_capabilities()
            self.assertIn("/goal", caps.get("slash_commands", []))
            self.assertIn("/grill-me", caps.get("slash_commands", []))
            self.assertIn("/schedule", caps.get("slash_commands", []))
            self.assertIn("/browser", caps.get("slash_commands", []))

    def test_explicit_claude(self):
        """Test explicit KENBUN_CALLER_IDE=claude context."""
        with patch.dict(os.environ, {"KENBUN_CALLER_IDE": "claude"}):
            self.assertEqual(get_caller_ide(), "claude")
            self.assertTrue(is_claude_ide())
            self.assertFalse(is_antigravity_ide())
            self.assertFalse(uses_external_review())

    def test_auto_detect_antigravity(self):
        """Test auto-detection heuristics for Antigravity 2.0."""
        env = {}
        env["ANTIGRAVITY_APP"] = "1"
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(get_caller_ide(), "antigravity")
            self.assertTrue(is_antigravity_ide())

    def test_log_formatting(self):
        """Test header output formatting."""
        with patch.dict(os.environ, {"KENBUN_CALLER_IDE": "antigravity"}):
            log_output = log_ide_context()
            self.assertIn("Google Antigravity 2.0 / IDE", log_output)
            self.assertIn("/goal", log_output)

    def test_hivemind_query(self):
        """Test querying past fixes / concepts from local Hivemind memory."""
        results = hive_memory.query("Antigravity 2.0", limit=5)
        # Verify query method runs cleanly without errors
        self.assertIsInstance(results, list)


if __name__ == "__main__":
    unittest.main()
