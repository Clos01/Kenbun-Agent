import unittest
import os
import tempfile
from tools.codebase.code_integrity_sentinel import CodeIntegritySentinel, audit_code_integrity


class TestCodeIntegritySentinel(unittest.TestCase):
    def setUp(self):
        self.sentinel = CodeIntegritySentinel()

    def test_detect_unquoted_dict_key_lookup(self):
        """Test catching .get(undefined_variable) that should be a string literal."""
        bad_code = """
def process_result(res):
    delta = res.get(screen_delta_after, 0.0)
    return delta
"""
        audit = self.sentinel.audit_code_string(bad_code)
        self.assertFalse(audit["valid"])
        self.assertEqual(len(audit["unquoted_dict_lookups"]), 1)
        self.assertEqual(audit["unquoted_dict_lookups"][0]["variable_passed"], "screen_delta_after")

    def test_autofix_unquoted_dict_key_lookup(self):
        """Test auto-quoting undefined dictionary keys."""
        bad_code = "delta = res.get(screen_delta_after, 0.0)"
        fixed_code, fixes = self.sentinel.autofix_code_string(bad_code)
        self.assertIn("res.get('screen_delta_after', 0.0)", fixed_code)
        self.assertEqual(len(fixes), 1)

    def test_detect_and_autofix_missing_imports(self):
        """Test detecting and auto-injecting missing standard library imports."""
        bad_code = """
def save_data(data):
    time.sleep(1)
    return json.dumps(data)
"""
        audit = self.sentinel.audit_code_string(bad_code)
        self.assertFalse(audit["valid"])
        missing = [m["symbol"] for m in audit["missing_imports"]]
        self.assertIn("time", missing)
        self.assertIn("json", missing)

        fixed_code, fixes = self.sentinel.autofix_code_string(bad_code)
        self.assertIn("import time", fixed_code)
        self.assertIn("import json", fixed_code)

    def test_audit_valid_clean_code(self):
        """Test that properly scoped and imported code passes with zero issues."""
        clean_code = """import json
import time

def process_payload(data: dict) -> str:
    time.sleep(0.01)
    status = data.get("status", "unknown")
    return json.dumps({"status": status})
"""
        audit = self.sentinel.audit_code_string(clean_code)
        self.assertTrue(audit["valid"])
        self.assertEqual(audit["issues_count"], 0)

    def test_sovereign_tool_interface(self):
        """Test audit_code_integrity sovereign tool wrapper."""
        snippet = "val = res.get(my_unquoted_key)"
        res = audit_code_integrity(target=snippet, autofix=True)
        self.assertIn("res.get('my_unquoted_key')", res["fixed_code"])


if __name__ == "__main__":
    unittest.main()
