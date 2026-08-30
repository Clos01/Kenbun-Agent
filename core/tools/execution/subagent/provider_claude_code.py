"""subagent capability -- Claude Code Service Provider (DSH-04).

Wraps the existing `tools.execution.claude_code_agent.ClaudeCodeAgent`: hands the
task to an external `claude` CLI process. Reports unavailable (not crashing) when
the CLI is not installed.
"""
from __future__ import annotations

import logging
from typing import Optional

from .definition import SubagentResult, task_label

logger = logging.getLogger("kenbun.subagent")


class ClaudeCodeSubagentProvider:
    name = "claude-code"

    def run(
        self,
        task: str,
        *,
        context: str = "",
        cwd: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> SubagentResult:
        from pathlib import Path

        from tools.execution.claude_code_agent import ClaudeCodeAgent

        label = task_label(task)
        agent = ClaudeCodeAgent(timeout=int(timeout) if timeout else 120)
        if not agent.is_available():
            logger.warning("subagent[claude-code]: CLI not installed; task %r not run", label)
            return SubagentResult(
                task_label=label, ok=False, output="", provider=self.name,
                error="claude CLI not found (npm i -g @anthropic-ai/claude-code)",
            )

        full = f"{context}\n\n{task}" if context else task
        logger.info("subagent[claude-code]: dispatching %r", label)
        res = agent.dispatch(
            full, working_dir=Path(cwd) if cwd else None, print_output=False,
        )
        return SubagentResult(
            task_label=label, ok=res.success, output=res.output, provider=self.name,
            duration_seconds=res.duration_seconds, error=res.error,
        )
