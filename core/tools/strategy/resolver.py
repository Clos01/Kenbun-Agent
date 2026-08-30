"""DSH-06 slice 1 -- health-aware provider resolution.

    docs/composability-primer.md: a capability with exactly one provider is the
    same bug as static composition -- a single fixed choice in a load-bearing
    spot. When it fails you are just down.

`Resolver` is the reusable "try providers in order, demote a failed one, recover
it after a cooldown" primitive. The shell / subagent seams do a hand-rolled
version of this; DSH-06 factors it out and points every single-provider
capability (Queen decomposition, the supervisor, memory, ...) at it.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Generic, List, Optional, Tuple, TypeVar

logger = logging.getLogger("kenbun.resolver")

P = TypeVar("P")          # a provider (adapter object, callable, client, ...)
R = TypeVar("R")          # what calling a provider returns


class ResolverExhausted(RuntimeError):
    """Every provider was tried and none could serve."""


@dataclass
class _Entry(Generic[P]):
    name: str
    provider: P
    demoted_until: float = 0.0        # monotonic time; 0 = healthy
    fail_count: int = 0


class Resolver(Generic[P]):
    """An ordered set of named providers with health tracking.

    * ``add(name, provider)`` -> a disposer that removes it (DSH-01 pattern).
    * ``mark_unhealthy(name)`` demotes a provider for ``cooldown_s`` seconds; it
      auto-recovers when the cooldown lapses.
    * ``candidates()`` yields healthy providers first, in insertion order, then
      demoted ones as a last resort -- so an all-demoted capability still tries
      rather than dead-ending.
    * ``run(call, is_unavailable=...)`` walks the candidates, calling each until
      one serves; a provider that raises or returns an "unavailable" result is
      demoted and the next is tried.
    """

    def __init__(self, cooldown_s: float = 120.0) -> None:
        self._lock = threading.RLock()
        self._entries: List[_Entry[P]] = []
        self._cooldown_s = cooldown_s

    # ------------------------------------------------------------- membership
    def add(self, name: str, provider: P) -> Callable[[], None]:
        with self._lock:
            self._entries = [e for e in self._entries if e.name != name]
            self._entries.append(_Entry(name=name, provider=provider))
        logger.info("resolver: provider %r registered (order: %s)", name, self.names())

        def _remove() -> None:
            with self._lock:
                self._entries = [e for e in self._entries if e.name != name]

        return _remove

    def names(self) -> List[str]:
        with self._lock:
            return [e.name for e in self._entries]

    # ------------------------------------------------------------- health
    def mark_unhealthy(self, name: str, cooldown_s: Optional[float] = None) -> None:
        with self._lock:
            for e in self._entries:
                if e.name == name:
                    e.demoted_until = time.monotonic() + (cooldown_s or self._cooldown_s)
                    e.fail_count += 1
                    logger.warning("resolver: provider %r demoted for %.0fs (fail #%d)",
                                   name, cooldown_s or self._cooldown_s, e.fail_count)
                    return

    def mark_healthy(self, name: str) -> None:
        with self._lock:
            for e in self._entries:
                if e.name == name:
                    e.demoted_until = 0.0
                    return

    def is_healthy(self, name: str) -> bool:
        with self._lock:
            for e in self._entries:
                if e.name == name:
                    return e.demoted_until == 0.0 or time.monotonic() >= e.demoted_until
        return False

    # ------------------------------------------------------------- selection
    def candidates(self) -> List[Tuple[str, P]]:
        now = time.monotonic()
        with self._lock:
            healthy, demoted = [], []
            for e in self._entries:
                if e.demoted_until and now < e.demoted_until:
                    demoted.append((e.name, e.provider))
                else:
                    if e.demoted_until:
                        e.demoted_until = 0.0        # cooldown lapsed -> auto-recover
                        logger.info("resolver: provider %r recovered", e.name)
                    healthy.append((e.name, e.provider))
        return healthy + demoted

    def pick(self) -> Optional[Tuple[str, P]]:
        c = self.candidates()
        return c[0] if c else None

    def snapshot(self) -> List[dict]:
        """Read-only health view for observability / UI, in configured (insertion)
        order. Does not mutate -- a lapsed cooldown still reads as healthy here
        but is only cleared on the next ``candidates()`` call."""
        now = time.monotonic()
        with self._lock:
            out: List[dict] = []
            for i, e in enumerate(self._entries):
                demoted = bool(e.demoted_until and now < e.demoted_until)
                out.append({
                    "name": e.name,
                    "healthy": not demoted,
                    "primary": i == 0,
                    "fail_count": e.fail_count,
                    "cooldown_remaining_s": round(e.demoted_until - now, 1) if demoted else 0.0,
                })
            return out

    def run(
        self,
        call: Callable[[P], R],
        *,
        is_unavailable: Optional[Callable[[R], bool]] = None,
    ) -> Tuple[str, R]:
        """Call each candidate until one serves. Returns ``(name, result)``.

        A provider that raises, or returns a result ``is_unavailable`` flags, is
        demoted and the walk continues. If every provider is unavailable the last
        non-exception result is returned; if every provider raised,
        ``ResolverExhausted`` is raised from the last exception.
        """
        cands = self.candidates()
        if not cands:
            raise ResolverExhausted("no providers registered")

        last_result: Tuple[str, R] | None = None
        last_exc: Optional[BaseException] = None
        for name, provider in cands:
            try:
                result = call(provider)
            except Exception as e:                      # noqa: BLE001 -- policy: any error demotes
                logger.warning("resolver: provider %r raised %s; trying next", name, type(e).__name__)
                self.mark_unhealthy(name)
                last_exc = e
                continue
            if is_unavailable is not None and is_unavailable(result):
                logger.warning("resolver: provider %r reported unavailable; trying next", name)
                self.mark_unhealthy(name)
                last_result = (name, result)
                continue
            if last_result is not None or last_exc is not None:
                logger.info("resolver: %r served after falling back", name)
            return name, result

        if last_result is not None:
            return last_result
        raise ResolverExhausted(
            f"all {len(cands)} providers raised; last was {type(last_exc).__name__}"
        ) from last_exc
