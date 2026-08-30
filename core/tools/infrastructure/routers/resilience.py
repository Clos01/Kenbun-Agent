"""DSH-06 -- resilience / no-SPOF status for the Observatory.

GET /api/v1/resilience  ->  {
    capability:  the one seam wired onto the resolver so far,
    providers:   live health of each decomposition provider (configured order),
    events:      recent failover activity (cross-process, from brain_health/),
    phases:      the DSH journey, plain-English,
    primer:      static vs dynamic composition, condensed,
}
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger("kenbun.routers.resilience")


@router.get("/api/v1/resilience")
async def get_resilience() -> Dict[str, Any]:
    """Read-only status for the Observatory Resilience panel.

    Unauthenticated by design -- same posture as the other Observatory read
    endpoints (health, intelligence): the API binds loopback / Tailscale and a
    separate bind gate requires CONFIG_TOKEN for any public bind. Exposes only
    provider names, health, and the DSH narrative -- no secrets, no user input.
    """
    providers = []
    provider_error = None
    try:
        from tools.strategy.decomposition import decomposition_resolver

        providers = decomposition_resolver().snapshot()
    except Exception as e:  # noqa: BLE001 -- never 500 the panel over a resolver import
        provider_error = str(e)[:200]
        logger.warning("resilience: could not read resolver snapshot: %s", e)

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

    healthy = [p for p in providers if p.get("healthy")]
    return {
        "capability": WIRED_CAPABILITY,
        "providers": providers,
        "provider_error": provider_error,
        "healthy_count": len(healthy),
        "total_count": len(providers),
        "spof": len(providers) <= 1,
        "events": events,
        "phases": DSH_PHASES,
        "primer": PRIMER,
    }
