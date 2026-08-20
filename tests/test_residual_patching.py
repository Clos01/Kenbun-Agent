"""
Test Suite: Forward Stagewise Residual Patching (ESL Ch. 10)
============================================================
Validates that the healer performs a STAGEWISE UPDATE -- f_m = f_{m-1} + h_m,
where h_m touches only the residual -- rather than a full regeneration.

The property under test is not "the output is correct code" (the healer LLM
decides that); it is "whatever the healer proposed, we applied it minimally,
verified it, and refused it when it was untrustworthy."
"""

import pytest

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


# ------------------------------------------------------------------
# compute_residual
# ------------------------------------------------------------------

def test_residual_snaps_to_real_code_not_the_comment():
    """The critique says line 5; line 5 is a comment. The residual must point at
    the cursor.execute on line 6, or the healer gets a target with no defect."""
    residual = compute_residual(VULNERABLE_CODE, SQL_CRITIQUE)
    assert residual["target_lines"] == [6], residual["target_lines"]
    source = residual["target_source"][0]["code"]
    assert "cursor.execute" in source


def test_residual_identifies_enclosing_function():
    residual = compute_residual(VULNERABLE_CODE, SQL_CRITIQUE)
    assert residual["target_definitions"] == ["authenticate_user"]
    assert "unrelated_helper" not in residual["target_definitions"]


def test_residual_classifies_risk_and_validates_syntax():
    residual = compute_residual(VULNERABLE_CODE, SQL_CRITIQUE)
    assert "sql_injection" in residual["risk_categories"]
    assert residual["syntax_valid"] is True


def test_residual_reports_syntax_error_location():
    broken = "def f(:\n    return 1\n"
    residual = compute_residual(broken, "Fix the syntax error")
    assert residual["syntax_valid"] is False
    assert residual["syntax_error"]


def test_residual_ignores_out_of_range_line_refs():
    """A critique citing line 900 of a 12-line file must not produce a target."""
    residual = compute_residual(VULNERABLE_CODE, "Problem at line 900.")
    assert residual["target_lines"] == []


# ------------------------------------------------------------------
# build_residual_prompt
# ------------------------------------------------------------------

def test_prompt_demands_hunks_not_a_rewrite():
    """This is the assertion that makes the ESL-10 claim honest: the prompt must
    ask for a patch. The previous version asked for 'the complete healed code',
    which is a fresh fit, not a stagewise update."""
    residual = compute_residual(VULNERABLE_CODE, SQL_CRITIQUE)
    system_prompt, user_message = build_residual_prompt(VULNERABLE_CODE, residual, "Secure auth")

    assert SEARCH_MARKER in system_prompt
    assert REPLACE_MARKER in system_prompt
    assert "do not rewrite the file" in system_prompt.lower()
    assert "complete, healed executable code" not in system_prompt

    # The residual's findings must actually reach the model.
    assert "authenticate_user" in user_message
    assert "sql_injection" in user_message


# ------------------------------------------------------------------
# hunk application
# ------------------------------------------------------------------

def test_parse_and_apply_single_hunk():
    patch = _hunk(
        "    cursor.execute(f'SELECT * FROM accounts WHERE id = {user_id}')",
        "    cursor.execute('SELECT * FROM accounts WHERE id = %s', (user_id,))",
    )
    hunks = parse_patch_hunks(patch)
    assert len(hunks) == 1

    patched, errors = apply_patch_hunks(VULNERABLE_CODE, hunks)
    assert errors == []
    assert "%s" in patched
    assert "f'SELECT" not in patched


def test_ambiguous_search_block_is_rejected_not_guessed():
    code = "x = 1\ny = 2\nx = 1\n"
    hunks = [("x = 1", "x = 42")]
    patched, errors = apply_patch_hunks(code, hunks)
    assert patched is None
    assert "ambiguous" in errors[0]


