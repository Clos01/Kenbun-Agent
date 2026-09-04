import math
import random
import pytest
from tools.utils.bayesian import (
    BayesianDistribution,
    pure_update_posterior,
    pure_expected_confidence,
    pure_thompson_sample,
    calculate_thompson_sample,
    rank_tools_thompson,
    sample_tool_thompson,
)


def test_bayesian_distribution_immutability():
    dist = BayesianDistribution(alpha=2.0, beta=3.0, success_count=1, failure_count=2)
    assert dist.alpha == 2.0
    assert dist.beta == 3.0
    assert dist.success_count == 1
    assert dist.failure_count == 2
    with pytest.raises(AttributeError):
        dist.alpha = 5.0  # NamedTuple is immutable


def test_pure_update_posterior_success_and_failure():
    prior = BayesianDistribution(alpha=1.0, beta=1.0, success_count=0, failure_count=0)

    # Success update
    post1 = pure_update_posterior(prior, success=True, weight=1.0)
    assert post1.alpha == 2.0
    assert post1.beta == 1.0
    assert post1.success_count == 1
    assert post1.failure_count == 0

    # Prior remains unchanged (pure function)
    assert prior.alpha == 1.0
    assert prior.beta == 1.0

    # Failure update
    post2 = pure_update_posterior(post1, success=False, weight=1.0)
    assert post2.alpha == 2.0
    assert post2.beta == 2.0
    assert post2.success_count == 1
    assert post2.failure_count == 1


def test_pure_update_posterior_ieee754_domain_validation():
    prior = BayesianDistribution(alpha=1.0, beta=1.0)

    # NaN weight
    with pytest.raises(ValueError, match="Weight must be a finite"):
        pure_update_posterior(prior, success=True, weight=float("nan"))

    # Inf weight
    with pytest.raises(ValueError, match="Weight must be a finite"):
        pure_update_posterior(prior, success=True, weight=float("inf"))

    # Negative weight
    with pytest.raises(ValueError, match="Weight must be a finite"):
        pure_update_posterior(prior, success=True, weight=-1.0)

    # Invalid prior with NaN
    nan_dist = BayesianDistribution(alpha=float("nan"), beta=1.0)
    with pytest.raises(ValueError, match="Alpha and beta parameters must be finite"):
        pure_update_posterior(nan_dist, success=True)


def test_pure_expected_confidence():
    # Symmetric prior Beta(1, 1) -> 0.5
    dist = BayesianDistribution(alpha=1.0, beta=1.0)
    assert pure_expected_confidence(dist) == 0.5

    # 3 successes, 1 failure -> 3/4 = 0.75
    dist2 = BayesianDistribution(alpha=3.0, beta=1.0)
    assert pure_expected_confidence(dist2) == 0.75

    # Degenerate / invalid edge cases safely return 0.5
    assert pure_expected_confidence(BayesianDistribution(alpha=float("nan"), beta=1.0)) == 0.5
    assert pure_expected_confidence(BayesianDistribution(alpha=0.0, beta=0.0)) == 0.5


def test_calculate_thompson_sample_deterministic_with_seed():
    rng = random.Random(42)
    sample1 = calculate_thompson_sample(alpha=5.0, beta=2.0, temperature=1.0, random_generator=rng)
    rng = random.Random(42)
    sample2 = calculate_thompson_sample(alpha=5.0, beta=2.0, temperature=1.0, random_generator=rng)
    assert sample1 == sample2
    assert 0.0 <= sample1 <= 1.0


def test_rank_tools_thompson_ordering():
    tools = ["tool_a", "tool_b", "tool_c"]
    ranked = rank_tools_thompson(
        category="global",
        candidate_tools=tools,
        exploration_mode=False,
        posteriors={"tool_a": (10.0, 1.0), "tool_b": (1.0, 10.0), "tool_c": (5.0, 5.0)},
    )
    assert len(ranked) == 3
    # Exploitation mode sorts strictly by expected value
    assert ranked[0][0] == "tool_a"
    assert ranked[1][0] == "tool_c"
    assert ranked[2][0] == "tool_b"
