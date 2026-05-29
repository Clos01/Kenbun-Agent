import functools
import inspect
import threading
from typing import Callable, Dict, Any, List, Optional

class ToolEntry:
    """Metadata representing a dynamically registered Kenbun sovereign tool."""
    
    __slots__ = ("name", "category", "description", "handler", "is_async", "requires_env")
    
    def __init__(
        self, 
        name: str, 
        category: str, 
        description: str, 
        handler: Callable, 
        is_async: bool, 
        requires_env: Optional[List[str]] = None
    ):
        self.name = name
        self.category = category
        self.description = description
        self.handler = handler
        self.is_async = is_async
        self.requires_env = requires_env or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "is_async": self.is_async,
            "requires_env": self.requires_env
        }

class SovereignRegistry:
    """Thread-safe global registry for all dynamically discovered Kenbun tools."""
    
    def __init__(self):
        self._tools: Dict[str, ToolEntry] = {}
        self._lock = threading.RLock()

    def register(self, entry: ToolEntry):
        with self._lock:
            self._tools[entry.name] = entry

    def get_tool(self, name: str) -> Optional[ToolEntry]:
        with self._lock:
            return self._tools.get(name)

    def get_all_tools(self) -> Dict[str, ToolEntry]:
        with self._lock:
            return dict(self._tools)

    def clear(self):
        with self._lock:
            self._tools.clear()

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
            requires_env=requires_env
        )
        
        registry.register(entry)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
            
        return wrapper
    return decorator