def test_missing_search_block_is_rejected():
    hunks = [("this text is not in the file", "replacement")]
    patched, errors = apply_patch_hunks(VULNERABLE_CODE, hunks)
    assert patched is None
    assert "not found" in errors[0]


def test_partial_patch_is_all_or_nothing():
    """One good hunk plus one bad hunk must apply neither."""
    good = ("    return cursor.fetchone()", "    return cursor.fetchone() or {}")
    bad = ("nonexistent line", "whatever")
    patched, errors = apply_patch_hunks(VULNERABLE_CODE, [good, bad])
    assert patched is None
    assert errors


# ------------------------------------------------------------------
# apply_stagewise_patch — the stagewise guarantee
# ------------------------------------------------------------------

def test_stagewise_patch_leaves_passing_code_byte_identical():
    """The core boosting property: h_m touches the residual and nothing else."""
    patch = _hunk(
        "    cursor.execute(f'SELECT * FROM accounts WHERE id = {user_id}')",
        "    cursor.execute('SELECT * FROM accounts WHERE id = %s', (user_id,))",
    )
    healed, stats = apply_stagewise_patch_verbose(VULNERABLE_CODE, patch)

    assert stats["mode"] == "stagewise"
    assert stats["hunks"] == 1
    assert stats["modified_definitions"] == ["authenticate_user"]
    assert stats["collateral_definitions"] == []

    # The untouched function survives verbatim.
    assert "def unrelated_helper(value):\n    # This function is passing and must never be touched.\n    return value.strip().lower()" in healed


def test_stagewise_patch_changes_few_lines():
    """A stagewise update must not rewrite the file. Two changed lines (one
    removed, one added) out of twelve."""
    patch = _hunk(
        "    cursor.execute(f'SELECT * FROM accounts WHERE id = {user_id}')",
        "    cursor.execute('SELECT * FROM accounts WHERE id = %s', (user_id,))",
    )
    _, stats = apply_stagewise_patch_verbose(VULNERABLE_CODE, patch)
    assert stats["changed_lines"] <= 4, stats
    assert stats["total_lines"] == len(VULNERABLE_CODE.splitlines())


def test_syntax_regression_is_rejected():
    patch = _hunk(
        "    return cursor.fetchone()",
        "    return cursor.fetchone(",  # unbalanced paren
    )
    healed, stats = apply_stagewise_patch_verbose(VULNERABLE_CODE, patch)
    assert healed == VULNERABLE_CODE
    assert stats["mode"] == "rejected"
    assert any("syntax" in e for e in stats["errors"])


def test_identical_candidate_is_rejected():
    patch = _hunk("    return cursor.fetchone()", "    return cursor.fetchone()")
    healed, stats = apply_stagewise_patch_verbose(VULNERABLE_CODE, patch)
    assert healed == VULNERABLE_CODE
    assert stats["mode"] == "rejected"


def test_empty_candidate_returns_original():
    assert apply_stagewise_patch(VULNERABLE_CODE, "") == VULNERABLE_CODE
    assert apply_stagewise_patch(VULNERABLE_CODE, "   \n  ") == VULNERABLE_CODE


def test_full_rewrite_is_flagged_as_fallback_not_stagewise():
    """Models disobey the format. We still accept it, but we must not call it a
    stagewise patch -- that mislabelling is what made the original claim false."""
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
    assert stats["mode"] == "full_rewrite"
    assert healed != VULNERABLE_CODE
    # And the collateral damage is detected and reported, not hidden.
    assert "unrelated_helper (removed)" in stats["collateral_definitions"]


def test_strict_mode_refuses_full_rewrite():
    rewrite = "def authenticate_user(user_id):\n    return None\n"
    healed, stats = apply_stagewise_patch_verbose(
        VULNERABLE_CODE, rewrite, allow_full_rewrite=False
    )
    assert healed == VULNERABLE_CODE
    assert stats["mode"] == "rejected"
