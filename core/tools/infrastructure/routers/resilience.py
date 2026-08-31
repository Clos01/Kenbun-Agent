"""DSH-06 -- resilience / no-SPOF status for the Observatory.

GET /api/v1/resilience  ->  {
    capabilities: [ {name, blurb, providers:[{name,healthy,primary,...}], spof, healthy_count, total_count} ],
    providers:    the first capability's provider list (back-compat),
    events:       recent failover activity (cross-process, from brain_health/),
    phases:       the DSH journey, plain-English,
    primer:       static vs dynamic composition, condensed,
}
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger("kenbun.routers.resilience")

# Every capability that has been pointed at a Resolver (DSH-06). (label, module, getter).
_RESOLVERS = [
    ("Queen decomposition", "the swarm breaks an objective into atomic tasks",
     "tools.strategy.decomposition", "decomposition_resolver"),
    ("Supervisor senior reviewer", "the local reasoning pass of the commit gate",
     "tools.strategy.senior_reviewer", "senior_reviewer_resolver"),
    ("Two-pass cloud audit", "the strong rung -- Pass 1 / Pass 2 security scan",
     "tools.strategy.senior_reviewer", "audit_scan_resolver"),
    ("Reasoning (misc callers)", "kanban decomposition, prompt rewrites, output scoring, git-push design",
     "tools.strategy.reasoning", "reasoning_resolver"),
]


def _snapshot_capability(label: str, blurb: str, module: str, getter: str) -> Dict[str, Any]:
    import importlib

    try:
        mod = importlib.import_module(module)
        providers = getattr(mod, getter)().snapshot()
        err = None
    except Exception as e:  # noqa: BLE001 -- never 500 the panel over one resolver
        providers, err = [], str(e)[:200]
        logger.warning("resilience: %s snapshot failed: %s", label, e)
    healthy = [p for p in providers if p.get("healthy")]
    return {
        "name": label,
        "blurb": blurb,
        "providers": providers,
        "error": err,
        "healthy_count": len(healthy),
        "total_count": len(providers),
        "spof": len(providers) <= 1,
    }


@router.get("/api/v1/resilience")
async def get_resilience() -> Dict[str, Any]:
    """Read-only status for the Observatory Resilience panel.

    Unauthenticated by design -- same posture as the other Observatory read
    endpoints (health, intelligence): the API binds loopback / Tailscale and a
    separate bind gate requires CONFIG_TOKEN for any public bind. Exposes only
    provider names, health, and the DSH narrative -- no secrets, no user input.
    """
    capabilities: List[Dict[str, Any]] = [
        _snapshot_capability(label, blurb, module, getter)
        for label, blurb, module, getter in _RESOLVERS
    ]

    try:
        from tools.strategy.resolver_events import recent

        events = recent(50)
    except Exception as e:  # noqa: BLE001
        events = []
        logger.warning("resilience: could not read failover events: %s", e)

    try:
        from tools.strategy.dsh_phases import DSH_PHASES, PRIMER, WIRED_CAPABILITY
    except Exception as e:  # noqa: BLE001
        DSH_PHASES, PRIMER, WIRED_CAPABILITY = [], [], {}
        logger.warning("resilience: could not load DSH phase manifest: %s", e)

    first = capabilities[0] if capabilities else {"providers": [], "healthy_count": 0, "total_count": 0}
    return {
        "capability": WIRED_CAPABILITY,
        "capabilities": capabilities,
        # back-compat: a frontend built before the multi-capability change reads these
        "providers": first["providers"],
        "provider_error": first.get("error"),
        "healthy_count": first["healthy_count"],
        "total_count": first["total_count"],
        "spof": any(c["spof"] for c in capabilities),
        "events": events,
        "phases": DSH_PHASES,
        "primer": PRIMER,
    }
