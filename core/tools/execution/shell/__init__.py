"""The `shell` capability seam (DSH-02, docs/deepseek-harness-study.md).

    from tools.execution.shell import shell
    res = shell.run("git status --porcelain")
    if res.ok:
        ...

Definition : ShellResult + ShellProvider          (definition.py)
Providers  : LocalShellProvider (default active)   (provider_local.py)
             E2BShellProvider (opt-in)             (provider_e2b.py)
Consumers  : any caller of ``shell.run(...)``

Registering a provider or switching the active one is a **revertible effect**
(DSH-01): ``register_shell_provider`` and ``shell.use`` each return a zero-arg
disposer that restores the previous state. That is what lets a profile point the
whole shell surface at a sandbox for one session and cleanly undo it.
"""
from __future__ import annotations

import logging
import threading
from typing import Callable, Dict, List, Optional

from .definition import ShellProvider, ShellResult
from .provider_local import LocalShellProvider

logger = logging.getLogger("kenbun.shell")

__all__ = ["shell", "register_shell_provider", "ShellResult", "ShellProvider"]


class _ShellSeam:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._providers: Dict[str, ShellProvider] = {}
        self._active: str = ""
        self.register_provider(LocalShellProvider(), make_active=True)

    # ------------------------------------------------------------- providers
    def register_provider(
        self, provider: ShellProvider, *, make_active: bool = False
    ) -> Callable[[], None]:
        """Add ``provider``. Returns a disposer that removes it and restores the
        previously-active provider if this one had taken over."""
        with self._lock:
            prev_active = self._active
            self._providers[provider.name] = provider
            if make_active or not self._active:
                self._active = provider.name
            became_active = self._active
        logger.info(
            "shell: registered provider %r (active=%r, was %r)",
            provider.name, became_active, prev_active or None,
        )

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

    def _fallback_active(self, preferred: str) -> str:
        """Which provider becomes active when the current one is disposed.

        Deterministic (never dict-insertion-order): the just-restored `preferred`
        if it survived, else the built-in ``local``, else the
        alphabetically-first remaining provider, else ``""`` (none left)."""
        if preferred and preferred in self._providers:
            return preferred
        if "local" in self._providers:
            return "local"
        remaining = sorted(self._providers)
        return remaining[0] if remaining else ""

    def use(self, name: str) -> Callable[[], None]:
        """Make an already-registered provider active. Returns a disposer that
        restores whichever provider was active before."""
        with self._lock:
            if name not in self._providers:
                raise KeyError(
                    f"no shell provider named {name!r}; registered: {sorted(self._providers)}"
                )
            prev = self._active
            self._active = name
        logger.info("shell: active provider %r -> %r", prev or None, name)

        armed = True

        def _restore() -> None:
            nonlocal armed
            with self._lock:
                if not armed:
                    return
                armed = False
                if prev in self._providers:
                    self._active = prev
                    logger.info("shell: active provider restored to %r", prev)

        return _restore

    # ------------------------------------------------------------- introspection
    # Provider names ('local', 'e2b', ...) are architecture identifiers, not
    # secrets -- they are in the source tree and the docs. `providers()` and the
    # `use()` error message deliberately expose the same non-sensitive list so a
    # caller can discover what it may switch to.
    def active(self) -> str:
        with self._lock:
            return self._active

    def providers(self) -> List[str]:
        with self._lock:
            return sorted(self._providers)

    # ------------------------------------------------------------- the call
    def run(
        self,
        command: str,
        *,
        cwd: Optional[str] = None,
        timeout: Optional[float] = 30.0,
    ) -> ShellResult:
        with self._lock:
            provider = self._providers[self._active]
        return provider.run(command, cwd=cwd, timeout=timeout)


shell = _ShellSeam()
register_shell_provider = shell.register_provider
