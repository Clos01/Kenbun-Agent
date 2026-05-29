"""
Workflow management and lifecycle hooks for Kenbun Swarm Agents.
Enforces lock-step progression of the Kenbun Workflow via the AGY SDK.
"""

from enum import Enum
import sys
from typing import Callable, Optional, Dict, Any, List

# Ensure google.kenbun imports are mocked if not present in the environment
import agents.mock_sdk

from google.kenbun import types
from google.kenbun.hooks import hooks, policy

class WorkflowPhase(str, Enum):
    """Sovereign Kenbun Workflow Phases."""
    RESEARCH = "PHASE_RESEARCH"
    PLANNING = "PHASE_PLANNING"
    AWAITING_APPROVAL = "PHASE_AWAITING_APPROVAL"
    EXECUTION = "PHASE_EXECUTION"
    VERIFICATION = "PHASE_VERIFICATION"
    COMPLETED = "PHASE_COMPLETED"

class SovereignVerificationHook:
    """
    Sovereign lifecycle hooks container for AGY Swarm Agents.
    Maintains workflow integrity, linting checks, and HITL authorization states.
    """
    def __init__(self, check_lint_fn: Callable[[], tuple[bool, str]]):
        self.phase = WorkflowPhase.RESEARCH
        self.check_lint = check_lint_fn
        self.user_approval_granted = False

    def set_phase(self, new_phase: WorkflowPhase):
        """Transition workflow phase with log outputs."""
        print(f"🔄 Swarm Agent Phase Transition: {self.phase.value} ➔ {new_phase.value}")
        self.phase = new_phase

    async def pre_turn_handler(self, data: str) -> types.HookResult:
        """Runs before a conversation turn starts to verify state gates."""
        if self.phase == WorkflowPhase.AWAITING_APPROVAL and not self.user_approval_granted:
            print("⚠️ Swarm Execution Halted: Awaiting manual review of implementation_plan.md.")
            return types.HookResult(allow=False, error_message="User approval required. Please approve the plan first.")
        return types.HookResult(allow=True)

    async def post_turn_handler(self, response_text: str):
        """Runs after a conversation turn finishes to evaluate SVE logic."""
        if self.phase == WorkflowPhase.EXECUTION:
            # Trigger SVE Verification phase
            self.set_phase(WorkflowPhase.VERIFICATION)
            
            # Execute background diagnostics
            success, diagnostic_output = self.check_lint()
            if not success:
                print("❌ SVE Diagnostic Failure detected. Reverting agent to Execution phase.")
                # We will instruct the model of its failure in the next turn
                self.set_phase(WorkflowPhase.EXECUTION)
            else:
                print("✅ SVE Verification Successful. Core stability guaranteed.")
                self.set_phase(WorkflowPhase.COMPLETED)

    async def pre_tool_call_handler(self, tool_call: types.ToolCall) -> types.HookResult:
        """
        Enforces execution safety boundaries and capability-based phase permissions.
        Implements async-safe HITL confirmation gates to protect the event loop.
        """
        import asyncio
        tool_name = tool_call.name
        args = tool_call.arguments or {}
        
        # Capability Mapping (DANGEROUS_TOOLS: actions modifying state or executing shell/binary payloads)
        DANGEROUS_TOOLS = {"edit_file", "run_command", "create_file", "delete_file"}
        
        # 1. Deny state modification capabilities during Research & Planning phases
        if self.phase in [WorkflowPhase.RESEARCH, WorkflowPhase.PLANNING]:
            if tool_name in DANGEROUS_TOOLS:
                # Except creating the design document / implementation plan in planning phase
                if self.phase == WorkflowPhase.PLANNING and tool_name == "create_file":
                    target = args.get("TargetFile", "")
                    if target.endswith("implementation_plan.md"):
                        return types.HookResult(allow=True)
                
                # Emit structured log for compliance audits (HERITAGE_OBS_001)
                print(f"[HERITAGE_SEC_AUDIT_FAIL] [Error Code: HERITAGE_SEC_002] Blocked attempt to call stateful tool '{tool_name}' during read-only phase '{self.phase.value}'")
                return types.HookResult(
                    allow=False, 
                    error_message=f"Permission Denied: Cannot modify code or run commands in {self.phase.value}."
                )
        
        # 2. Trigger HITL confirmation gate on active state modification operations during Execution
        if self.phase == WorkflowPhase.EXECUTION and tool_name in DANGEROUS_TOOLS:
            print(f"\n📢 HITL Security Gate: Agent requested execution of stateful tool '{tool_name}' with arguments: {args}")
            
            # Non-blocking async input execution in thread pool (HERITAGE_ASYNC_001)
            try:
                confirm = await asyncio.to_thread(input, "Authorize tool execution? [y/N]: ")
                confirm = confirm.strip().lower()
            except Exception as e:
                print(f"❌ HITL Input Exception: {e}")
                confirm = "n"
                
            if confirm not in ["y", "yes"]:
                # Emit structured log for denied administrative actions (HERITAGE_OBS_001)
                print(f"[HERITAGE_SEC_AUDIT_FAIL] [Error Code: HERITAGE_SEC_002] Tool '{tool_name}' execution denied by system administrator.")
                return types.HookResult(allow=False, error_message="Tool execution rejected by the system administrator.")
            print("🚀 Tool Execution Approved.")
            
        return types.HookResult(allow=True)

def build_agent_policy(workflow_hook: SovereignVerificationHook) -> List[Any]:
    """
    Generates declarative safety policies tailored to the active workflow phase.
    Provides argument-level predicates for fine-grained safety.
    """
    policies = []
    
    # Restrict file tools to authorized workspace paths
    from tools.infrastructure.config import settings
    policies.append(policy.workspace_only([settings.PROJECT_ROOT]))
    
    # Argument Predicate: Reject dangerous execution strings instantly
    policies.append(policy.deny(
        "run_command",
        when=lambda args: any(tok in args.get("CommandLine", "") for tok in ["rm ", "sudo ", "chmod"]),
        name="deny_destructive_commands"
    ))
    
    # Deny shell execution entirely unless explicitly in the Execution/Verification phases
    policies.append(policy.deny(
        "run_command",
        when=lambda args: workflow_hook.phase not in [WorkflowPhase.EXECUTION, WorkflowPhase.VERIFICATION],
        name="restrict_commands_by_phase"
    ))
    
    return policies
