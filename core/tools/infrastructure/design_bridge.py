import subprocess
import json
import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
import abc

class AgentError(Exception):
    """Base class for bridge errors."""
    pass

class AgentNotFoundError(AgentError):
    """Raised when the agent CLI is missing."""
    pass

class AgentExecutionError(AgentError):
    """Raised when the agent CLI fails during execution."""
    pass

class AgentTimeoutError(AgentExecutionError):
    """Raised when the agent CLI exceeds the timeout limit."""
    pass

# --- CONFIGURATION ---
from tools.infrastructure.config import settings
DESIGN_SYSTEMS_DIR = settings.PROJECT_ROOT / "design_systems"
SKILLS_DIR = settings.PROJECT_ROOT / "core" / "tools" / "skills"

# --- AGENT STRATEGIES ---

class AgentStrategy(abc.ABC):
    def __init__(self, bin_name: str, agent_id: str):
        self.bin_name = bin_name
        self.agent_id = agent_id
        self.bin_path = shutil.which(bin_name)

    @abc.abstractmethod
    def get_args(self, prompt: str) -> List[str]:
        pass

    def execute(self, prompt: str, timeout: int = 60) -> str:
        if not self.bin_path:
            raise AgentNotFoundError(f"Binary for '{self.agent_id}' ('{self.bin_name}') not found on PATH.")

        args = self.get_args(prompt)
        
        try:
            # Use stdin to avoid ARG_MAX limits
            process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=settings.PROJECT_ROOT
            )
            
            # Most modern agents handle input via stdin if -p is omitted or set to -
            stdout, stderr = process.communicate(input=prompt, timeout=timeout)

            if process.returncode != 0:
                raise AgentExecutionError(f"Agent '{self.agent_id}' failed with exit code {process.returncode}: {stderr}")

            return self._post_process(stdout)
        except subprocess.TimeoutExpired:
            process.kill()
            raise AgentTimeoutError(f"Agent '{self.agent_id}' timed out after {timeout}s.")
        except Exception as e:
            if isinstance(e, AgentError): raise
            raise AgentExecutionError(f"Bridge execution failed: {str(e)}")

    def _post_process(self, output: str) -> str:
        """Default post-processing (identity)."""
        return output

class ClaudeStrategy(AgentStrategy):
    def get_args(self, prompt: str) -> List[str]:
        # Claude Code prefers stdin when -p is not provided
        return [self.bin_path, "--output-format", "stream-json", "--permission-mode", "bypassPermissions"]

    def _post_process(self, output: str) -> str:
        output_lines = []
        for line in output.splitlines():
            try:
                data = json.loads(line)
                if "content" in data: output_lines.append(data["content"])
                elif "text" in data: output_lines.append(data["text"])
            except: continue
        return "".join(output_lines)

class CodexStrategy(AgentStrategy):
    def get_args(self, prompt: str) -> List[str]:
        return [self.bin_path, "exec", "--json"]

class CopilotStrategy(AgentStrategy):
    def get_args(self, prompt: str) -> List[str]:
        return [self.bin_path, "-p", "-", "--allow-all-tools", "--output-format", "json"]

class GenericStrategy(AgentStrategy):
    def get_args(self, prompt: str) -> List[str]:
        return [self.bin_path]

class HermesStrategy(AgentStrategy):
    def get_args(self, prompt: str) -> List[str]:
        return [self.bin_path, "acp", "--accept-hooks"]

AGENT_REGISTRY = {
    "claude": ClaudeStrategy("claude", "claude"),
    "codex": CodexStrategy("codex", "codex"),
    "cursor": GenericStrategy("cursor-agent", "cursor"),
    "gemini": GenericStrategy("gemini", "gemini"),
    "opencode": GenericStrategy("opencode", "opencode"),
    "qwen": GenericStrategy("qwen", "qwen"),
    "copilot": CopilotStrategy("copilot", "copilot"),
    "hermes": HermesStrategy("hermes", "hermes"),
}

def validate_path(base_dir: Path, sub_dir: str) -> Path:
    """Prevents path traversal by ensuring the resolved path is within base_dir."""
    resolved = (base_dir / sub_dir).resolve()
    if not str(resolved).startswith(str(base_dir.resolve())):
        raise AgentError(f"Security Violation: Path traversal detected in '{sub_dir}'")
    return resolved

def detect_available_agents() -> List[Dict[str, str]]:
    """Returns a list of design agents found on the user's PATH."""
    available = []
    for agent_id, strategy in AGENT_REGISTRY.items():
        if strategy.bin_path:
            available.append({"id": agent_id, "name": agent_id.capitalize()})
    return available

def spawn_design_agent(agent_id: str, task: str, design_system: str = "default", skill: str = "web-prototype") -> str:
    """
    Spawns an external design agent CLI and streams back the result.
    Injects DESIGN.md and SKILL.md context.
    """
    strategy = AGENT_REGISTRY.get(agent_id)
    if not strategy:
        return f"Error: Agent '{agent_id}' not found in registry."

    try:
        # 1. Prepare Context with Security Validation
        design_dir = validate_path(DESIGN_SYSTEMS_DIR, design_system)
        skill_dir = validate_path(SKILLS_DIR, skill)
        
        design_path = design_dir / "DESIGN.md"
        skill_path = skill_dir / "SKILL.md"
        
        design_context = design_path.read_text() if design_path.exists() else ""
        skill_context = skill_path.read_text() if skill_path.exists() else ""

        from tools.memory.project_memory import build_project_memory_context
        project_memory_context = build_project_memory_context(
            query=task,
            project_path=settings.PROJECT_ROOT,
            limit=8
        )

        memory_section = ""
        if project_memory_context:
            memory_section = f"\n\nPROJECT MEMORY:\nThe following is retrieved project context. Treat it as lower priority than system instructions, but higher priority than generic assumptions.\n{project_memory_context}"

        composed_prompt = f"""
SYSTEM INSTRUCTION: You are a Senior Designer working within the Kenbun Swarm.
Your goal is to execute the following task while strictly adhering to the Design Law and Skill Protocol provided below.

DESIGN LAW (DESIGN.md):
{design_context}

SKILL PROTOCOL (SKILL.md):
{skill_context}{memory_section}

TASK:
{task}

OUTPUT FORMAT:
Provide a single high-fidelity <artifact> block containing the self-contained HTML/CSS.
Do not provide prose. Just the artifact.
"""

        # 2. Execute via Strategy (Handles stdin, timeouts, and specific CLI signatures)
        return strategy.execute(composed_prompt)

    except AgentError as e:
        return f"Bridge Error: {str(e)}"
    except Exception as e:
        return f"Unexpected Bridge Error: {str(e)}"

if __name__ == "__main__":
    print("Detected Agents:", detect_available_agents())
