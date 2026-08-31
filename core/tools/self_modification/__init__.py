"""Self-modification primitives (DSH-05).

The payoff of DSH-01: `registry.register_tool` returns a disposer, so a tool can
be added to a *live* process and cleanly removed. `guarded_mount` adds the safety
valve -- run a guard against the freshly-mounted tool and auto-revert on failure
-- so `agent_self_improve` can try a generated tool without a restart and without
risking the running swarm.
"""
from .compile_source import UnsafeSourceError, compile_tool_source
from .hot_mount import MountResult, guarded_mount, guarded_mount_source, hot_mount_tool

__all__ = [
    "hot_mount_tool", "guarded_mount", "guarded_mount_source", "MountResult",
    "compile_tool_source", "UnsafeSourceError",
]
