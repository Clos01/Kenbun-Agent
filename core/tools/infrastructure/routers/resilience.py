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

import asyncio
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
    ("LLM gateway", "general model requests -- primary, fallback, and native fallbacks",
     "tools.utils.llm_router", "llm_gateway_resolver"),
]


def _snapshot_memory() -> Dict[str, Any]:
    """Snapshots the DSH-10 Unified Memory Seam (Honcho, Chroma, SQLite)."""
    from tools.strategy.memory_seam import UnifiedMemorySeam
    seam = UnifiedMemorySeam()
    providers: List[Dict[str, Any]] = []
    for p in seam._providers:
        healthy = False
        try:
            healthy = p.is_healthy()
        except Exception:
            healthy = False
        providers.append({
            "name": p.name,
            "healthy": healthy,
            "primary": p.priority == 90,
            "priority": p.priority,
            "fail_count": 0 if healthy else 1,
            "cooldown_remaining_s": 0.0,
        })
    healthy_providers = [p for p in providers if p["healthy"]]
    return {
        "name": "DSH-10 Unified Memory Seam",
        "blurb": "System 3 concepts & embeddings -- Honcho (remote), Chroma (vectors), local SQLite fallback",
        "providers": providers,
        "error": None if any(p["healthy"] for p in providers) else "All memory providers unreachable",
        "healthy_count": len(healthy_providers),
        "total_count": len(providers),
        "spof": len(healthy_providers) <= 1 and len(providers) > 1,
    }


def _chroma_ok() -> bool:
    from tools.memory.honcho_connect import get_chroma_client

    client = get_chroma_client()
    if client is None:
        return False
    try:
        client.heartbeat()
        return True
    except Exception:
        return False


def _honcho_ok() -> bool:
    from tools.memory.honcho_connect import is_honcho_ready

    return is_honcho_ready()


def _snapshot_database() -> Dict[str, Any]:
    """Snapshots the Bayesian intelligence database state: remote PostgreSQL -> local SQLite fallback."""
    from tools.utils.bayesian import get_db_status

    status = get_db_status()
    providers = [
        {
            "name": "postgres",
            "healthy": status["primary_reachable"],
            "primary": True,
            "fail_count": 1 if status["fallback_active"] else 0,
            "cooldown_remaining_s": 0.0,
        },
        {
            "name": "sqlite_local",
            "healthy": True,
            "primary": False,
            "fail_count": 0,
            "cooldown_remaining_s": 0.0,
        },
    ]
    healthy = [p for p in providers if p["healthy"]]
    return {
        "name": "Database & Bayesian intelligence",
        "blurb": "weights & synaptic tuning -- remote PostgreSQL, then local SQLite fallback",
        "providers": providers,
        "error": None if status["primary_reachable"] else "Remote PostgreSQL unreachable; using SQLite fallback",
        "healthy_count": len(healthy),
        "total_count": len(providers),
        "spof": len(healthy) <= 1 and len(providers) > 1,
    }


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
        # blocking network pings -- off the event loop, fail fast if a store hangs
        capabilities.append(await asyncio.wait_for(asyncio.to_thread(_snapshot_memory), timeout=3.0))
    except Exception as e:  # noqa: BLE001 -- incl. TimeoutError; the panel drops the row
        logger.warning("resilience: memory snapshot skipped (%s)", type(e).__name__)

    try:
        capabilities.append(await asyncio.wait_for(asyncio.to_thread(_snapshot_database), timeout=3.5))
    except Exception as e:  # noqa: BLE001
        logger.warning("resilience: database snapshot skipped (%s)", type(e).__name__)

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


@router.get("/api/v1/replay/eval")
async def get_replay_eval(session_id: Optional[str] = None, strict: bool = False) -> Dict[str, Any]:
    """Runs DSH-09 session replay evaluation for the Observatory.

    Evaluates the specified session or a representative session turn stream,
    verifying model-visible <=> logged invariant and reporting fidelity score.
    """
    from tools.strategy.session_replay import SessionReplayEngine
    from tools.memory.session_log import SessionEvent

    engine = SessionReplayEngine(strict=strict)
    if session_id:
        report = engine.evaluate_session(session_id)
    else:
        # Default representative baseline verification
        sample_events = [
            SessionEvent(seq=1, kind="system_prompt", role="system", content="You are Kenbun, the CTO agent."),
            SessionEvent(seq=2, kind="user_message", role="user", content="Check memory seam and replay gate."),
            SessionEvent(seq=3, kind="assistant_message", role="assistant", content="Running verification suite."),
            SessionEvent(seq=4, kind="tool_result", role="tool", content="OK", tool_name="get_db_status"),
            SessionEvent(seq=5, kind="assistant_message", role="assistant", content="All invariants verified."),
        ]
        report = engine.evaluate_session(sample_events, session_id="live_observatory_eval")

    badge = "PASSED" if report.passed else "REGRESSION_DETECTED"
    res = report.to_dict()
    res["badge"] = badge
    return res
