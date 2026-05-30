import functools
import hashlib
import json
import time
from pathlib import Path
from tools.infrastructure.sovereign_verifier import audit_function, SovereignBreach
from tools.infrastructure.config import settings

REGISTRY_PATH = settings.BRAIN_HEALTH_DIR / "sovereign_registry.json"

def _update_registry(func_name: str, module: str, is_clean: bool, breaches: list, signature: str):
    """Updates the persistent Sovereign Registry."""
    try:
        data = {}
        if REGISTRY_PATH.exists():
            with open(REGISTRY_PATH, "r") as f:
                data = json.load(f)
        
        key = f"{module}.{func_name}"
        data[key] = {
            "timestamp": time.time(),
            "is_clean": is_clean,
            "signature": signature,
            "breaches": breaches if not is_clean else []
        }
        
        with open(REGISTRY_PATH, "w") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass

def sovereign_logic(strict: bool = False):
    """
    Decorator to enforce architectural sovereignty on a function.
    
    Args:
        strict: If True, raises SovereignBreach on any structural violation.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 1. Generate Signature
            import inspect
            source = inspect.getsource(func)
            signature = hashlib.sha256(source.encode()).hexdigest()
            
            # 2. Audit
            is_clean, breaches = audit_function(func)
            
            # 3. Register
            _update_registry(func.__name__, func.__module__, is_clean, breaches, signature)
            
            # 4. Enforce
            if strict and not is_clean:
                error_msg = f"SOVEREIGNTY BREACH in {func.__name__}: " + " | ".join([b['message'] for b in breaches])
                raise SovereignBreach(error_msg)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def grounded_data(node_ref: str = None):
    """
    Ensures the data being processed originates from a trusted 'Grounded' source.
    (Placeholder for future Data-Flow provenance)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Future logic: Verify kwargs against the TaintTracker
            return func(*args, **kwargs)
        return wrapper
    return decorator
