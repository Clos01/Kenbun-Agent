import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Union
from tools.registry import sovereign_tool
from tools.infrastructure.config import settings
from tools.infrastructure.orchestrator import spawn_swarm

logger = logging.getLogger("delegation_tool")

def get_tools_for_toolsets(toolsets: Any, is_orchestrator: bool = False) -> Dict[str, Any]:
    from tools.audit.gemini_reviewer import gemini_code_review, gemini_research
    from tools.memory.repo_mapper import scan_repo
    from tools.utils.error_memory import remember_fix, recall_fix
    from tools.utils.backtracker import save_checkpoint, restore_checkpoint
    from tools.execution.e2b_runner import run_code_safely
    from tools.audit.consult_architect import consult_brain
    from tools.audit.linter_autofix import autofix_linter
    from tools.infrastructure.server import write_website_content
    
    def _local_view_file(AbsolutePath: str) -> str:
        path = os.path.abspath(AbsolutePath)
        if not path.startswith(settings.PROJECT_ROOT):
            raise PermissionError("Access denied: Path is outside the PROJECT_ROOT.")
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    # Tool mapping grouped by category
    all_tool_mappings = {
        "scan_repo": ("file", scan_repo),
        "view_file": ("file", _local_view_file),
        "consult_hivemind": ("file", consult_brain),
        "review_code_with_gemini": ("file", gemini_code_review),
        
        "research_with_gemini": ("web", gemini_research),
        "write_website_content": ("web", write_website_content),
        
        "run_code_safely": ("terminal", run_code_safely),
        "autofix_linter": ("terminal", autofix_linter),
        "save_checkpoint": ("terminal", save_checkpoint),
        "restore_checkpoint": ("terminal", restore_checkpoint),

        # Error memory. Both were imported at the top of this function but never
        # mapped, so they resolved for nobody: spawn_swarm hands this dict
        # straight to run_pipeline, and pipelines/research.py indexes
        # tools["recall_fix"], so every delegate_task run routed to a pipeline
        # died on KeyError('recall_fix') before doing any work. Grouped with
        # "file" to match consult_hivemind, the other memory-ish read.
        "recall_fix": ("file", recall_fix),
        "remember_fix": ("file", remember_fix),
    }
    
    # Resolve toolsets list
    toolsets_list = []
    if isinstance(toolsets, str):
        val_clean = toolsets.strip()
        if val_clean.startswith("[") and val_clean.endswith("]"):
            try:
                toolsets_list = json.loads(val_clean)
            except Exception:
                pass
        if not toolsets_list:
            toolsets_list = [t.strip() for t in val_clean.split(",") if t.strip()]
    elif isinstance(toolsets, list):
        toolsets_list = toolsets
    else:
        toolsets_list = ["terminal", "file", "web"]
        
    # Start from the canonical pipeline map. spawn_swarm passes this dict
    # straight to run_pipeline and nowhere else -- it is never handed to a
    # free-roaming child agent -- so a toolset filter here restricted nothing
    # and only starved the pipelines, which index tools by string key. Every
    # delegate_task run that reached a pipeline died on a KeyError for a tool
    # this function had simply never mapped.
    from tools.infrastructure.orchestrator import build_pipeline_tools
    selected_tools = build_pipeline_tools(str(settings.PROJECT_ROOT))

    # The toolset selection still decides which tools are ADVERTISED to the
    # child as its own callable surface.
    for name, (category, func) in all_tool_mappings.items():
        if category in toolsets_list:
            selected_tools[name] = func

    if is_orchestrator:
        from tools.strategy.delegation_tool import delegate_task
        selected_tools["delegate_task"] = delegate_task
        
    return selected_tools

@sovereign_tool(name="delegate_task", category="Strategy")
async def delegate_task(
    goal: str = "",
    context: str = "",
    toolsets: Any = None,
    tasks: Any = None,
    role: str = "leaf",
    max_iterations: int = 50
) -> str:
    """
    Delegate one or more tasks to isolated child AIAgent swarms in parallel.
    
    Args:
      goal: The objective for the child subagent (required for single task).
      context: Full background context and requirements for the child subagent.
      toolsets: Comma-separated list or JSON array of tool groups the child can access: 'terminal', 'file', 'web'. Defaults to all.
      tasks: JSON array of task definitions for parallel execution: [{"goal": "...", "context": "...", "toolsets": [...]}, ...]
      role: 'leaf' (default) prevents child from delegating further; 'orchestrator' permits nested delegation.
      max_iterations: Maximum iteration turns permitted for the subagent run (default: 50).
    """
    is_orchestrator = (role.strip().lower() == "orchestrator")
    
    # 1. Parallel Batch Delegation
    if tasks:
        parsed_tasks = []
        if isinstance(tasks, str):
            try:
                parsed_tasks = json.loads(tasks)
            except json.JSONDecodeError as e:
                return f"❌ Failed to parse tasks JSON: {e}"
        elif isinstance(tasks, list):
            parsed_tasks = tasks
            
        if not parsed_tasks:
            return "❌ No tasks provided in the tasks batch array."
            
        # Spawn concurrent child swarms
        async_tasks = []
        for i, t_spec in enumerate(parsed_tasks):
            t_goal = t_spec.get("goal", "")
            t_context = t_spec.get("context", "")
            t_toolsets = t_spec.get("toolsets", ["terminal", "file", "web"])
            
            if not t_goal:
                return f"❌ Task index {i} is missing 'goal'."
                
            t_tools = get_tools_for_toolsets(t_toolsets, is_orchestrator=is_orchestrator)
            t_prompt = f"OBJECTIVE: {t_goal}\n\nCONTEXT:\n{t_context}"
            
            # Append task run to gather
            async_tasks.append(spawn_swarm(t_prompt, t_tools, project_path=settings.PROJECT_ROOT))
            
        logger.info(f"⚡ Spawning {len(async_tasks)} parallel subagents...")
        results = await asyncio.gather(*async_tasks, return_exceptions=True)
        
        report = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                report.append(f"### Subagent Task {i+1} Failed\nError: {res}\n")
            else:
                report.append(f"### Subagent Task {i+1} Summary\n{res}\n")
        return "\n".join(report)
        
    # 2. Single Task Delegation
    else:
        if not goal:
            return "❌ Parameter 'goal' is required for single task delegation."
            
        t_tools = get_tools_for_toolsets(toolsets, is_orchestrator=is_orchestrator)
        t_prompt = f"OBJECTIVE: {goal}\n\nCONTEXT:\n{context}"
        
        logger.info(f"⚡ Spawning single subagent for goal: {goal[:50]}...")
        try:
            result = await spawn_swarm(t_prompt, t_tools, project_path=settings.PROJECT_ROOT)
            return f"### Subagent Task Summary\n{result}"
        except Exception as e:
            return f"❌ Subagent execution failed: {e}"
