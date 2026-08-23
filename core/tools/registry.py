import atexit
import contextlib
import functools
import inspect
import logging
import sys
import threading
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
    """Thread-safe global registry for all dynamically discovered Kenbun tools and pipelines."""
    
    def __init__(self):
        self._tools: Dict[str, ToolEntry] = {}
        self._pipelines: Dict[str, PipelineEntry] = {}
        self._lock = threading.RLock()

    def register_tool(self, entry: ToolEntry) -> None:
        with self._lock:
            self._tools[entry.name] = entry

    def get_tool(self, name: str) -> Optional[ToolEntry]:
        with self._lock:
            return self._tools.get(name)

    def get_all_tools(self) -> Dict[str, ToolEntry]:
        with self._lock:
            return dict(self._tools)

    def register_pipeline(self, entry: PipelineEntry) -> None:
        with self._lock:
            self._pipelines[entry.name] = entry

    def get_pipeline(self, name: str) -> Optional[PipelineEntry]:
        with self._lock:
            return self._pipelines.get(name)

    def get_all_pipelines(self) -> Dict[str, PipelineEntry]:
        with self._lock:
            return dict(self._pipelines)

    def clear(self) -> None:
        with self._lock:
            self._tools.clear()
            self._pipelines.clear()

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
    requires_env: Optional[List[str]] = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to designate a function as an active sovereign tool in the Swarm.
    
    Args:
        name: Optional override for the tool ID (defaults to function name).
        category: Operational swarm module (e.g. 'Strategy', 'Sensory', 'Memory').
        requires_env: Optional list of environment variable names required for enablement.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        tool_name = name or func.__name__
        
        # Parse and sanitize docstrings for model readability
        raw_doc = func.__doc__ or "No description provided."
        doc_lines = [line.strip() for line in raw_doc.strip().split("\n")]
        description = "\n".join(doc_lines)
        
        is_async = inspect.iscoroutinefunction(func)

        if is_async:
            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Stdout guard around the entire coroutine: any stray print()
                # inside async tool bodies (or their awaited internals) gets
                # routed to stderr so the MCP JSON-RPC channel stays clean.
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

        # Register the WRAPPER, not the bare function.
        #
        # server.py exposes every tool to FastMCP via
        # ``mcp.tool(...)(tool_entry.handler)``, so whatever lands in this entry
        # is what actually serves MCP traffic. Registering ``func`` here meant
        # every MCP call bypassed all three guarantees the wrapper exists to
        # provide: the stdout guard that keeps stray print() out of the JSON-RPC
        # framing, the surrogate sanitisation of str returns, and outcome
        # telemetry. functools.wraps sets __wrapped__, so inspect.signature()
        # still resolves the real signature and FastMCP's schema generation is
        # unaffected.
        entry = ToolEntry(
            name=tool_name,
            category=category,
            description=description,
            handler=wrapper,
            is_async=is_async,
            requires_env=requires_env or []
        )

        registry.register_tool(entry)

        return wrapper
    return decorator
