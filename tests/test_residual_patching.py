"""
Test Suite: Forward Stagewise Residual Patching (ESL Ch. 10)
============================================================
Validates that the healer performs a STAGEWISE UPDATE -- f_m = f_{m-1} + h_m,
where h_m touches only the residual -- rather than a full regeneration.
"""

import unittest

try:
    from tools.audit.residual_patcher import (
        compute_residual,
        build_residual_prompt,
        apply_stagewise_patch,
        apply_stagewise_patch_verbose,
        parse_patch_hunks,
        apply_patch_hunks,
        SEARCH_MARKER,
        DIVIDER_MARKER,
        REPLACE_MARKER,
    )
except ImportError:
    from core.tools.audit.residual_patcher import (
        compute_residual,
        build_residual_prompt,
        apply_stagewise_patch,
        apply_stagewise_patch_verbose,
        parse_patch_hunks,
        apply_patch_hunks,
        SEARCH_MARKER,
        DIVIDER_MARKER,
        REPLACE_MARKER,
    )


VULNERABLE_CODE = (
    "def authenticate_user(user_id):\n"
    "    if not user_id:\n"
    "        return None\n"
    "\n"
    "    # OFFENDING LINE (residual defect)\n"
    "    cursor.execute(f'SELECT * FROM accounts WHERE id = {user_id}')\n"
    "    return cursor.fetchone()\n"
    "\n"
    "\n"
    "def unrelated_helper(value):\n"
    "    # This function is passing and must never be touched.\n"
    "    return value.strip().lower()\n"
)

SQL_CRITIQUE = (
    "CRITICAL SECURITY REJECTION: SQL injection vulnerability detected at line 5. "
    "Dynamic f-string formatting in cursor.execute must be replaced with a parameterized query."
)


def _hunk(search: str, replace: str) -> str:
    return f"{SEARCH_MARKER}\n{search}\n{DIVIDER_MARKER}\n{replace}\n{REPLACE_MARKER}"


