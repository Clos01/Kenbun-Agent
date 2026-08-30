"""DSH-06 slice 2 -- Queen task decomposition, health-aware and multi-provider.

    docs/composability-primer.md: a load-bearing capability with exactly one
    provider is static composition in disguise -- when that one provider is
    down, so are you.

The swarm's Queen (``spawn_swarm`` in orchestrator.py) decomposes an objective
into a JSON array of atomic tasks. It used to call ``call_gemini_pro`` directly,
so a Gemini quota exhaustion (429 / RESOURCE_EXHAUSTED) meant *no swarm at all*.

This module points that one call at a :class:`~tools.strategy.resolver.Resolver`
carrying up to three reasoning providers, tried in order:

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

import logging
import os
import threading
from typing import Callable, Dict, Optional, Tuple

from tools.strategy.resolver import Resolver, ResolverExhausted

__all__ = ["run_decomposition", "decomposition_resolver", "ResolverExhausted"]

logger = logging.getLogger("kenbun.decomposition")

_DEFAULT_COOLDOWN_S = 300.0
_COOLDOWN_ENV = "KENBUN_QUEEN_COOLDOWN_S"


def _env_cooldown_s() -> float:
    """Provider demotion window. LLM outages (quota resets, endpoint restarts)
    heal on the order of minutes; tune via KENBUN_QUEEN_COOLDOWN_S."""
    raw = os.getenv(_COOLDOWN_ENV, "").strip()
    if not raw:
        return _DEFAULT_COOLDOWN_S
    try:
        val = float(raw)
        return val if val > 0 else _DEFAULT_COOLDOWN_S
    except ValueError:
        logger.warning("%s=%r is not a number; using %.0fs", _COOLDOWN_ENV, raw, _DEFAULT_COOLDOWN_S)
        return _DEFAULT_COOLDOWN_S


# Ordered allowlist. Override with KENBUN_QUEEN_PROVIDERS="gemini,local" to drop
# one (e.g. to keep the objective away from DeepSeek). Unknown names are ignored.
_DEFAULT_ORDER = ("gemini", "deepseek", "local")
_PROVIDERS_ENV = "KENBUN_QUEEN_PROVIDERS"

_QUEEN_SYSTEM = (
    "You are the Kenbun Queen, a high-reasoning task decomposer. "
    "Return ONLY a valid JSON array of atomic task objects -- no prose, no markdown fences."
)

# If a provider returns a *string* (rather than raising) that starts with one of
# these, treat it as an outage and fall through. The direct clients all raise on
# failure today; this is belt-and-suspenders for any that start returning error
# text instead.
_ERROR_PREFIXES = ("❌", "⚠️", "error:", "exception:")
_OUTAGE_MARKERS = ("resource_exhausted", "quota exceeded", "rate limit exceeded")


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


# Indirect through the module globals (not bound references) so a test can
# monkeypatch a single ``_*_provider`` and the resolver picks it up.
_PROVIDER_FNS: Dict[str, Callable[[str], str]] = {
    "gemini": lambda p: _gemini_provider(p),
    "deepseek": lambda p: _deepseek_provider(p),
    "local": lambda p: _local_provider(p),
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
    logger.info("decomposition resolver built with providers: %s", r.names())
    return r


_RESOLVER: Optional[Resolver] = None
_RESOLVER_LOCK = threading.Lock()


def decomposition_resolver() -> Resolver:
    """The process-wide decomposition Resolver (lazily built; order from the
    KENBUN_QUEEN_PROVIDERS env var, or the default gemini -> deepseek -> local).

    Built once under a lock so racing swarm spawns share one instance (and one
    view of provider health). ``Resolver`` itself is internally RLock-guarded, so
    concurrent ``run`` calls on the shared instance are safe -- at worst two
    spawns both discover Gemini is down and both demote it, which is idempotent.
    """
    global _RESOLVER
    if _RESOLVER is None:
        with _RESOLVER_LOCK:
            if _RESOLVER is None:
                _RESOLVER = _build_resolver()
    return _RESOLVER


# ----------------------------------------------------------------------- run
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
    provider raised -- the per-provider failure detail is already in the log via
    ``Resolver.run``; callers should surface a generic message, not the exception.

    ``is_usable`` lets the caller reject text that came back cleanly but is not a
    usable decomposition (e.g. "no JSON array in it") without this module having
    to import the caller's parser.
    """
    res = resolver or decomposition_resolver()

    def _unavailable(out: object) -> bool:
        if not isinstance(out, str) or not out.strip():
            return True
        low = out.strip().lower()
        if low.startswith(_ERROR_PREFIXES) or any(m in low for m in _OUTAGE_MARKERS):
            return True
        if is_usable is not None and not is_usable(out):
            return True
        return False

    try:
        name, raw = res.run(lambda provider: provider(queen_prompt), is_unavailable=_unavailable)
    except ResolverExhausted as e:
        logger.error("Queen decomposition: every reasoning provider is unavailable (%s)", e)
        raise
    if name != "gemini":
        logger.warning("Queen decomposition served by fallback provider %r (gemini unavailable)", name)
    return name, raw
