"""DSH-06 slice 2 -- Queen task decomposition, health-aware and multi-provider.

    docs/composability-primer.md: a load-bearing capability with exactly one
    provider is static composition in disguise -- when that one provider is
    down, so are you.

The swarm's Queen (``spawn_swarm`` in orchestrator.py) decomposes an objective
into a JSON array of atomic tasks. It used to call ``call_gemini_pro`` directly,
so a Gemini quota exhaustion (429 / RESOURCE_EXHAUSTED) meant *no swarm at all*.

This module points that one call at a :class:`~tools.strategy.resolver.Resolver`
(via the shared :class:`~tools.strategy.capability_resolver.CapabilityResolver`),
carrying up to three reasoning providers tried in order:

    gemini  ->  deepseek  ->  local LLM gateway

Gemini stays first, so the happy path is unchanged. When it fails (or returns
something that is not a usable decomposition), the Resolver demotes it for a
cooldown and the next provider serves. "Kill Gemini -> decomposition still runs."

Data boundary: the objective text is sent to whichever provider serves. The
original design already sent it to Gemini (a third party); the fallbacks widen
that set. An operator who does not want a given provider to ever see the prompt
removes it from ``KENBUN_QUEEN_PROVIDERS`` (or simply leaves its API key /
endpoint unconfigured -- an unconfigured client raises *before* any network I/O,
so nothing leaves the box, and the Resolver just moves on).
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple

from tools.strategy.capability_resolver import (
    CapabilityResolver,
    ResolverExhausted,
    text_unavailable,
)
from tools.strategy.resolver import Resolver

__all__ = ["run_decomposition", "decomposition_resolver", "ResolverExhausted"]

_QUEEN_SYSTEM = (
    "You are the Kenbun Queen, a high-reasoning task decomposer. "
    "Return ONLY a valid JSON array of atomic task objects -- no prose, no markdown fences."
)


# --------------------------------------------------------------------- providers
# Each adapter normalises a differently-shaped client to ``(prompt: str) -> str``.
# Imports are lazy so importing this module (and orchestrator.py) stays cheap and
# a broken client import just demotes that one provider instead of exploding.

def _gemini_provider(prompt: str) -> str:
    from tools.audit.gemini_reviewer import call_gemini_pro

    return call_gemini_pro(prompt)


def _deepseek_provider(prompt: str) -> str:
    from tools.utils.deepseek_client import call_deepseek

    return call_deepseek(system_prompt=_QUEEN_SYSTEM, user_message=prompt)


def _local_provider(prompt: str) -> str:
    from tools.utils.llm_router import call_llm_gateway

    return call_llm_gateway(system_prompt=_QUEEN_SYSTEM, user_message=prompt, max_tokens=4000)


# Lambdas indirect through the module globals so a test can monkeypatch a single
# ``_*_provider`` and the resolver picks it up.
_CAP = CapabilityResolver(
    "queen_decomposition",
    {
        "gemini": lambda p: _gemini_provider(p),
        "deepseek": lambda p: _deepseek_provider(p),
        "local": lambda p: _local_provider(p),
    },
    providers_env="KENBUN_QUEEN_PROVIDERS",
    cooldown_env="KENBUN_QUEEN_COOLDOWN_S",
)


def decomposition_resolver() -> Resolver:
    """The process-wide decomposition Resolver (lazily built; order from the
    KENBUN_QUEEN_PROVIDERS env var, or the default gemini -> deepseek -> local)."""
    return _CAP.resolver()


def run_decomposition(
    queen_prompt: str,
    *,
    is_usable: Optional[Callable[[str], bool]] = None,
    resolver: Optional[Resolver] = None,
) -> Tuple[str, str]:
    """Ask the reasoning providers, in order, to decompose ``queen_prompt``.

    Returns ``(provider_name, raw_text)``. A provider that raises, returns empty
    / error-prefixed text, or fails the optional ``is_usable`` check is demoted
    and the next one is tried. Raises :class:`ResolverExhausted` only if every
    provider is unavailable.

    ``is_usable`` lets the caller reject text that came back cleanly but is not a
    usable decomposition (e.g. "no JSON array in it") without this module having
    to import the caller's parser.
    """
    def _unavailable(out: object) -> bool:
        if text_unavailable(out):
            return True
        return is_usable is not None and not is_usable(out)  # type: ignore[arg-type]

    return _CAP.run(
        lambda provider: provider(queen_prompt),
        is_unavailable=_unavailable,
        resolver=resolver,
    )
