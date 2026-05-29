"""
Claude Code Sub-Agent Bridge
============================
Dispatches complex, multi-file coding tasks to Claude Code CLI.
Kenbun acts as the CTO brain; Claude Code is the execution specialist.

Usage:
    from tools.execution.claude_code_agent import claude_code_agent
    result = claude_code_agent.dispatch("Refactor guardrails.py to use a plugin pattern")
"""
import subprocess
import json
import time
import shutil
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from tools.utils.path_utils import get_project_root

logger = logging.getLogger(__name__)

PROJECT_ROOT = get_project_root()
LOG_FILE = PROJECT_ROOT / "brain_health" / "claude_code_log.jsonl"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

@dataclass
class ClaudeCodeResult:
    success: bool
    output: str
    task: str
    duration_seconds: float
    model: str = "claude-code"
    error: Optional[str] = None


class ClaudeCodeAgent:
    """
    Sub-Agent that wraps the Claude Code CLI.
    Activated by DecisionRouter when task complexity exceeds threshold.
    """

    # Keywords that trigger Claude Code dispatch
    DISPATCH_KEYWORDS = [
        "refactor", "implement", "build feature", "generate tests",
        "architect module", "write module", "create component",
        "full implementation", "multi-file", "overhaul", "migrate"
    ]

    def __init__(self, timeout: int = 120):
        self.timeout = timeout
        self._cli_path = shutil.which("claude")

    def is_available(self) -> bool:
        """Check if Claude Code CLI is installed and accessible."""
        return self._cli_path is not None

    def should_dispatch(self, objective: str) -> bool:
        """Returns True if the objective warrants Claude Code dispatch."""
        lower = objective.lower()
        return any(kw in lower for kw in self.DISPATCH_KEYWORDS)

    def dispatch(
        self,
        task: str,
        working_dir: Optional[Path] = None,
        context_files: Optional[list] = None,
        print_output: bool = True
    ) -> ClaudeCodeResult:
        """
        Dispatches a coding task to Claude Code CLI.

        Args:
            task: The natural language task description.
            working_dir: Directory to run Claude Code in (defaults to project root).
            context_files: Optional list of file paths to pass as context.
            print_output: Whether to stream output to console.
        """
        if not self.is_available():
            return ClaudeCodeResult(
                success=False,
                output="",
                task=task,
                duration_seconds=0,
                error="Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
            )

        cwd = working_dir or PROJECT_ROOT
        start = time.time()

        # Build context prefix if files provided
        context_prefix = ""
        if context_files:
            context_prefix = "Context files:\n"
            for f in context_files:
                context_prefix += f"- {f}\n"
            context_prefix += "\n"

        full_prompt = f"{context_prefix}{task}"

        logger.info(f"🤖 Dispatching to Claude Code: {task[:80]}...")

        try:
            result = subprocess.run(
                [self._cli_path, "-p", full_prompt, "--no-interactive"],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=self.timeout
            )

            duration = time.time() - start
            success = result.returncode == 0
            output = result.stdout or result.stderr

            if print_output:
                print(f"\n{'='*60}")
                print(f"🤖 Claude Code Result ({duration:.1f}s):")
                print(f"{'='*60}")
                print(output)
                print(f"{'='*60}\n")

            # Log the interaction
            self._log(task, output, success, duration, result.returncode)

            return ClaudeCodeResult(
                success=success,
                output=output,
                task=task,
                duration_seconds=duration,
                error=None if success else f"Exit code: {result.returncode}"
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start
            err = f"Claude Code timed out after {self.timeout}s"
            self._log(task, "", False, duration, -1, err)
            return ClaudeCodeResult(
                success=False, output="", task=task,
                duration_seconds=duration, error=err
            )
        except Exception as e:
            duration = time.time() - start
            self._log(task, "", False, duration, -1, str(e))
            return ClaudeCodeResult(
                success=False, output="", task=task,
                duration_seconds=duration, error=str(e)
            )

    def _log(self, task, output, success, duration, code, error=None):
        """Append interaction to JSONL log for Hivemind indexing."""
        entry = {
            "timestamp": time.time(),
            "task": task[:500],
            "success": success,
            "duration_seconds": round(duration, 2),
            "exit_code": code,
            "output_length": len(output),
            "error": error
        }
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")


# Singleton
claude_code_agent = ClaudeCodeAgent()


if __name__ == "__main__":
    # Test harness
    print(f"Claude Code available: {claude_code_agent.is_available()}")
    print(f"Should dispatch 'refactor the guardrails': {claude_code_agent.should_dispatch('refactor the guardrails')}")
    print(f"Should dispatch 'fix a small bug': {claude_code_agent.should_dispatch('fix a small bug')}")
