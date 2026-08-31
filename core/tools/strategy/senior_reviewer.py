"""DSH-06 slice 3 -- the supervisor's "local senior reviewer", health-aware.

    docs/composability-primer.md: a load-bearing capability with exactly one
    provider is static composition in disguise -- when that one provider is
    down, so are you.

``consult_supervisor`` (the commit gate) leans on ``_call_local_senior`` in
core/tools/audit/supervisor_agent.py, which *always* pointed at one LM Studio
box (``SWARM_PC_IP:lm_studio_port``). If that machine is off, the supervisor
degrades on every call.

This module points that one call at a :class:`~tools.strategy.resolver.Resolver`
(via the shared :class:`~tools.strategy.capability_resolver.CapabilityResolver`).
The default order is **operator-configured endpoints only**:

    lmstudio  ->  gateway (settings.PRIMARY_LLM_URL / FALLBACK_LLM_URL)

so a fallback for this data-sensitive commit gate never surprises an operator
with a third party. DeepSeek is available but opt-in:
``KENBUN_SENIOR_PROVIDERS=lmstudio,deepseek,gateway``.

LM Studio stays first, so the happy path is byte-for-byte unchanged. When it
fails (or returns empty / error text), the Resolver demotes it for a cooldown
and the next provider serves. "Kill the LM Studio box -> the supervisor still
returns a verdict."

Data boundary: the code under review is sent to whichever provider serves -- see
the module note above; an unconfigured client raises before any network I/O.
"""
from __future__ import annotations

from typing import Optional, Tuple

from tools.strategy.capability_resolver import (
    CapabilityResolver,
    ResolverExhausted,
    text_unavailable,
)
from tools.strategy.resolver import Resolver

__all__ = ["run_senior_review", "senior_reviewer_resolver", "ResolverExhausted"]


# --------------------------------------------------------------------- providers
# Each adapter normalises a client to ``(system_prompt, user_message, max_tokens) -> str``.
# Imports are lazy so a broken client import just demotes that one provider.

def _lmstudio_provider(system_prompt: str, user_message: str, max_tokens: int) -> str:
    from tools.infrastructure.config import settings
    from tools.utils.llm_router import call_llm_gateway

    # All config-driven: SWARM_PC_IP, lm_studio_port and lm_studio_model each
    # carry a default in config.py -- no in-code host/model literal here.
    lm_url = f"http://{settings.SWARM_PC_IP}:{settings.models.lm_studio_port}/v1"
    return call_llm_gateway(
        system_prompt, user_message, max_tokens=max_tokens,
        url_override=lm_url, model_override=settings.models.lm_studio_model,
    )


def _deepseek_provider(system_prompt: str, user_message: str, max_tokens: int) -> str:
    from tools.utils.deepseek_client import call_deepseek

    return call_deepseek(system_prompt=system_prompt, user_message=user_message)


def _gateway_provider(system_prompt: str, user_message: str, max_tokens: int) -> str:
    # No url/model override: uses settings.PRIMARY_LLM_URL then FALLBACK_LLM_URL,
    # a different path than the pinned LM Studio endpoint above.
    from tools.utils.llm_router import call_llm_gateway

    return call_llm_gateway(system_prompt, user_message, max_tokens=max_tokens)


_CAP = CapabilityResolver(
    "senior_reviewer",
    {
        "lmstudio": lambda sp, um, mt: _lmstudio_provider(sp, um, mt),
        "deepseek": lambda sp, um, mt: _deepseek_provider(sp, um, mt),
        "gateway": lambda sp, um, mt: _gateway_provider(sp, um, mt),
    },
    providers_env="KENBUN_SENIOR_PROVIDERS",
    cooldown_env="KENBUN_SENIOR_COOLDOWN_S",
    default_order=("lmstudio", "gateway"),   # deepseek is opt-in for the commit gate
)


def senior_reviewer_resolver() -> Resolver:
    """The process-wide senior-reviewer Resolver (lazily built; order from
    KENBUN_SENIOR_PROVIDERS or the default lmstudio -> gateway)."""
    return _CAP.resolver()


def run_senior_review(
    system_prompt: str,
    user_message: str,
    *,
    max_tokens: int = 3000,
    resolver: Optional[Resolver] = None,
) -> Tuple[str, str]:
    """Ask the reasoning providers, in order, for a senior-reviewer response.

    Returns ``(provider_name, content)``. A provider that raises or returns
    empty / error-prefixed text is demoted and the next is tried. Raises
    :class:`ResolverExhausted` only if every provider is unavailable.
    """
    return _CAP.run(
        lambda provider: provider(system_prompt, user_message, max_tokens),
        is_unavailable=text_unavailable,
        resolver=resolver,
    )
