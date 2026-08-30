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
        "commit": "ca6858f",
        "blurb": (
            "Hand the swarm a freshly-built tool, run a smoke test on it, and keep it only "
            "if it passes -- otherwise it's auto-reverted and never surfaces. The capstone: "
            "self-modification without a restart."
        ),
    },
    {
        "id": "DSH-06",
        "title": "No single point of failure, anywhere",
        "status": "in_progress",
        "commit": "6cd3785",
        "blurb": (
            "A capability with exactly one provider is a single fixed choice in a "
            "load-bearing spot -- when it's down, you're just down. The fix: every seam "
            "gets 2+ providers and a resolver that DEMOTES a failing one (for a cooldown) "
            "instead of stopping. First seam wired: the swarm Queen's task decomposition. "
            "Kill Gemini and the swarm still plans its work."
        ),
    },
]

# The one capability wired onto the resolver so far.
WIRED_CAPABILITY: Dict[str, str] = {
    "name": "Queen task decomposition",
    "where": "spawn_swarm() -- breaks an objective into atomic tasks",
    "was": "one direct call to Gemini; a 429 meant no swarm at all",
    "now": "gemini -> deepseek -> local, health-aware, auto-recovering",
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
