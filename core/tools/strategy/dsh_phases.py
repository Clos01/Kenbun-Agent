"""DSH ("DeepSeek-Harness adoption") journey -- the plain-English version.

This is narrative content for the Observatory's Resilience panel. It changes
rarely; keep the blurbs informal and jargon-light.
"""
from __future__ import annotations

from typing import Dict, List

# status: "done" | "in_progress" | "todo"
DSH_PHASES: List[Dict[str, str]] = [
    {
        "id": "DSH-01",
        "title": "An undo button for the tool registry",
        "status": "done",
        "commit": "8297614",
        "blurb": (
            "Adding a tool to the running swarm used to be permanent -- you could bolt "
            "something on but never cleanly take it off without a restart. Now every "
            "registration hands back a disposer that removes exactly what it added, and "
            "the live MCP tool list follows along. No restart, no leftovers."
        ),
    },
    {
        "id": "DSH-02",
        "title": "Shell / files / web became swappable",
        "status": "done",
        "commit": "26fa15d",
        "blurb": (
            "Split each capability into three parts: what it promises, who provides it, "
            "and who uses it. Running a shell command now goes through a seam, so a "
            "sandboxed provider can stand in for the local one without touching callers."
        ),
    },
    {
        "id": "DSH-03",
        "title": "One honest record of what the model saw",
        "status": "done",
        "commit": "59f5449",
        "blurb": (
            "The session event log is the single source of truth for model context -- if "
            "the model was shown something, it's in the log. A guard raises if anything "
            "reaches the model without being written down first."
        ),
    },
    {
        "id": "DSH-04",
        "title": "One way to hand work to a sub-agent",
        "status": "done",
        "commit": "00e8cfa",
        "blurb": (
            "One interface for spawning helpers, with pluggable drivers behind it "
            "(in-process swarm, or the external Claude Code CLI). When one driver reports "
            "'unavailable', the seam walks to the next -- this is where the 429 quota "
            "failure first got a real fallback."
        ),
    },
    {
        "id": "DSH-05",
        "title": "Mount a new tool while the swarm is running",
        "status": "done",
        "commit": "e680f35",
        "blurb": (
            "Hand the swarm a freshly-built tool, run a smoke test on it, and keep it only "
            "if it passes -- otherwise it's auto-reverted and never surfaces. The other "
            "half: lifecycle hooks -- an operator can drop a hooks.json next to the swarm "
            "and a shell command of theirs runs before a tool does, free to block it, "
            "rewrite its input, or add a note. Same protocol Claude Code uses. Together: "
            "self-modification and operator control, both without a restart."
        ),
    },
    {
        "id": "DSH-06",
        "title": "No single point of failure, anywhere",
        "status": "done",
        "commit": "578632d",
        "blurb": (
            "A capability with exactly one provider is a single fixed choice in a "
            "load-bearing spot -- when it's down, you're just down. The fix: every "
            "load-bearing LLM call gets 2+ providers and a resolver that DEMOTES a "
            "failing one (for a cooldown) instead of stopping. Wired: the swarm "
            "Queen's decomposition, the supervisor's senior reviewer, the two-pass "
            "audit, the misc reasoning callers, and memory reads. Kill any one "
            "provider and the swarm keeps working."
        ),
    },
    {
        "id": "DSH-07",
        "title": "LLM Gateway health-aware failover",
        "status": "done",
        "commit": "578632d",
        "blurb": (
            "The general LLM gateway (call_llm_gateway) now routes through a "
            "CapabilityResolver with auto-cooldown demotion and resilience telemetry. "
            "If the primary endpoint is down or hits quota, the swarm falls back "
            "seamlessly without repeated timeout stalls on subsequent turns."
        ),
    },
    {
        "id": "DSH-08",
        "title": "Spatiotemporal Reactive Coeffects & Context Engine",
        "status": "done",
        "commit": "e50330f",
        "blurb": (
            "A pure OOP spatiotemporal context engine (ContextEngine). Capabilities declare "
            "what they require via reactive coeffects (inject); when a provider appears, updates, "
            "or fails, the context engine notifies and refreshes dependent fibers automatically. "
            "Revertible effects clean up LIFO on teardown. Zero hardcoding, cycle-safe."
        ),
    },
    {
        "id": "DSH-09",
        "title": "Automated Session Replay & Regression Eval Gate",
        "status": "done",
        "commit": "HEAD",
        "blurb": (
            "Keyless deterministic session playback and regression gating harness "
            "mirroring DeepSeek-Harness test protocol. Replays recorded conversational "
            "turns, validates the 'model-visible <=> logged' invariant at each step, "
            "detects unlogged context injections, and scores replay fidelity with "
            "zero paid API key dependency."
        ),
    },
    {
        "id": "DSH-10",
        "title": "Unified Memory Capability Seam (Definition/Provider/Consumer)",
        "status": "done",
        "commit": "HEAD",
        "blurb": (
            "A unified memory capability seam abstracting SQLite, ChromaDB, and Honcho. "
            "Query results and memory embeddings use immutable records (MemoryRecord, "
            "MemoryEmbedding) with health-aware automatic failover to local SQLite "
            "fallback when remote stores are unreachable."
        ),
    },
]

# The capabilities wired onto a Resolver so far (shown in the panel).
WIRED_CAPABILITY: Dict[str, str] = {
    "name": "load-bearing LLM calls",
    "where": "decomposition, senior review, two-pass audit, misc reasoning callers, general LLM gateway",
    "was": "one hardcoded provider each; a 429 or a dead box killed the feature",
    "now": "each behind a health-aware Resolver, auto-recovering",
}

# Condensed composability primer for the panel footer.
PRIMER = [
    {
        "term": "Static composition",
        "line": "Decided once, at build time. Changing it means editing code and restarting -- "
                "and a restart wipes every bit of in-memory state.",
    },
    {
        "term": "Dynamic composition",
        "line": "Swapped while running, and undoable. Add a piece, test it, roll it back if a "
                "guard fails -- the swarm never stops.",
    },
    {
        "term": "The trap",
        "line": "Depending on one API key / one router / one model is static composition in "
                "disguise. A resolver with real fallbacks is how you make it dynamic.",
    },
]
