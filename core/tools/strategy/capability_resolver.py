"""DSH-06 -- shared wiring for pointing a single-provider capability at a Resolver.

The :class:`~tools.strategy.resolver.Resolver` primitive (slice 1) does the
health tracking. This module is the per-capability layer that was otherwise
copy-pasted between decomposition.py and senior_reviewer.py: build a
lazily-cached, process-wide resolver from an ordered provider map, honour a
``KENBUN_*_PROVIDERS`` allowlist and a ``KENBUN_*_COOLDOWN_S`` override, and
record failover / exhaustion to the cross-process ``resolver_events`` trail the
Observatory panel reads.

A capability module becomes: define adapters -> ``CapabilityResolver(...)`` ->
two thin wrappers. See decomposition.py / senior_reviewer.py.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Callable, Dict, Optional, Sequence, Tuple, TypeVar

from tools.strategy.resolver import Resolver, ResolverExhausted

__all__ = ["CapabilityResolver", "ResolverExhausted", "text_unavailable"]

R = TypeVar("R")

_ERROR_PREFIXES = ("❌", "⚠️", "error:", "exception:")
_OUTAGE_MARKERS = ("resource_exhausted", "quota exceeded", "rate limit exceeded")
_DEFAULT_COOLDOWN_S = 300.0


def text_unavailable(out: object) -> bool:
    """True if a provider's string result looks like an outage, not an answer:
    empty / whitespace, an error-prefixed line, or a quota / rate-limit marker."""
    if not isinstance(out, str) or not out.strip():
        return True
    low = out.strip().lower()
    return low.startswith(_ERROR_PREFIXES) or any(m in low for m in _OUTAGE_MARKERS)


def _env_float(name: str, default: float, log: logging.Logger) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        val = float(raw)
        return val if val > 0 else default
    except ValueError:
        log.warning("%s=%r is not a positive number; using %s", name, raw, default)
        return default


class CapabilityResolver:
    """A lazily-built, process-wide Resolver for one named capability.

    capability:     short slug -- the ``resolver_events`` tag and logger suffix
                    (e.g. "queen_decomposition").
    provider_fns:   ordered {name: callable}. Wrap each in a lambda that
                    indirects through a module global if a test must monkeypatch
                    one provider.
    providers_env:  env var with a comma-separated allowlist / reorder.
    cooldown_env:   env var overriding the demotion window (seconds).
    default_order:  which provider_fns keys to use (and in what order) when
                    providers_env is unset. Defaults to all, insertion order.
    """

    def __init__(self, capability: str, provider_fns: Dict[str, Callable],
                 *, providers_env: str, cooldown_env: str,
                 default_order: Optional[Sequence[str]] = None) -> None:
        self.capability = capability
        self._fns: Dict[str, Callable] = dict(provider_fns)
        self._providers_env = providers_env
        self._cooldown_env = cooldown_env
        self._default_order: Tuple[str, ...] = (
            tuple(default_order) if default_order else tuple(provider_fns)
        )
        if not self._default_order:
            raise ValueError(f"{capability}: at least one provider is required")
        unknown = [n for n in self._default_order if n not in self._fns]
        if unknown:
            raise ValueError(f"{capability}: default_order names not in provider_fns: {unknown}")
        self.primary = self._default_order[0]
        self._log = logging.getLogger(f"kenbun.{capability}")
        self._resolver: Optional[Resolver] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------- config
    def _order(self) -> Tuple[str, ...]:
        raw = os.getenv(self._providers_env, "").strip()
        if not raw:
            return self._default_order
        picked = tuple(
            n for n in (p.strip().lower() for p in raw.split(",")) if n in self._fns
        )
        if not picked:
            self._log.warning("%s=%r matched no known providers; using default order",
                              self._providers_env, raw)
            return self._default_order
        return picked

    def _build(self) -> Resolver:
        r = Resolver(cooldown_s=_env_float(self._cooldown_env, _DEFAULT_COOLDOWN_S, self._log))
        for name in self._order():
            r.add(name, self._fns[name])
        self._log.info("%s resolver built with providers: %s", self.capability, r.names())
        return r

    def resolver(self) -> Resolver:
        """The process-wide Resolver -- built once under a lock, then shared, so
        concurrent callers see one view of provider health."""
        if self._resolver is None:
            with self._lock:
                if self._resolver is None:
                    self._resolver = self._build()
        return self._resolver

    def reset(self) -> None:
        """Drop the cached resolver so the next resolver() rebuilds it (tests)."""
        with self._lock:
            self._resolver = None

    # ------------------------------------------------------------- run
    def run(self, call: Callable[[Callable], R], *,
            is_unavailable: Optional[Callable[[R], bool]] = None,
            resolver: Optional[Resolver] = None) -> Tuple[str, R]:
        """Walk the candidates until one serves; return ``(provider_name, result)``.

        Records a ``failover`` event when a non-primary serves and an
        ``exhausted`` event (then re-raises :class:`ResolverExhausted`) when
        every provider is down. The per-provider failure detail is already in
        the log via ``Resolver.run`` -- callers should surface a generic message.
        """
        res = resolver or self.resolver()
        try:
            name, out = res.run(call, is_unavailable=is_unavailable)
        except ResolverExhausted as e:
            self._log.error("%s: every provider is unavailable (%s)", self.capability, e)
            self._record("exhausted", None, str(e), res)
            raise
        if name != self.primary:
            self._log.warning("%s served by fallback provider %r (%s unavailable)",
                              self.capability, name, self.primary)
            self._record("failover", name, f"{self.primary} unavailable", res)
        return name, out

    def _record(self, kind: str, provider: Optional[str], detail: str, res: Resolver) -> None:
        try:
            from tools.strategy.resolver_events import record

            record(kind, capability=self.capability, provider=provider,
                   detail=detail, providers_order=res.names())
        except Exception as e:  # noqa: BLE001 -- telemetry must never break a live call
            self._log.debug("%s: could not record %s event: %s", self.capability, kind, e)
