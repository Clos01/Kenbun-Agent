"""
Kenbun Swarm Agents (System 2 & 5)
Sovereign, autonomous cognitive agents powered by the Google Kenbun (AGY) SDK.
Enforces strict sandboxing, HITL gates, and SHA-256 lineage manifests.
"""

# First, ensure google.kenbun imports are mocked if not present in the environment
import agents.mock_sdk

from agents.adapter import AgentToolInterface, HeritageSecurityException
from agents.workflow import WorkflowPhase, SovereignVerificationHook, build_agent_policy
from agents.trace import TraceabilityManifestLogger

__all__ = [
    "AgentToolInterface",
    "HeritageSecurityException",
    "WorkflowPhase",
    "SovereignVerificationHook",
    "build_agent_policy",
    "TraceabilityManifestLogger",
]
