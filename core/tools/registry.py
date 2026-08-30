import atexit
import contextlib
import functools
import inspect
import logging
import sys
import threading
import weakref
from typing import Any, Callable, Dict, List, Optional, Tuple, Set
try:
    from pydantic import BaseModel, Field
except ImportError:
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    def Field(*args, **kwargs):
        return None

logger = logging.getLogger("registry")

# Identity set of every wrapper `sovereign_tool` has produced. A mirror
# (server.py's FastMCP list) checks membership before exposing a handler, so a
# hand-built ToolEntry carrying a raw callable cannot reach an MCP client -- the
# raw callable is not in here and cannot be added without importing this private
# module and calling .add (by which point the caller is already running
# arbitrary in-process code). WeakSet: a disposed tool's wrapper is collected.
_SOVEREIGN_WRAPPERS: "weakref.WeakSet[Callable]" = weakref.WeakSet()


def is_sovereign_wrapper(fn: object) -> bool:
    """True iff ``fn`` is a callable that ``sovereign_tool`` built (identity check)."""
    try:
        return fn in _SOVEREIGN_WRAPPERS
    except TypeError:
        return False  # unhashable arg -> definitely not one of our wrappers


@contextlib.contextmanager
def _silence_stdout_during_tool_call():
    """Redirect stdout → stderr while a sovereign tool is executing.

    FastMCP uses stdout for JSON-RPC framing; any stray ``print(...)`` from a
    tool implementation (or one of its transitive imports) corrupts that
    channel and crashes the MCP client. This guard isolates the noisy body of
    the tool from the framing layer. FastMCP serializes the tool's return
    value AFTER this context exits, so the JSON-RPC write still lands on the
    real stdout.

    A 1:1 copy of ``silence_stdout`` in ``tools/infrastructure/server.py`` —
    duplicated here so ``sovereign_tool`` (which is imported very early during
    bootstrap) can use it without a circular dependency on ``server``.
    """
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old_stdout

class ToolEntry(BaseModel):
    """Metadata representing a dynamically registered Kenbun sovereign tool."""
    name: str
    category: str = "General"
    description: str
    handler: Callable = Field(exclude=True)
    is_async: bool
    requires_env: List[str] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True

class PipelineEntry(BaseModel):
    """Metadata representing a dynamic workflow pipeline."""
    name: str
    description: str
    builder: Callable = Field(exclude=True)
    
    class Config:
        arbitrary_types_allowed = True

