"""subagent capability -- in-process swarm Service Provider (DSH-04).

Wraps `tools.infrastructure.orchestrator.spawn_swarm` -- the Queen-decomposes /
workers-execute path that `delegate_task` uses today. `spawn_swarm` is async and
its decomposition step calls Gemini, so this provider:

  * bridges async -> sync (its own loop, or a worker thread if one is running)
  * surfaces a Gemini quota failure as `ok=False` with a `error` the seam can act
    on (fall back to another provider) rather than a raw 429 string
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from .definition import SubagentResult, task_label

logger = logging.getLogger("kenbun.subagent")

# Substrings that mean "this provider cannot run right now, try another".
_UNAVAILABLE_MARKERS = ("RESOURCE_EXHAUSTED", "quota", "429", "decomposition failed")


class InProcessSwarmSubagentProvider:
    name = "in-process-swarm"

    def run(
        self,
        task: str,
        *,
        context: str = "",
        cwd: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> SubagentResult:
        from tools.infrastructure.config import settings
        from tools.infrastructure.orchestrator import build_pipeline_tools, spawn_swarm

        label = task_label(task)
        prompt = f"OBJECTIVE: {task}\n\nCONTEXT:\n{context}" if context else f"OBJECTIVE: {task}"
        project_path = cwd or str(settings.PROJECT_ROOT)
        tools = build_pipeline_tools(project_path)

        logger.info("subagent[in-process-swarm]: spawning for %r", label)
        start = time.monotonic()
        try:
            output = _run_sync(spawn_swarm(prompt, tools, project_path=project_path))
        except Exception as e:  # spawn_swarm mostly returns error strings, but be safe
            output = f"decomposition failed: {e}"

        duration = time.monotonic() - start
        unavailable = any(m.lower() in output.lower() for m in _UNAVAILABLE_MARKERS)
        ok = not unavailable and not output.lstrip().startswith("❌")  # leading ❌
        return SubagentResult(
            task_label=label, ok=ok, output=output, provider=self.name,
            duration_seconds=duration,
            error=("provider unavailable (quota / decomposition)" if unavailable else
                   (None if ok else "swarm returned an error")),
            meta={"unavailable": unavailable},
        )


def _run_sync(coro):
    """Run an awaitable from a synchronous caller. Uses a fresh loop; if one is
    already running on this thread, runs the coroutine on a worker thread."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro)).result()
