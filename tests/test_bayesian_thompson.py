"""
Test Suite: Bayesian Thompson Sampling Engine (ESL Ch. 8 & 16)
==============================================================
Validates Bayesian posterior sampling, exploration-exploitation trade-offs,
deterministic greedy fallback, and that the sampler is actually reached by the
production routing path (DecisionRouter.recommend_tools).
"""

import importlib

import pytest
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


@pytest.fixture
def stub_posteriors():
    """Force every posterior read through the stub, whichever path is taken."""
    def per_tool(tool_id, category="global"):
        return PARAMS.get(tool_id, (1.0, 1.0))

    with patch(f"{MODULE_PATH}.get_posterior_params", side_effect=per_tool), \
         patch(f"{MODULE_PATH}.get_posterior_params_batch", return_value={}):
        yield


# ------------------------------------------------------------------
# posterior retrieval
# ------------------------------------------------------------------

def test_get_posterior_params_default():
    """Unknown tools default to the Beta(1,1) uniform prior."""
    with patch(f"{MODULE_PATH}.get_connection") as mock_conn:
        mock_conn.side_effect = Exception("DB offline")
        alpha, beta = get_posterior_params("unknown_tool_xyz")
        assert alpha == 1.0
        assert beta == 1.0


def test_batch_fetch_returns_empty_on_db_failure():
    """A telemetry outage must degrade to the prior, never raise into routing."""
    with patch(f"{MODULE_PATH}.get_connection") as mock_conn:
        mock_conn.side_effect = Exception("DB offline")
        assert get_posterior_params_batch(["a", "b"]) == {}


def test_batch_fetch_short_circuits_on_empty_input():
    assert get_posterior_params_batch([]) == {}


# ------------------------------------------------------------------
# sampling behaviour
# ------------------------------------------------------------------

def test_sample_tool_thompson_single_candidate(stub_posteriors):
    """A single candidate reports its posterior mean, not a noisy draw."""
    tool, score = sample_tool_thompson("security", ["tool_veteran"])
    assert tool == "tool_veteran"
    assert score == pytest.approx(50.0 / 55.0)


def test_sample_tool_thompson_empty_raises():
    with pytest.raises(ValueError):
        sample_tool_thompson("security", [])


def test_rank_tools_thompson_empty_raises():
    with pytest.raises(ValueError):
        rank_tools_thompson("security", [])


def test_rank_returns_every_candidate_once(stub_posteriors):
    ranked = rank_tools_thompson("general", ["tool_veteran", "tool_uncertain", "tool_veteran"])
    ids = [tid for tid, _ in ranked]
    assert sorted(ids) == ["tool_uncertain", "tool_veteran"]


def test_rank_is_sorted_descending(stub_posteriors):
    ranked = rank_tools_thompson("general", list(PARAMS), exploration_mode=False)
    scores = [s for _, s in ranked]
    assert scores == sorted(scores, reverse=True)
    assert ranked[0][0] == "tool_veteran"


def test_thompson_exploration_vs_exploitation_distribution(stub_posteriors):
    """
    1,000 trials across a veteran, an unobserved tool, and a failing tool.
    The veteran should dominate, the unobserved tool must still get explored
    (this is the tool-starvation fix), and the failing tool must stay rare.
    """
    counts = {k: 0 for k in PARAMS}
    trials = 1000
    for _ in range(trials):
        chosen, _ = sample_tool_thompson("general", list(PARAMS))
        counts[chosen] += 1

    assert counts["tool_veteran"] >= 800, counts
    assert counts["tool_uncertain"] >= 10, counts
    assert counts["tool_failing"] <= 20, counts


def test_temperature_increases_exploration(stub_posteriors):
    """Higher T flattens the posteriors, so the veteran wins less often."""
    def veteran_share(temp):
        wins = 0
        for _ in range(600):
            chosen, _ = sample_tool_thompson("general", list(PARAMS), temperature=temp)
            if chosen == "tool_veteran":
                wins += 1
        return wins / 600

    assert veteran_share(20.0) < veteran_share(1.0)


def test_get_best_tool_deterministic_greedy_mode():
    conf_map = {"tool_a": 0.85, "tool_b": 0.92, "tool_c": 0.40}
    with patch(f"{MODULE_PATH}.get_confidence", side_effect=lambda tid, cat: conf_map[tid]):
        best_tool, score = get_best_tool("general", ["tool_a", "tool_b", "tool_c"], exploration_mode=False)
        assert best_tool == "tool_b"
        assert score == 0.92


# ------------------------------------------------------------------
# WIRING — the sampler must be reached by production routing
# ------------------------------------------------------------------

def test_recommend_tools_ranks_via_thompson():
    """Regression guard for the original defect: the sampler existed, passed its
    tests, and no production code path called it."""
    decision_logic = importlib.import_module(ROUTER_PATH)

    called = {}

    def fake_rank(category, candidates, exploration_mode=True, temperature=1.0):
        called["category"] = category
        called["candidates"] = list(candidates)
        return [(tid, 0.5) for tid in reversed(candidates)]

    with patch(f"{MODULE_PATH}.rank_tools_thompson", side_effect=fake_rank):
        ordered = decision_logic.router.recommend_tools("fix the SQL injection in the auth handler")

    assert called, "recommend_tools did not consult the Thompson sampler"
    # Ordering came from the sampler, not from the hardcoded list.
    assert ordered == list(reversed(called["candidates"]))


def test_recommend_tools_falls_back_when_sampler_unavailable():
    """A telemetry failure must not break routing."""
    decision_logic = importlib.import_module(ROUTER_PATH)

    with patch(f"{MODULE_PATH}.rank_tools_thompson", side_effect=RuntimeError("intelligence store down")):
        ordered = decision_logic.router.recommend_tools("fix the SQL injection in the auth handler")

    assert ordered, "fallback must still return candidate tools"
    assert all(isinstance(t, str) for t in ordered)


def test_governor_sample_strategy_delegates_to_canonical_sampler():
    """The duplicate betavariate loop in strategy_manager must be gone."""
    try:
        from tools.strategy.strategy_manager import governor
    except ImportError:
        from core.tools.strategy.strategy_manager import governor

    with patch(f"{MODULE_PATH}.rank_tools_thompson", return_value=[("tool_b", 0.9), ("tool_a", 0.1)]):
        tool, score = governor.sample_strategy(["tool_a", "tool_b"])

    assert tool == "tool_b"
    assert score == 0.9
