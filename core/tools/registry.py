import contextlib
import functools
import inspect
import sys
import threading
from typing import Callable, Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator


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

    def register_tool(self, entry: ToolEntry):
        with self._lock:
            self._tools[entry.name] = entry

    def get_tool(self, name: str) -> Optional[ToolEntry]:
        with self._lock:
            return self._tools.get(name)

    def get_all_tools(self) -> Dict[str, ToolEntry]:
        with self._lock:
            return dict(self._tools)

    def register_pipeline(self, entry: PipelineEntry):
        with self._lock:
            self._pipelines[entry.name] = entry

    def get_pipeline(self, name: str) -> Optional[PipelineEntry]:
        with self._lock:
            return self._pipelines.get(name)

    def get_all_pipelines(self) -> Dict[str, PipelineEntry]:
        with self._lock:
            return dict(self._pipelines)

    def clear(self):
        with self._lock:
            self._tools.clear()
            self._pipelines.clear()

# Thread-safe global registry instance
registry = SovereignRegistry()

def sovereign_tool(
    name: Optional[str] = None, 
    category: str = "General", 
    requires_env: Optional[List[str]] = None
):
    """
    Decorator to designate a function as an active sovereign tool in the Swarm.
    
    Args:
        name: Optional override for the tool ID (defaults to function name).
        category: Operational swarm module (e.g. 'Strategy', 'Sensory', 'Memory').
        requires_env: Optional list of environment variable names required for enablement.
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        
        # Parse and sanitize docstrings for model readability
        raw_doc = func.__doc__ or "No description provided."
        doc_lines = [line.strip() for line in raw_doc.strip().split("\n")]
        description = "\n".join(doc_lines)
        
        is_async = inspect.iscoroutinefunction(func)
        
        entry = ToolEntry(
            name=tool_name,
            category=category,
            description=description,
            handler=func,
            is_async=is_async,
            requires_env=requires_env or []
        )
        
        registry.register_tool(entry)

        if is_async:
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # Stdout guard around the entire coroutine: any stray print()
                # inside async tool bodies (or their awaited internals) gets
                # routed to stderr so the MCP JSON-RPC channel stays clean.
                with _silence_stdout_during_tool_call():
                    return await func(*args, **kwargs)
        else:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with _silence_stdout_during_tool_call():
                    return func(*args, **kwargs)

        return wrapper
    return decorator
