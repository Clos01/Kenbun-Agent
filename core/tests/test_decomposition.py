"""DSH-06 slice 2 -- the swarm Queen's decomposition survives a provider outage.

The core promise: kill Gemini (429 / quota) and ``spawn_swarm`` still gets a
task decomposition -- from DeepSeek, then the local gateway.
"""
import pytest

from tools.strategy import decomposition
from tools.strategy.decomposition import ResolverExhausted, run_decomposition
from tools.strategy.resolver import Resolver

_JSON = '[{"id": "t0", "label": "do it", "worker_type": "coder", "task_description": "..."}]'


def _resolver(*providers):
    """Build a throwaway Resolver from (name, callable) pairs."""
    r = Resolver(cooldown_s=100)
    for name, fn in providers:
        r.add(name, fn)
    return r


# --------------------------------------------------------------- happy path
def test_gemini_serves_when_healthy():
    r = _resolver(
        ("gemini", lambda p: _JSON),
        ("deepseek", lambda p: pytest.fail("deepseek should not be reached")),
    )
    name, raw = run_decomposition("decompose X", resolver=r)
    assert name == "gemini"
    assert raw == _JSON


def test_queen_prompt_is_passed_through_to_the_provider():
    seen = {}

    def gem(prompt):
        seen["prompt"] = prompt
        return _JSON

    run_decomposition("OBJECTIVE: ship the thing", resolver=_resolver(("gemini", gem)))
    assert seen["prompt"] == "OBJECTIVE: ship the thing"


# --------------------------------------------------------------- failover
def test_gemini_429_falls_through_to_deepseek():
    def gem(p):
        raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")

    r = _resolver(("gemini", gem), ("deepseek", lambda p: _JSON))
    name, raw = run_decomposition("decompose X", resolver=r)
    assert name == "deepseek"
    assert raw == _JSON
    assert not r.is_healthy("gemini")          # demoted for next time


def test_falls_all_the_way_to_the_local_gateway():
    r = _resolver(
        ("gemini", lambda p: (_ for _ in ()).throw(RuntimeError("boom"))),
        ("deepseek", lambda p: (_ for _ in ()).throw(ConnectionError("no route"))),
        ("local", lambda p: _JSON),
    )
    name, raw = run_decomposition("decompose X", resolver=r)
    assert name == "local"
    assert raw == _JSON


def test_every_provider_down_raises_resolver_exhausted():
    r = _resolver(
        ("gemini", lambda p: (_ for _ in ()).throw(RuntimeError("a"))),
        ("deepseek", lambda p: (_ for _ in ()).throw(RuntimeError("b"))),
    )
    with pytest.raises(ResolverExhausted):
        run_decomposition("decompose X", resolver=r)


# ------------------------------------------------- "returned text, but useless"
def test_clean_but_unusable_output_falls_through_via_is_usable():
    """Gemini answers without erroring, but the answer has no JSON array in it."""
    r = _resolver(
        ("gemini", lambda p: "Sure! Here is how I would think about that..."),
        ("deepseek", lambda p: _JSON),
    )
    name, raw = run_decomposition(
        "decompose X", resolver=r, is_usable=lambda t: t.strip().startswith("["),
    )
    assert name == "deepseek"
    assert not r.is_healthy("gemini")


def test_error_prefixed_string_is_treated_as_an_outage():
    r = _resolver(
        ("gemini", lambda p: "❌ Gemini Error: RESOURCE_EXHAUSTED"),
        ("deepseek", lambda p: _JSON),
    )
    name, _ = run_decomposition("decompose X", resolver=r)
    assert name == "deepseek"


def test_empty_output_is_treated_as_an_outage():
    r = _resolver(
        ("gemini", lambda p: "   "),
        ("deepseek", lambda p: _JSON),
    )
    name, _ = run_decomposition("decompose X", resolver=r)
    assert name == "deepseek"


def test_all_providers_unusable_returns_last_result_not_an_exception():
    """So the caller can surface the raw text in a 'no JSON array' message,
    exactly as it did before DSH-06."""
    r = _resolver(
        ("gemini", lambda p: "prose one"),
        ("deepseek", lambda p: "prose two"),
    )
    name, raw = run_decomposition(
        "decompose X", resolver=r, is_usable=lambda t: False,
    )
    assert (name, raw) == ("deepseek", "prose two")


# ------------------------------------------------- module-level singleton wiring
def test_module_resolver_is_a_lazy_singleton():
    decomposition._CAP.reset()
    try:
        first = decomposition.decomposition_resolver()
        assert decomposition.decomposition_resolver() is first
        assert first.names() == ["gemini", "deepseek", "local"]
    finally:
        decomposition._CAP.reset()


def test_provider_allowlist_env_narrows_and_orders_the_resolver(monkeypatch):
    monkeypatch.setenv("KENBUN_QUEEN_PROVIDERS", "local, gemini")
    decomposition._CAP.reset()
    try:
        assert decomposition.decomposition_resolver().names() == ["local", "gemini"]
    finally:
        decomposition._CAP.reset()


