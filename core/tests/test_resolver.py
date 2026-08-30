"""DSH-06 slice 1 -- Resolver: health-aware provider selection, no single point of failure."""
import time

import pytest

from tools.strategy.resolver import Resolver, ResolverExhausted


def test_pick_returns_first_provider_in_insertion_order():
    r = Resolver()
    r.add("a", "PA"); r.add("b", "PB")
    assert r.pick() == ("a", "PA")
    assert r.names() == ["a", "b"]


def test_add_returns_a_working_remove_disposer():
    r = Resolver()
    remove_a = r.add("a", 1); r.add("b", 2)
    remove_a()
    assert r.names() == ["b"]
    assert r.pick() == ("b", 2)


def test_re_adding_a_name_replaces_and_moves_to_end():
    r = Resolver()
    r.add("a", 1); r.add("b", 2); r.add("a", 99)
    assert r.names() == ["b", "a"]


# --------------------------------------------------------------------- health
def test_demoted_provider_is_skipped_then_auto_recovers():
    r = Resolver(cooldown_s=0.3)
    r.add("a", "PA"); r.add("b", "PB")

    r.mark_unhealthy("a")
    assert r.pick() == ("b", "PB")           # a skipped
    assert not r.is_healthy("a")

    time.sleep(0.35)
    assert r.is_healthy("a")
    assert r.pick() == ("a", "PA")           # recovered, back to front


def test_all_demoted_still_yields_candidates_as_last_resort():
    r = Resolver(cooldown_s=100)
    r.add("a", "PA"); r.add("b", "PB")
    r.mark_unhealthy("a"); r.mark_unhealthy("b")
    # not empty -- a dead-end is worse than trying a demoted provider
    assert [n for n, _ in r.candidates()] == ["a", "b"]
    assert r.pick() == ("a", "PA")


def test_mark_healthy_undoes_a_demotion():
    r = Resolver(cooldown_s=100)
    r.add("a", 1)
    r.mark_unhealthy("a")
    assert not r.is_healthy("a")
    r.mark_healthy("a")
    assert r.is_healthy("a")


# ----------------------------------------------------------------------- run
def test_run_returns_the_first_provider_that_serves():
    r = Resolver()
    r.add("primary", "P"); r.add("backup", "B")
    name, out = r.run(lambda p: f"handled by {p}")
    assert name == "primary" and out == "handled by P"


def test_run_falls_through_an_unavailable_result_and_demotes_it():
    r = Resolver(cooldown_s=100)
    r.add("gemini", "G"); r.add("deepseek", "D")

    def call(p):
        return "429 RESOURCE_EXHAUSTED" if p == "G" else "ok from deepseek"

    name, out = r.run(call, is_unavailable=lambda res: "429" in res)
    assert name == "deepseek" and out == "ok from deepseek"
    assert not r.is_healthy("gemini")        # demoted for next time


def test_run_falls_through_a_raising_provider():
    r = Resolver(cooldown_s=100)
    r.add("flaky", "F"); r.add("solid", "S")

    def call(p):
        if p == "F":
            raise ConnectionError("boom")
        return "solid result"

    name, out = r.run(call)
    assert name == "solid" and out == "solid result"
    assert not r.is_healthy("flaky")


def test_run_raises_ResolverExhausted_when_every_provider_raises():
    r = Resolver()
    r.add("a", 1); r.add("b", 2)
    with pytest.raises(ResolverExhausted):
        r.run(lambda p: (_ for _ in ()).throw(RuntimeError("nope")))


def test_run_returns_last_unavailable_result_when_all_are_unavailable():
    r = Resolver()
    r.add("a", 1); r.add("b", 2)
    name, out = r.run(lambda p: f"down-{p}", is_unavailable=lambda res: True)
    assert (name, out) == ("b", "down-2")


def test_run_raises_when_no_providers_registered():
    with pytest.raises(ResolverExhausted):
        Resolver().run(lambda p: p)
