"""DSH-06 slice 4 -- the shared reasoning fallback for the ex-call_gemini_pro callers."""
import pytest

from tools.strategy import reasoning
from tools.strategy.reasoning import ResolverExhausted, reason, run_reasoning
from tools.strategy.resolver import Resolver

_TXT = "here is the answer"


def _resolver(*providers):
    r = Resolver(cooldown_s=100)
    for name, fn in providers:
        r.add(name, fn)
    return r


def test_gemini_serves_when_healthy():
    r = _resolver(("gemini", lambda p: _TXT),
                  ("deepseek", lambda p: pytest.fail("not reached")))
    assert run_reasoning("do it", resolver=r) == ("gemini", _TXT)


def test_gemini_429_falls_through():
    r = _resolver(
        ("gemini", lambda p: (_ for _ in ()).throw(RuntimeError("429 RESOURCE_EXHAUSTED"))),
        ("deepseek", lambda p: _TXT),
    )
    name, txt = run_reasoning("do it", resolver=r)
    assert name == "deepseek" and txt == _TXT


def test_run_reasoning_raises_resolver_exhausted_when_all_down():
    r = _resolver(
        ("gemini", lambda p: (_ for _ in ()).throw(RuntimeError("x"))),
        ("deepseek", lambda p: (_ for _ in ()).throw(RuntimeError("y"))),
    )
    with pytest.raises(ResolverExhausted):
        run_reasoning("do it", resolver=r)


def test_is_usable_rejects_clean_but_wrong_output():
    r = _resolver(("gemini", lambda p: "prose, no json"),
                  ("deepseek", lambda p: '["ok"]'))
    name, txt = run_reasoning("do it", resolver=r, is_usable=lambda t: t.strip().startswith("["))
    assert name == "deepseek"


def test_default_order_excludes_deepseek_and_is_a_singleton(monkeypatch):
    monkeypatch.delenv("KENBUN_REASONING_PROVIDERS", raising=False)
    reasoning._CAP.reset()
    try:
        assert reasoning.reasoning_resolver().names() == ["gemini", "local"]
        assert reasoning.reasoning_resolver() is reasoning.reasoning_resolver()
    finally:
        reasoning._CAP.reset()


def test_deepseek_is_opt_in(monkeypatch):
    monkeypatch.setenv("KENBUN_REASONING_PROVIDERS", "gemini,deepseek,local")
    reasoning._CAP.reset()
    try:
        assert reasoning.reasoning_resolver().names() == ["gemini", "deepseek", "local"]
    finally:
        reasoning._CAP.reset()


def test_singleton_reason_uses_the_patched_providers(monkeypatch):
    monkeypatch.delenv("KENBUN_REASONING_PROVIDERS", raising=False)
    reasoning._CAP.reset()
    monkeypatch.setattr(reasoning, "_gemini_provider",
                        lambda p: (_ for _ in ()).throw(RuntimeError("429")))
    monkeypatch.setattr(reasoning, "_local_provider", lambda p: _TXT)
    try:
        assert reason("hello") == _TXT          # gemini down -> local (default fallback) serves
    finally:
        reasoning._CAP.reset()


# --------------------------------------------- the call sites are actually migrated
@pytest.mark.parametrize("module_path,needle", [
    ("tools.strategy.agent_evaluator", "reason("),
    ("tools.infrastructure.git_watcher_tools", "reason("),
])
def test_ex_gemini_callers_now_call_reason(module_path, needle):
    import importlib
    import inspect
    mod = importlib.import_module(module_path)
    src = inspect.getsource(mod)
    assert "call_gemini_pro" not in src
    assert needle in src
