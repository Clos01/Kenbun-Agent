"""The `subagent` capability seam (DSH-04, docs/deepseek-harness-study.md).

    from tools.execution.subagent import subagent
    res = subagent.run("refactor the guardrail module", context="...")
    if res.ok:
        ...

Definition : SubagentResult + SubagentProvider        (definition.py)
Providers  : ClaudeCodeSubagentProvider               (provider_claude_code.py)
             InProcessSwarmSubagentProvider (default)  (provider_in_process.py)
Consumers  : any caller of ``subagent.run(...)`` -- `delegate_task` and the
             orchestrator are the ones to migrate (slice 2).

Registering a provider or switching the active one is a **revertible effect**
(DSH-01): ``register_subagent_provider`` / ``subagent.use`` each return a
zero-arg disposer that restores the previous state.

`run(..., fallback=True)` (the default) walks the other registered providers in a
deterministic order if the active one reports itself unavailable -- which is how
a Gemini 429 in the in-process swarm stops being a dead end.
"""
from __future__ import annotations

import logging
import threading
from typing import Callable, Dict, List, Optional

from .definition import SubagentProvider, SubagentResult, task_label
from .provider_in_process import InProcessSwarmSubagentProvider

logger = logging.getLogger("kenbun.subagent")

__all__ = [
    "subagent",
    "register_subagent_provider",
    "SubagentResult",
    "SubagentProvider",
]

# Deterministic order the fallback walk tries providers in (any not listed go
# last, alphabetically). `in-process-swarm` first: it is the current default and
# the richest; `claude-code` next; unknown providers after.
_FALLBACK_ORDER = ("in-process-swarm", "claude-code")


class _SubagentSeam:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._providers: Dict[str, SubagentProvider] = {}
        self._active: str = ""
        self.register_provider(InProcessSwarmSubagentProvider(), make_active=True)

    # ------------------------------------------------------------- providers
    def register_provider(
        self, provider: SubagentProvider, *, make_active: bool = False
    ) -> Callable[[], None]:
        with self._lock:
            prev_active = self._active
            self._providers[provider.name] = provider
            if make_active or not self._active:
                self._active = provider.name
            became = self._active
        logger.info("subagent: registered provider %r (active=%r, was %r)",
                    provider.name, became, prev_active or None)

        armed = True

        def _dispose() -> None:
            nonlocal armed
            with self._lock:
                if not armed:
                    return
                armed = False
                if self._providers.get(provider.name) is provider:
                    del self._providers[provider.name]
                if self._active == provider.name:
                    self._active = self._fallback_active(prev_active)

        return _dispose

    def use(self, name: str) -> Callable[[], None]:
        with self._lock:
            if name not in self._providers:
                raise KeyError(
                    f"no subagent provider named {name!r}; registered: {sorted(self._providers)}"
                )
            prev = self._active
            self._active = name
        logger.info("subagent: active provider %r -> %r", prev or None, name)

        armed = True

        def _restore() -> None:
            nonlocal armed
            with self._lock:
                if not armed:
                    return
                armed = False
                if prev in self._providers:
                    self._active = prev

        return _restore

    def _fallback_active(self, preferred: str) -> str:
        if preferred and preferred in self._providers:
            return preferred
        if "in-process-swarm" in self._providers:
            return "in-process-swarm"
        remaining = sorted(self._providers)
        return remaining[0] if remaining else ""

    # ------------------------------------------------------------- introspection
    # Provider names are architecture identifiers (in the source tree and docs),
    # not secrets -- `providers()` and the `use()` error deliberately expose them.
    def active(self) -> str:
        with self._lock:
            return self._active

    def providers(self) -> List[str]:
        with self._lock:
            return sorted(self._providers)

    def _ordered_candidates(self, start: str) -> List[str]:
        with self._lock:
            names = list(self._providers)
        rank = {n: i for i, n in enumerate(_FALLBACK_ORDER)}
        names.sort(key=lambda n: (rank.get(n, len(_FALLBACK_ORDER)), n))
        # start with the active provider, then the rest in deterministic order
        return [start] + [n for n in names if n != start]

    # ------------------------------------------------------------- the call
    def run(
        self,
        task: str,
        *,
        context: str = "",
        cwd: Optional[str] = None,
        timeout: Optional[float] = None,
        fallback: bool = True,
    ) -> SubagentResult:
        if timeout is not None and timeout <= 0:
            raise ValueError(f"timeout must be positive or None, got {timeout!r}")

        with self._lock:
            active = self._active
            if not active:
                return SubagentResult(
                    task_label=task_label(task), ok=False, output="",
                    error="no subagent provider registered",
                )

        tried: List[str] = []
        candidates = self._ordered_candidates(active) if fallback else [active]
        last: Optional[SubagentResult] = None
        for name in candidates:
            with self._lock:
                provider = self._providers.get(name)
            # `provider` is now a strong local ref: a concurrent dispose() that
            # unregisters it cannot pull it out from under this call. run() is
            # invoked outside the lock so a slow child never blocks registration.
            if provider is None:
                continue
            tried.append(name)
            result = provider.run(task, context=context, cwd=cwd, timeout=timeout)
            last = result
            if result.ok or not fallback:
                if len(tried) > 1:
                    logger.info("subagent: %r succeeded after falling back from %r",
                                name, tried[:-1])
                return result
            if not result.meta.get("unavailable"):
                # a real failure, not "provider can't run" -- do not mask it by
                # trying another provider on the same (possibly side-effecting) task
                return result
            logger.warning("subagent: provider %r unavailable, trying next", name)

        return last or SubagentResult(
            task_label=task_label(task), ok=False, output="",
            error=f"all subagent providers failed: {tried}",
        )


subagent = _SubagentSeam()
register_subagent_provider = subagent.register_provider