def test_provider_allowlist_env_with_no_known_names_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("KENBUN_QUEEN_PROVIDERS", "bogus,   ,nonsense")
    decomposition._CAP.reset()
    try:
        assert decomposition.decomposition_resolver().names() == ["gemini", "deepseek", "local"]
    finally:
        decomposition._CAP.reset()


def test_cooldown_env_is_honoured(monkeypatch):
    monkeypatch.setenv("KENBUN_QUEEN_COOLDOWN_S", "42")
    decomposition._CAP.reset()
    try:
        assert decomposition.decomposition_resolver()._cooldown_s == 42.0
    finally:
        decomposition._CAP.reset()


def test_racing_spawns_share_one_resolver_instance():
    """The double-checked lock means concurrent first-touches don't each build
    their own resolver (which would split the provider-health view)."""
    import threading

    decomposition._CAP.reset()
    try:
        seen = []
        barrier = threading.Barrier(12)

        def grab():
            barrier.wait()
            seen.append(decomposition.decomposition_resolver())

        threads = [threading.Thread(target=grab) for _ in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(seen) == 12
        assert all(r is seen[0] for r in seen)
    finally:
        decomposition._CAP.reset()


def test_run_decomposition_uses_the_singleton_and_its_providers(monkeypatch):
    """End-to-end through the real singleton: patch the provider functions,
    kill gemini, prove deepseek serves."""
    decomposition._CAP.reset()
    try:
        monkeypatch.setattr(decomposition, "_gemini_provider",
                            lambda p: (_ for _ in ()).throw(RuntimeError("429")))
        monkeypatch.setattr(decomposition, "_deepseek_provider", lambda p: _JSON)
        monkeypatch.setattr(decomposition, "_local_provider",
                            lambda p: pytest.fail("local should not be reached"))
        name, raw = run_decomposition("decompose X")
        assert name == "deepseek"
        assert raw == _JSON
    finally:
        decomposition._CAP.reset()


# ------------------------------------------------- failover telemetry
def test_a_failover_records_a_cross_process_event(tmp_path, monkeypatch):
    from tools.infrastructure.config import settings
    from tools.strategy import resolver_events

    monkeypatch.setattr(settings, "BRAIN_HEALTH_DIR", tmp_path)

    r = _resolver(
        ("gemini", lambda p: (_ for _ in ()).throw(RuntimeError("429"))),
        ("deepseek", lambda p: _JSON),
    )
    run_decomposition("decompose X", resolver=r)

    events = resolver_events.recent(10)
    assert len(events) == 1
    assert events[0]["kind"] == "failover"
    assert events[0]["provider"] == "deepseek"
    assert events[0]["capability"] == "queen_decomposition"
    assert events[0]["providers_order"] == ["gemini", "deepseek"]


def test_concurrent_records_never_corrupt_or_lose_a_line(tmp_path, monkeypatch):
    """The flock + threading.Lock guard means N racing recorders each land a
    complete, parseable line (up to the _MAX_LINES cap)."""
    import json as _json
    import threading

    from tools.infrastructure.config import settings
    from tools.strategy import resolver_events

    monkeypatch.setattr(settings, "BRAIN_HEALTH_DIR", tmp_path)

    per_thread = 40
    threads_n = 8
    total = per_thread * threads_n                           # 320 > _MAX_LINES (200)

    def worker(n: int) -> None:
        for i in range(per_thread):
            resolver_events.record("failover", capability="cap",
                                   provider=f"p{n}", detail=f"{n}-{i}")

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(threads_n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    raw = (tmp_path / "resolver_events.jsonl").read_text().splitlines()
    lines = [ln for ln in raw if ln.strip()]
    assert total > resolver_events._MAX_LINES
    assert len(lines) == resolver_events._MAX_LINES          # capped exactly, no over/undercount
    seen = set()
    for ln in lines:
        obj = _json.loads(ln)                                # every surviving line is intact JSON
        seen.add(obj["detail"])
    assert len(seen) == resolver_events._MAX_LINES           # no dupes -> no torn/duplicated writes


def test_total_exhaustion_records_an_event(tmp_path, monkeypatch):
    from tools.infrastructure.config import settings
    from tools.strategy import resolver_events

    monkeypatch.setattr(settings, "BRAIN_HEALTH_DIR", tmp_path)

    r = _resolver(
        ("gemini", lambda p: (_ for _ in ()).throw(RuntimeError("a"))),
        ("deepseek", lambda p: (_ for _ in ()).throw(RuntimeError("b"))),
    )
    with pytest.raises(ResolverExhausted):
        run_decomposition("decompose X", resolver=r)

    kinds = [e["kind"] for e in resolver_events.recent(10)]
    assert "exhausted" in kinds


# ------------------------------------------------- orchestrator is actually wired
def test_orchestrator_spawn_swarm_no_longer_calls_gemini_directly():
    import inspect

    from tools.infrastructure import orchestrator

    src = inspect.getsource(orchestrator.spawn_swarm)
    assert "run_decomposition" in src
    assert "call_gemini_pro(queen_prompt)" not in src
