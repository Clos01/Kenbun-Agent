"""
Live End-to-End Integration Check for the ESL Upgrades
======================================================
Unlike the unit suites (which stub the intelligence store and the healer model),
this script exercises the three upgrades against the REAL runtime: the live
Postgres posteriors, the live tool registry, and the real production call sites.

It asserts. A failed expectation exits non-zero. Nothing here prints a success
banner it has not earned.

Run:  python3 scripts/testing/test_esl_live_integration.py
"""

import sys
import traceback
from pathlib import Path

core_dir = Path(__file__).resolve().parent.parent.parent / "core"
sys.path.insert(0, str(core_dir))

from tools.utils.bayesian import rank_tools_thompson, get_posterior_params_batch  # noqa: E402
from tools.audit.residual_patcher import (  # noqa: E402
    compute_residual,
    build_residual_prompt,
    apply_stagewise_patch_verbose,
    SEARCH_MARKER,
    DIVIDER_MARKER,
    REPLACE_MARKER,
)
from tools.utils.sparse_gating import build_registry_tool_map, gated_tool_catalog  # noqa: E402

FAILURES = []


def check(condition, label, detail=""):
    if condition:
        print(f"  ✅ {label}")
    else:
        print(f"  ❌ {label}" + (f" — {detail}" if detail else ""))
        FAILURES.append(label)


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ----------------------------------------------------------------------
# 1. Thompson Sampling against the live intelligence store
# ----------------------------------------------------------------------

def test_live_thompson_sampling():
    section("1. Bayesian Thompson Sampling — live posteriors (ESL Ch. 8 & 16)")

    candidates = ["consult_supervisor", "ask_architect", "run_code_safely"]
    params = get_posterior_params_batch(candidates, "security")
    print(f"Live posteriors from the intelligence store: {params or '(none stored — uniform priors)'}")

    counts = {c: 0 for c in candidates}
    trials = 500
    for _ in range(trials):
        ranked = rank_tools_thompson("security", candidates)
        counts[ranked[0][0]] += 1

    print(f"\n{trials} draws:")
    for tool, n in counts.items():
        pct = n / trials * 100
        print(f"  {tool:<25} {n:>4} ({pct:>5.1f}%) {'█' * int(pct // 2)}")

    check(sum(counts.values()) == trials, "every draw selected exactly one tool")
    check(all(n > 0 for n in counts.values()),
          "no candidate is starved (all explored at least once)",
          f"counts={counts}")

    greedy = rank_tools_thompson("security", candidates, exploration_mode=False)
    greedy_repeat = rank_tools_thompson("security", candidates, exploration_mode=False)
    print(f"\nDeterministic mode order: {[t for t, _ in greedy]}")
    check(greedy == greedy_repeat, "deterministic mode is reproducible")

    # Production wiring: the router must consult the sampler.
    from tools.strategy.decision_logic import router
    ordered = router.recommend_tools("fix the SQL injection in the auth handler")
    print(f"router.recommend_tools -> {ordered}")
    check(isinstance(ordered, list) and len(ordered) > 0, "router.recommend_tools returns candidates")
    check(set(ordered) == set(router._PATH_TOOLS[router.get_strategy_path(
        "fix the SQL injection in the auth handler")]),
        "router returns the path's candidate set (reordered, not truncated)")


# ----------------------------------------------------------------------
# 2. Residual patching — real minimal patch, real verification
# ----------------------------------------------------------------------