class SovereignRegistry:
    """Thread-safe global registry for all dynamically discovered Kenbun tools and pipelines.

    Registration is a *revertible effect* (DSH-01, docs/deepseek-harness-study.md):
    ``register_tool`` / ``register_pipeline`` return a zero-arg **disposer** that
    removes exactly what they added. The disposer is idempotent and will not evict
    a later re-registration made under the same name. Consumers that mirror the
    registry elsewhere -- the FastMCP tool list in ``server.py`` is the one that
    matters today -- subscribe via ``add_removal_listener`` and tear their copy
    down when a disposer fires. This is the first step toward unloading a tool
    from a running swarm without a process restart.

    Removal is atomic: the dict mutation and the listener notifications happen
    under one hold of ``self._lock`` so a mirror can never observe a removal event
    for a name that a concurrent thread has already re-registered. The lock is an
    ``RLock``, so a listener may call back into the registry on the same thread;
    a listener MUST NOT block on another thread that needs this lock, and MUST
    return quickly -- it runs on the remover's thread inside the critical section.
    A listener that raises is logged at ``error`` (the mirror is now desynced) and
    the remaining listeners and the removal itself still complete.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolEntry] = {}
        self._pipelines: Dict[str, PipelineEntry] = {}
        self._lock = threading.RLock()
        self._tool_removal_listeners: List[Callable[[str], None]] = []
        self._pipeline_removal_listeners: List[Callable[[str], None]] = []
        self._tool_registration_listeners: List[Callable[[ToolEntry], None]] = []

    # ------------------------------------------------------------------ tools
    def register_tool(self, entry: ToolEntry, *, exclusive: bool = False) -> Callable[[], None]:
        """Register ``entry`` and return its disposer.

        ``exclusive=True`` makes the check-and-insert atomic: if a tool is
        already registered under this name, raise ``KeyError`` instead of
        overwriting it. Two concurrent hot-mounts of the same name cannot then
        both "win" and leak one disposer. Default (``False``) overwrites, as the
        ``@sovereign_tool`` decorator relies on at import time.

        Defence in depth (DSH-05 follow-up): if ``entry.handler`` is not a
        ``sovereign_tool`` wrapper -- a hand-built ToolEntry carrying a raw
        callable -- it is rescued here: re-wrapped so the stdout guard and
        telemetry apply, and the stored entry carries the wrapped handler. So
        NOTHING unguarded can live in ``_tools`` (not just "cannot reach MCP").
        """
        if not is_sovereign_wrapper(entry.handler):
            logger.warning(
                "registry: tool %r registered with a raw (non-@sovereign_tool) "
                "handler -- auto-wrapping it with the stdout guard + telemetry",
                entry.name,
            )
            wrapped = build_sovereign_wrapper(
                entry.handler, tool_name=entry.name, category=entry.category,
            )
            entry = entry.model_copy(update={"handler": wrapped}) if hasattr(entry, "model_copy") \
                else ToolEntry(name=entry.name, category=entry.category,
                               description=entry.description, handler=wrapped,
                               is_async=entry.is_async, requires_env=list(entry.requires_env))

        with self._lock:
            if exclusive and entry.name in self._tools:
                raise KeyError(f"a tool named {entry.name!r} is already registered")
            self._tools[entry.name] = entry
            # Registration and notification are one atomic critical section, same
            # as removal -- a mirror (server.py's FastMCP list) sees a consistent
            # add. This is what lets a tool mounted AFTER startup (DSH-05
            # hot_mount) still reach the live MCP surface, no restart.
            self._fire(self._tool_registration_listeners, entry)
        return self._make_disposer(self._tools, entry.name, entry, self._notify_tool_removed)

    def unregister_tool(self, name: str) -> bool:
        """Remove whatever tool is under ``name``. Returns True if one existed.

        Removal and notification are one atomic critical section (see class doc).
        """
        with self._lock:
            removed = self._tools.pop(name, None) is not None
            if removed:
                self._notify_tool_removed(name)
        return removed

    def get_tool(self, name: str) -> Optional[ToolEntry]:
        with self._lock:
            return self._tools.get(name)

    def get_all_tools(self) -> Dict[str, ToolEntry]:
        with self._lock:
            return dict(self._tools)

    def add_registration_listener(self, fn: Callable[[ToolEntry], None]) -> Callable[[], None]:
        """Call ``fn(entry)`` whenever a tool is registered. Returns a detach
        disposer. Same contract as ``add_removal_listener``: runs on the
        registering thread inside the lock, must be fast, a raise is logged."""
        return self._add_listener(self._tool_registration_listeners, fn)

    def add_removal_listener(self, fn: Callable[[str], None]) -> Callable[[], None]:
        """Call ``fn(tool_name)`` whenever a tool is removed. Returns a detach disposer.

        A listener that raises is logged and skipped -- one broken mirror must not
        block teardown of the others, nor the removal itself.
        """
        return self._add_listener(self._tool_removal_listeners, fn)

    # -------------------------------------------------------------- pipelines
    def register_pipeline(self, entry: PipelineEntry) -> Callable[[], None]:
        with self._lock:
            self._pipelines[entry.name] = entry
        return self._make_disposer(self._pipelines, entry.name, entry, self._notify_pipeline_removed)

    def unregister_pipeline(self, name: str) -> bool:
        with self._lock:
            removed = self._pipelines.pop(name, None) is not None
            if removed:
                self._notify_pipeline_removed(name)
        return removed

    def get_pipeline(self, name: str) -> Optional[PipelineEntry]:
        with self._lock:
            return self._pipelines.get(name)

    def get_all_pipelines(self) -> Dict[str, PipelineEntry]:
        with self._lock:
            return dict(self._pipelines)

    def add_pipeline_removal_listener(self, fn: Callable[[str], None]) -> Callable[[], None]:
        return self._add_listener(self._pipeline_removal_listeners, fn)

    # ---------------------------------------------------------------- shared
    def _make_disposer(self, store: dict, name: str, entry: Any,
                       notify: Callable[[str], None]) -> Callable[[], None]:
        armed = True

        def _dispose() -> None:
            nonlocal armed
            with self._lock:
                if not armed:
                    return
                armed = False
                # Only remove what we put there: a later register_* under the same
                # name replaces the value (a new object -> `is` fails even if its
                # fields were mutated), and disposing the stale handle must not
                # evict the live one.
                if store.get(name) is not entry:
                    return
                del store[name]
                # notify while still holding the lock -- a mirror must not see this
                # removal for a name another thread has already re-registered.
                notify(name)

        return _dispose

    def _add_listener(self, listeners: list, fn: Callable[[str], None]) -> Callable[[], None]:
        with self._lock:
            listeners.append(fn)

        def _detach() -> None:
            with self._lock:
                try:
                    listeners.remove(fn)
                except ValueError:
                    pass

        return _detach

    def _notify_tool_removed(self, name: str) -> None:
        self._fire(self._tool_removal_listeners, name)

    def _notify_pipeline_removed(self, name: str) -> None:
        self._fire(self._pipeline_removal_listeners, name)

    def _fire(self, listeners: list, arg: Any) -> None:
        # Always called with self._lock already held (RLock). Snapshot so a
        # listener that detaches itself mid-iteration does not corrupt the walk.
        # `arg` is a tool name (removal) or a ToolEntry (registration).
        label = getattr(arg, "name", arg)
        with self._lock:
            snapshot = list(listeners)
            for fn in snapshot:
                try:
                    fn(arg)
                except Exception as e:
                    logger.error(
                        f"registry listener {getattr(fn, '__name__', fn)!r} failed "
                        f"for '{label}' -- its mirror is now desynced: {e}",
                        exc_info=True,
                    )

    def clear(self) -> None:
        with self._lock:
            tool_names = list(self._tools)
            pipeline_names = list(self._pipelines)
            self._tools.clear()
            self._pipelines.clear()
            for n in tool_names:
                self._notify_tool_removed(n)
            for n in pipeline_names:
                self._notify_pipeline_removed(n)

# Thread-safe global registry instance
registry = SovereignRegistry()

_TELEMETRY_POOL = None
_TELEMETRY_LOCK = threading.Lock()


def _shutdown_telemetry_pool() -> None:
    global _TELEMETRY_POOL
    with _TELEMETRY_LOCK:
        if _TELEMETRY_POOL is not None:
            _TELEMETRY_POOL.shutdown(wait=False)


atexit.register(_shutdown_telemetry_pool)


def _record_tool_outcome(tool_name: str, category: str, success: bool) -> None:
    """Record one tool invocation in the intelligence store.

    Runs on a single background worker so a Postgres round-trip never lands on
    the tool's own latency path, and swallows everything: telemetry must not be
    able to slow down or break the tool it is measuring.

    KNOWN LIMITATION: success is inferred from "did not raise". Tools in this
    codebase that report failure by RETURNING an error string (rather than
    raising) are still counted as successes. Narrowing that requires the tools
    to raise, and is deliberately not papered over with string-sniffing here --
    a measurement layer that guesses is what this change exists to replace.
    """
    def _write() -> None:
        try:
            from tools.utils.bayesian import tune_swarm
            tune_swarm(tool_name, success, category)
        except Exception as e:
            logger.warning(f"Telemetry warning: tune_swarm failed for {tool_name}: {e}", exc_info=True)

    global _TELEMETRY_POOL
    try:
        with _TELEMETRY_LOCK:
            if _TELEMETRY_POOL is None:
                from concurrent.futures import ThreadPoolExecutor
                _TELEMETRY_POOL = ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="tool-telemetry"
                )
        _TELEMETRY_POOL.submit(_write)
    except Exception as e:
        logger.warning(f"Telemetry warning: Failed to record outcome for {tool_name}: {e}", exc_info=True)


def sovereign_tool(
    name: Optional[str] = None,
    category: str = "General",
    requires_env: Optional[List[str]] = None,
    exclusive: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to designate a function as an active sovereign tool in the Swarm.

    Args:
        name: Optional override for the tool ID (defaults to function name).
        category: Operational swarm module (e.g. 'Strategy', 'Sensory', 'Memory').
        requires_env: Optional list of environment variable names required for enablement.
        exclusive: If True, raise KeyError instead of overwriting a same-named tool
            (atomic check-and-insert). Used by DSH-05 hot_mount so two racing
            self-improvement loops cannot both register the same name.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        tool_name = name or func.__name__

        raw_doc = func.__doc__ or "No description provided."
        description = "\n".join(line.strip() for line in raw_doc.strip().split("\n"))
        is_async = inspect.iscoroutinefunction(func)

        wrapper = build_sovereign_wrapper(func, tool_name=tool_name, category=category)

        entry = ToolEntry(
            name=tool_name,
            category=category,
            description=description,
            handler=wrapper,
            is_async=is_async,
            requires_env=requires_env or [],
        )

        # DSH-01: keep the unload handle reachable from the decorated function so
        # a caller (or a self-modification pipeline) can retract the tool at
        # runtime -- registry.get_tool(name) disappears, server.py drops it from
        # FastMCP -- without restarting the process.
        wrapper._sovereign_disposer = registry.register_tool(entry, exclusive=exclusive)
        return wrapper

    return decorator


def build_sovereign_wrapper(
    func: Callable[..., Any], *, tool_name: str, category: str = "General",
) -> Callable[..., Any]:
    """Wrap ``func`` with the three guarantees every registered tool must carry:
    the stdout guard (stray ``print`` stays out of the MCP JSON-RPC framing),
    surrogate sanitisation of ``str`` returns, and outcome telemetry.

    The returned wrapper is stamped ``._sovereign_tool_name`` and recorded in
    ``_SOVEREIGN_WRAPPERS`` -- the identity set ``is_sovereign_wrapper`` checks and
    ``server.py`` gates MCP exposure on. This is the ONE place a guarded handler
    is minted; the decorator uses it, and ``register_tool`` uses it to rescue a
    raw callable so nothing unguarded can reach ``_tools``.
    """
    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            with _silence_stdout_during_tool_call():
                try:
                    res = await func(*args, **kwargs)
                except Exception:
                    _record_tool_outcome(tool_name, category, False)
                    raise
                if isinstance(res, str):
                    res = res.encode("utf-8", "replace").decode("utf-8")
                _record_tool_outcome(tool_name, category, True)
                return res
    else:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with _silence_stdout_during_tool_call():
                try:
                    res = func(*args, **kwargs)
                except Exception:
                    _record_tool_outcome(tool_name, category, False)
                    raise
                if isinstance(res, str):
                    res = res.encode("utf-8", "replace").decode("utf-8")
                _record_tool_outcome(tool_name, category, True)
                return res

    wrapper._sovereign_tool_name = tool_name
    _SOVEREIGN_WRAPPERS.add(wrapper)
    return wrapper