class TestResidualPatching(unittest.TestCase):

    def test_residual_snaps_to_real_code_not_the_comment(self):
        residual = compute_residual(VULNERABLE_CODE, SQL_CRITIQUE)
        self.assertEqual(residual["target_lines"], [6])
        source = residual["target_source"][0]["code"]
        self.assertIn("cursor.execute", source)

    def test_residual_identifies_enclosing_function(self):
        residual = compute_residual(VULNERABLE_CODE, SQL_CRITIQUE)
        self.assertEqual(residual["target_definitions"], ["authenticate_user"])
        self.assertNotIn("unrelated_helper", residual["target_definitions"])

    def test_residual_classifies_risk_and_validates_syntax(self):
        residual = compute_residual(VULNERABLE_CODE, SQL_CRITIQUE)
        self.assertIn("sql_injection", residual["risk_categories"])
        self.assertTrue(residual["syntax_valid"])

    def test_residual_reports_syntax_error_location(self):
        broken = "def f(:\n    return 1\n"
        residual = compute_residual(broken, "Fix the syntax error")
        self.assertFalse(residual["syntax_valid"])
        self.assertTrue(bool(residual["syntax_error"]))

    def test_residual_ignores_out_of_range_line_refs(self):
        residual = compute_residual(VULNERABLE_CODE, "Problem at line 900.")
        self.assertEqual(residual["target_lines"], [])

    def test_prompt_demands_hunks_not_a_rewrite(self):
        residual = compute_residual(VULNERABLE_CODE, SQL_CRITIQUE)
        system_prompt, user_message = build_residual_prompt(VULNERABLE_CODE, residual, "Secure auth")

        self.assertIn(SEARCH_MARKER, system_prompt)
        self.assertIn(REPLACE_MARKER, system_prompt)
        self.assertIn("do not rewrite the file", system_prompt.lower())
        self.assertNotIn("complete, healed executable code", system_prompt)
        self.assertIn("authenticate_user", user_message)
        self.assertIn("sql_injection", user_message)

    def test_parse_and_apply_single_hunk(self):
        patch = _hunk(
            "    cursor.execute(f'SELECT * FROM accounts WHERE id = {user_id}')",
            "    cursor.execute('SELECT * FROM accounts WHERE id = %s', (user_id,))",
        )
        hunks = parse_patch_hunks(patch)
        self.assertEqual(len(hunks), 1)

        patched, errors = apply_patch_hunks(VULNERABLE_CODE, hunks)
        self.assertEqual(errors, [])
        self.assertIn("%s", patched)
        self.assertNotIn("f'SELECT", patched)

    def test_ambiguous_search_block_is_rejected_not_guessed(self):
        code = "x = 1\ny = 2\nx = 1\n"
        hunks = [("x = 1", "x = 42")]
        patched, errors = apply_patch_hunks(code, hunks)
        self.assertIsNone(patched)
        self.assertIn("ambiguous", errors[0])

    def test_missing_search_block_is_rejected(self):
        hunks = [("this text is not in the file", "replacement")]
        patched, errors = apply_patch_hunks(VULNERABLE_CODE, hunks)
        self.assertIsNone(patched)
        self.assertIn("not found", errors[0])

    def test_partial_patch_is_all_or_nothing(self):
        good = ("    return cursor.fetchone()", "    return cursor.fetchone() or {}")
        bad = ("nonexistent line", "whatever")
        patched, errors = apply_patch_hunks(VULNERABLE_CODE, [good, bad])
        self.assertIsNone(patched)
        self.assertTrue(bool(errors))

    def test_stagewise_patch_leaves_passing_code_byte_identical(self):
        patch = _hunk(
            "    cursor.execute(f'SELECT * FROM accounts WHERE id = {user_id}')",
            "    cursor.execute('SELECT * FROM accounts WHERE id = %s', (user_id,))",
        )
        healed, stats = apply_stagewise_patch_verbose(VULNERABLE_CODE, patch)

        self.assertEqual(stats["mode"], "stagewise")
        self.assertEqual(stats["hunks"], 1)
        self.assertEqual(stats["modified_definitions"], ["authenticate_user"])
        self.assertEqual(stats["collateral_definitions"], [])
        self.assertIn("def unrelated_helper(value):\n    # This function is passing and must never be touched.\n    return value.strip().lower()", healed)

    def test_stagewise_patch_changes_few_lines(self):
        patch = _hunk(
            "    cursor.execute(f'SELECT * FROM accounts WHERE id = {user_id}')",
            "    cursor.execute('SELECT * FROM accounts WHERE id = %s', (user_id,))",
        )
        _, stats = apply_stagewise_patch_verbose(VULNERABLE_CODE, patch)
        self.assertLessEqual(stats["changed_lines"], 4)
        self.assertEqual(stats["total_lines"], len(VULNERABLE_CODE.splitlines()))

    def test_syntax_regression_is_rejected(self):
        patch = _hunk(
            "    return cursor.fetchone()",
            "    return cursor.fetchone(",
        )
        healed, stats = apply_stagewise_patch_verbose(VULNERABLE_CODE, patch)
        self.assertEqual(healed, VULNERABLE_CODE)
        self.assertEqual(stats["mode"], "rejected")
        self.assertTrue(any("syntax" in e for e in stats["errors"]))

    def test_identical_candidate_is_rejected(self):
        patch = _hunk("    return cursor.fetchone()", "    return cursor.fetchone()")
        healed, stats = apply_stagewise_patch_verbose(VULNERABLE_CODE, patch)
        self.assertEqual(healed, VULNERABLE_CODE)
        self.assertEqual(stats["mode"], "rejected")

    def test_empty_candidate_returns_original(self):
        self.assertEqual(apply_stagewise_patch(VULNERABLE_CODE, ""), VULNERABLE_CODE)
        self.assertEqual(apply_stagewise_patch(VULNERABLE_CODE, "   \n  "), VULNERABLE_CODE)

    def test_full_rewrite_is_flagged_as_fallback_not_stagewise(self):
        rewrite = (
            "```python\n"
            "def authenticate_user(user_id):\n"
            "    if not user_id:\n"
            "        return None\n"
            "    cursor.execute('SELECT * FROM accounts WHERE id = %s', (user_id,))\n"
            "    return cursor.fetchone()\n"
            "```"
        )
        healed, stats = apply_stagewise_patch_verbose(VULNERABLE_CODE, rewrite)
        self.assertEqual(stats["mode"], "full_rewrite")
        self.assertNotEqual(healed, VULNERABLE_CODE)
        self.assertIn("unrelated_helper (removed)", stats["collateral_definitions"])

    def test_strict_mode_refuses_full_rewrite(self):
        rewrite = "def authenticate_user(user_id):\n    return None\n"
        healed, stats = apply_stagewise_patch_verbose(
            VULNERABLE_CODE, rewrite, allow_full_rewrite=False
        )
        self.assertEqual(healed, VULNERABLE_CODE)
        self.assertEqual(stats["mode"], "rejected")


if __name__ == "__main__":
    unittest.main()