def test_live_residual_patching():
    section("2. Forward Stagewise Residual Patching (ESL Ch. 10)")

    original = (
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
        "    return value.strip().lower()\n"
    )
    critique = (
        "CRITICAL SECURITY REJECTION: SQL injection vulnerability detected at line 5. "
        "Dynamic f-string formatting in cursor.execute must use a parameterized query."
    )

    residual = compute_residual(original, critique)
    print(f"Residual r_m: lines={residual['target_lines']} "
          f"defs={residual['target_definitions']} risks={residual['risk_categories']}")

    check(residual["target_lines"] == [6],
          "residual snapped past the comment onto the real offending line",
          f"got {residual['target_lines']}")
    check(residual["target_definitions"] == ["authenticate_user"],
          "residual located the enclosing function")
    check("sql_injection" in residual["risk_categories"], "residual classified the risk")

    system_prompt, _ = build_residual_prompt(original, residual, "Secure authentication")
    check(SEARCH_MARKER in system_prompt and REPLACE_MARKER in system_prompt,
          "prompt demands SEARCH/REPLACE hunks (a patch, not a rewrite)")

    # A hunk of the shape the healer is instructed to produce.
    patch = (
        f"{SEARCH_MARKER}\n"
        "    cursor.execute(f'SELECT * FROM accounts WHERE id = {user_id}')\n"
        f"{DIVIDER_MARKER}\n"
        "    cursor.execute('SELECT * FROM accounts WHERE id = %s', (user_id,))\n"
        f"{REPLACE_MARKER}"
    )
    healed, stats = apply_stagewise_patch_verbose(original, patch)

    print(f"\nPatch stats: {stats}")
    print("Healed output:")
    print(healed)

    check(stats["mode"] == "stagewise", "applied as a stagewise hunk, not a full rewrite")
    check(stats["changed_lines"] <= 4,
          f"minimal: {stats['changed_lines']} of {stats['total_lines']} lines changed")
    check(stats["modified_definitions"] == ["authenticate_user"],
          "only the residual's function was modified")
    check(stats["collateral_definitions"] == [], "no collateral damage to passing code")
    check("def unrelated_helper(value):\n    return value.strip().lower()" in healed,
          "the passing helper survived byte-identical")
    check("%s" in healed and "f'SELECT" not in healed, "the vulnerability is actually gone")

    # A bad patch must be refused, not applied.
    bad = f"{SEARCH_MARKER}\n    return cursor.fetchone()\n{DIVIDER_MARKER}\n    return cursor.fetchone(\n{REPLACE_MARKER}"
    reverted, bad_stats = apply_stagewise_patch_verbose(original, bad)
    check(reverted == original and bad_stats["mode"] == "rejected",
          "a syntax-breaking patch is rejected and the original is preserved")


# ----------------------------------------------------------------------
# 3. Sparse L1 gating against the REAL registry
# ----------------------------------------------------------------------

def test_live_sparse_tool_gating():
    section("3. Sparse L1 Tool Context Gating — live registry (ESL Ch. 3 & 18)")

    full_map = build_registry_tool_map()
    print(f"Live registry size: {len(full_map)} tools")
    check(len(full_map) > 20,
          "catalog is built from the live registry (not the stale 20-entry constant)",
          f"got {len(full_map)}")

    queries = [
        "Create a sleek dark-mode navigation bar with glassmorphism CSS",
        "Commit feature branch changes and open a pull request for review",
        "Search the hivemind for prior art on Bayesian routing",
    ]

    for q in queries:
        text, stats = gated_tool_catalog(q, max_active_tools=12)
        print(f"\nTask: \"{q}\"")
        if text is None:
            check(False, "gated catalog produced output", "registry unavailable")
            continue
        print(f"  tools: {stats['active_tools']}/{stats['total_tools']}  "
              f"chars: {stats['full_chars']} -> {stats['gated_chars']} "
              f"({stats['savings_pct']}% saved)")
        check(stats["active_tools"] < stats["total_tools"], "gate actually pruned the catalog")
        check(stats["gated_chars"] < stats["full_chars"],
              "measured character savings are real",
              f"{stats['gated_chars']} vs {stats['full_chars']}")

    # Production wiring: think_about_tools must go through the gate.
    from tools.infrastructure import workspace_tools
    catalog = workspace_tools._catalog_for_task("Fix the CSS grid on the navbar")
    check("L1-gated" in catalog or catalog == workspace_tools.TOOL_CATALOG,
          "think_about_tools routes through _catalog_for_task")
    check("L1-gated" in catalog,
          "the live catalog is gated (not silently falling back to the static one)")


if __name__ == "__main__":
    for fn in (test_live_thompson_sampling, test_live_residual_patching, test_live_sparse_tool_gating):
        try:
            fn()
        except Exception:
            traceback.print_exc()
            FAILURES.append(f"{fn.__name__} raised")

    print("\n" + "=" * 70)
    if FAILURES:
        print(f"❌ {len(FAILURES)} CHECK(S) FAILED:")
        for f in FAILURES:
            print(f"   - {f}")
        print("=" * 70)
        sys.exit(1)
    print("✅ All live integration checks passed.")
    print("=" * 70)
    sys.exit(0)
