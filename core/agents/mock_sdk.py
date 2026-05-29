"""
Mock implementation of google.kenbun for development and testing environment compatibility.
Automatically registers itself in sys.modules if the real SDK is not present in the runtime.
"""
import sys
from types import ModuleType
from typing import Any, List, Optional, Callable, Dict

class HookResult:
    def __init__(self, allow: bool, error_message: Optional[str] = None):
        self.allow = allow
        self.error_message = error_message

class ToolCall:
    def __init__(self, id: str, name: str, arguments: Optional[Dict[str, Any]] = None):
        self.id = id
        self.name = name
        self.arguments = arguments or {}

class AskQuestionInteractionSpec:
    pass

class QuestionHookResult:
    def __init__(self, responses: Optional[List[str]] = None):
        self.responses = responses or []

# Attempt real import first
try:
    import google.kenbun
except ModuleNotFoundError:
    # Build mock google.kenbun module hierarchy
    if "google" not in sys.modules:
        google_mod = ModuleType("google")
        sys.modules["google"] = google_mod
    else:
        google_mod = sys.modules["google"]
        
    # Create 'google.kenbun'
    kenbun_mod = ModuleType("google.kenbun")
    
    # Create 'google.kenbun.types'
    types_mod = ModuleType("google.kenbun.types")
    types_mod.HookResult = HookResult
    types_mod.ToolCall = ToolCall
    types_mod.AskQuestionInteractionSpec = AskQuestionInteractionSpec
    types_mod.QuestionHookResult = QuestionHookResult
    
    # Assign attributes
    kenbun_mod.types = types_mod
    
    # Register in sys.modules
    sys.modules["google.kenbun"] = kenbun_mod
    sys.modules["google.kenbun.types"] = types_mod
    
    # Create 'google.kenbun.hooks'
    hooks_mod = ModuleType("google.kenbun.hooks")
    
    class HooksRegistry:
        def on_session_start(self, func): return func
        def on_session_end(self, func): return func
        def pre_turn(self, func): return func
        def post_turn(self, func): return func
        def pre_tool_call_decide(self, func): return func
        def post_tool_call(self, func): return func
        def on_tool_error(self, func): return func
        def on_interaction(self, func): return func
        def on_compaction(self, func): return func
        
    hooks_instance = HooksRegistry()
    hooks_mod.hooks = hooks_instance
    
    # Create 'google.kenbun.hooks.policy'
    class MockPolicy:
        def __init__(self, type_name: str, target: str = "*", when: Optional[Callable] = None, name: Optional[str] = None):
            self.type_name = type_name
            self.target = target
            self.when = when
            self.name = name
            
        def __repr__(self):
            return f"MockPolicy({self.type_name}, {self.target}, name={self.name})"

    policy_mod = ModuleType("google.kenbun.hooks.policy")
    policy_mod.workspace_only = lambda workspaces: MockPolicy("workspace_only", str(workspaces))
    policy_mod.deny = lambda target, when=None, name=None: MockPolicy("deny", target, when, name)
    policy_mod.allow = lambda target, when=None, name=None: MockPolicy("allow", target, when, name)
    policy_mod.deny_all = lambda: MockPolicy("deny_all")
    policy_mod.allow_all = lambda: MockPolicy("allow_all")
    policy_mod.confirm_run_command = lambda handler=None: MockPolicy("confirm_run_command")
    
    # Assign attributes
    hooks_mod.policy = policy_mod
    kenbun_mod.hooks = hooks_mod
    
    # Register hooks modules in sys.modules
    sys.modules["google.kenbun.hooks"] = hooks_mod
    sys.modules["google.kenbun.hooks.policy"] = policy_mod
