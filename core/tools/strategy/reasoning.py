"""DSH-06 slice 4 -- general high-reasoning text generation, health-aware.

Several callers reach for ``call_gemini_pro`` directly for a one-shot reasoning
task -- Kanban subtask decomposition, self-improvement prompt rewrites, agent
output scoring, git-push integration design. Each was its own Gemini SPOF: a
429 / quota exhaustion killed that feature with no fallback.

This is the shared fallback for all of them -- a
:class:`~tools.strategy.capability_resolver.CapabilityResolver`.

Data boundary: these callers carry a mix of payloads -- an agent's own system
prompt (self_improvement_daemon), scored agent output (agent_evaluator), commit
content and repo layout (git_watcher_tools), internal task context
(kanban_dispatcher). Some of that is sensitive, so the **default fallback is
operator-configured endpoints only**:

    gemini  ->  local (settings.PRIMARY_LLM_URL / FALLBACK_LLM_URL)

DeepSeek (third party) is opt-in for the whole reasoning path:
``KENBUN_REASONING_PROVIDERS=gemini,deepseek,local``.
``KENBUN_REASONING_COOLDOWN_S`` tunes the demotion window. Every failover is
logged and recorded to the ``resolver_events`` trail (capability "reasoning"),
so the Observatory panel shows when a fallback fired.
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple

from tools.strategy.capability_resolver import (
    CapabilityResolver,
    ResolverExhausted,
    text_unavailable,
)
from tools.strategy.resolver import Resolver

__all__ = ["run_reasoning", "reason", "reasoning_resolver", "ResolverExhausted"]

_SYSTEM = (
    "You are a high-reasoning AI agent. Process the following request with precision "
    "and return only what was asked for."
)


def _gemini_provider(prompt: str) -> str:
    from tools.audit.gemini_reviewer import call_gemini_pro

    return call_gemini_pro(prompt)


def _deepseek_provider(prompt: str) -> str:
    from tools.utils.deepseek_client import call_deepseek

    return call_deepseek(system_prompt=_SYSTEM, user_message=prompt)


def _local_provider(prompt: str) -> str:
    from tools.utils.llm_router import call_llm_gateway

    return call_llm_gateway(system_prompt=_SYSTEM, user_message=prompt, max_tokens=4000)


_CAP = CapabilityResolver(
    "reasoning",
    {
        "gemini": lambda p: _gemini_provider(p),
        "deepseek": lambda p: _deepseek_provider(p),
        "local": lambda p: _local_provider(p),
    },
    providers_env="KENBUN_REASONING_PROVIDERS",
    cooldown_env="KENBUN_REASONING_COOLDOWN_S",
    default_order=("gemini", "local"),   # deepseek (3rd party) is opt-in
)


def reasoning_resolver() -> Resolver:
    """The process-wide reasoning Resolver. Default order is ``gemini -> local``
    (operator-configured endpoints only); DeepSeek is opt-in via
    ``KENBUN_REASONING_PROVIDERS=gemini,deepseek,local``."""
    return _CAP.resolver()


def run_reasoning(
    prompt: str,
    *,
    is_usable: Optional[Callable[[str], bool]] = None,
    resolver: Optional[Resolver] = None,
) -> Tuple[str, str]:
    """Send ``prompt`` to the reasoning providers in order; return ``(provider, text)``.

    A provider that raises, returns empty / error-prefixed text, or fails the
    optional ``is_usable`` check is demoted and the next is tried. Raises
    :class:`ResolverExhausted` only if every provider is unavailable -- callers
    that previously let ``call_gemini_pro`` raise get the same failure mode.
    """
    def _unavailable(out: object) -> bool:
        if text_unavailable(out):
            return True
        return is_usable is not None and not is_usable(out)  # type: ignore[arg-type]

    return _CAP.run(lambda provider: provider(prompt), is_unavailable=_unavailable, resolver=resolver)


def reason(prompt: str, *, is_usable: Optional[Callable[[str], bool]] = None) -> str:
    """Drop-in for ``call_gemini_pro``: returns the text, raises
    :class:`ResolverExhausted` (a ``RuntimeError``) only if every provider is down."""
    return run_reasoning(prompt, is_usable=is_usable)[1]
