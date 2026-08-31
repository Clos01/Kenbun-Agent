"""DSH-06 slice 3 -- the supervisor's "local senior reviewer", health-aware.

    docs/composability-primer.md: a load-bearing capability with exactly one
    provider is static composition in disguise -- when that one provider is
    down, so are you.

``consult_supervisor`` (the commit gate) leans on ``_call_local_senior`` in
core/tools/audit/supervisor_agent.py, which *always* pointed at one LM Studio
box (``SWARM_PC_IP:lm_studio_port``). If that machine is off, the supervisor
degrades on every call.

This module points that one call at a :class:`~tools.strategy.resolver.Resolver`.
The default order is **operator-configured endpoints only**:

    lmstudio  ->  gateway (settings.PRIMARY_LLM_URL / FALLBACK_LLM_URL)

so a fallback for this data-sensitive commit gate never surprises an operator
with a third party. DeepSeek is available but opt-in:
``KENBUN_SENIOR_PROVIDERS=lmstudio,deepseek,gateway``.

LM Studio stays first, so the happy path is byte-for-byte unchanged. When it
fails (or returns empty / error text), the Resolver demotes it for a cooldown
and the next provider serves. "Kill the LM Studio box -> the supervisor still
returns a verdict."

Data boundary: the code under review is sent to whichever provider serves. The
original design already sent it to a self-hosted LM Studio box; the fallbacks
widen that to DeepSeek / the gateway's configured endpoints. An operator who
does not want a provider to ever see audited code drops it from
``KENBUN_SENIOR_PROVIDERS`` (or leaves its key / endpoint unconfigured -- an
unconfigured client raises before any network I/O, so nothing leaves the box).

Mirrors tools/strategy/decomposition.py; the shared machinery is a candidate
for extraction once DSH-06 slices 4-5 land (see deepseek-harness-adoption memo).
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Callable, Dict, Optional, Tuple

from tools.strategy.resolver import Resolver, ResolverExhausted

__all__ = ["run_senior_review", "senior_reviewer_resolver", "ResolverExhausted"]

logger = logging.getLogger("kenbun.senior_reviewer")

_DEFAULT_COOLDOWN_S = 300.0
_COOLDOWN_ENV = "KENBUN_SENIOR_COOLDOWN_S"

# Ordered allowlist. Default is operator-configured endpoints only (LM Studio,
# then the gateway's PRIMARY/FALLBACK URLs). Add "deepseek" via
# KENBUN_SENIOR_PROVIDERS to allow that third-party fallback for the commit gate.
_KNOWN = ("lmstudio", "deepseek", "gateway")
_DEFAULT_ORDER = ("lmstudio", "gateway")
_PROVIDERS_ENV = "KENBUN_SENIOR_PROVIDERS"
_PRIMARY = _DEFAULT_ORDER[0]

_ERROR_PREFIXES = ("❌", "⚠️", "error:", "exception:")
_OUTAGE_MARKERS = ("resource_exhausted", "quota exceeded", "rate limit exceeded")


def _env_cooldown_s() -> float:
    raw = os.getenv(_COOLDOWN_ENV, "").strip()
    if not raw:
        return _DEFAULT_COOLDOWN_S
    try:
        val = float(raw)
        return val if val > 0 else _DEFAULT_COOLDOWN_S
    except ValueError:
        logger.warning("%s=%r is not a number; using %.0fs", _COOLDOWN_ENV, raw, _DEFAULT_COOLDOWN_S)
        return _DEFAULT_COOLDOWN_S


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


# Indirect through the module globals so a test can monkeypatch one provider.
_PROVIDER_FNS: Dict[str, Callable[[str, str, int], str]] = {
    "lmstudio": lambda sp, um, mt: _lmstudio_provider(sp, um, mt),
    "deepseek": lambda sp, um, mt: _deepseek_provider(sp, um, mt),
    "gateway": lambda sp, um, mt: _gateway_provider(sp, um, mt),
}


def _configured_order() -> Tuple[str, ...]:
    raw = os.getenv(_PROVIDERS_ENV, "").strip()
    if not raw:
        return _DEFAULT_ORDER
    picked = tuple(
        name for name in (p.strip().lower() for p in raw.split(","))
        if name in _PROVIDER_FNS
    )
    if not picked:
        logger.warning("%s=%r matched no known providers; using default order", _PROVIDERS_ENV, raw)
        return _DEFAULT_ORDER
    return picked


def _build_resolver() -> Resolver:
    r: Resolver = Resolver(cooldown_s=_env_cooldown_s())
    for name in _configured_order():
        r.add(name, _PROVIDER_FNS[name])
    logger.info("senior-reviewer resolver built with providers: %s", r.names())
    return r


_RESOLVER: Optional[Resolver] = None
_RESOLVER_LOCK = threading.Lock()


def senior_reviewer_resolver() -> Resolver:
    """The process-wide senior-reviewer Resolver (lazily built; order from
    KENBUN_SENIOR_PROVIDERS or the default lmstudio -> deepseek -> gateway)."""
    global _RESOLVER
    if _RESOLVER is None:
        with _RESOLVER_LOCK:
            if _RESOLVER is None:
                _RESOLVER = _build_resolver()
    return _RESOLVER


def _unavailable(out: object) -> bool:
    if not isinstance(out, str) or not out.strip():
        return True
    low = out.strip().lower()
    return low.startswith(_ERROR_PREFIXES) or any(m in low for m in _OUTAGE_MARKERS)


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
    res = resolver or senior_reviewer_resolver()
    try:
        name, content = res.run(
            lambda provider: provider(system_prompt, user_message, max_tokens),
            is_unavailable=_unavailable,
        )
    except ResolverExhausted as e:
        logger.error("senior reviewer: every provider is unavailable (%s)", e)
        _record_event("exhausted", provider=None, detail=str(e), resolver=res)
        raise
    if name != _PRIMARY:
        logger.warning("senior reviewer served by fallback provider %r (%s unavailable)", name, _PRIMARY)
        _record_event("failover", provider=name, detail=f"{_PRIMARY} unavailable", resolver=res)
    return name, content


def _record_event(kind: str, *, provider: Optional[str], detail: str, resolver: Resolver) -> None:
    try:
        from tools.strategy.resolver_events import record

        record(kind, capability="senior_reviewer", provider=provider,
               detail=detail, providers_order=resolver.names())
    except Exception as e:  # noqa: BLE001 -- telemetry must never break the commit gate
        logger.debug("senior_reviewer: could not record %s event: %s", kind, e)
