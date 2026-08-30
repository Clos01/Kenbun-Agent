import os
import json
import logging
import asyncio
from typing import Dict, Any
from tools.registry import sovereign_tool
from tools.infrastructure.config import settings
from tools.infrastructure.orchestrator import spawn_swarm

logger = logging.getLogger("delegation_tool")

_FULL_TOOLSETS = {"terminal", "file", "web"}
_LEAF_TIMEOUT_S = 900  # a leaf delegation that runs longer than this is hung


def _toolsets_restricted(toolsets: Any) -> bool:
    """True iff the caller asked for a strict subset of {terminal, file, web}.

    A restricted request must keep the exact old spawn_swarm route with its
    scoped tool advertising -- the subagent seam gives a child the full
    build_pipeline_tools surface, which would widen a deliberately-narrow
    delegation. None / "" / the full set -> not restricted -> seam is fine.
    """
    if toolsets in (None, "", []):
        return False
    resolved: set
    if isinstance(toolsets, str):
        s = toolsets.strip()
        try:
            parsed = json.loads(s) if s.startswith("[") else None
        except json.JSONDecodeError:
            parsed = None
        resolved = set(parsed) if isinstance(parsed, list) else {
            t.strip() for t in s.split(",") if t.strip()
        }
    elif isinstance(toolsets, list):
        resolved = set(toolsets)
    else:
        return False
    return bool(resolved) and not _FULL_TOOLSETS.issubset(resolved)


def _sanitize_error(e: BaseException) -> str:
    """One-line, path-free label for an exception surfaced to a child agent."""
    return type(e).__name__


async def _run_leaf(goal: str, context: str) -> str:
    """One leaf delegation, through the DSH-04 subagent seam.

    The seam's default provider is the same in-process Queen+workers swarm this
    tool always used, so the happy path is unchanged -- but when it reports itself
    unavailable (Gemini decomposition 429), `fallback=True` walks to the next
    registered provider (e.g. an external `claude` CLI) instead of dead-ending.
    `subagent.run` is sync; `to_thread` gives it a loop-free worker so the
    provider's own `asyncio.run(spawn_swarm(...))` bridge is clean.
    """
    from tools.execution.subagent import subagent

    try:
        res = await asyncio.wait_for(
            asyncio.to_thread(
                subagent.run, goal, context=context, cwd=str(settings.PROJECT_ROOT),
            ),
            timeout=_LEAF_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning("delegate_task: leaf delegation exceeded %ss", _LEAF_TIMEOUT_S)
        return f"❌ delegation timed out after {_LEAF_TIMEOUT_S}s"

    if res.ok:
        return res.output
    # Failure: hand the child only the seam-controlled reason (clean, no host
    # paths / stack). The provider's raw output goes to the log, not the child.
    logger.warning("delegate_task: leaf delegation failed via %s: %s",
                   res.provider, res.output[:2000])
    return f"❌ delegation failed: {res.error or 'subagent unavailable'}"

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
        path = os.path.realpath(AbsolutePath)
        root = os.path.realpath(str(settings.PROJECT_ROOT))
        # Boundary-aware: a bare startswith lets '/app/project_secrets' pass when
        # root is '/app/project'. Require an exact match or a real separator.
        if path != root and not path.startswith(root + os.sep):
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

    _bad = {c for c, _ in all_tool_mappings.values()} - _FULL_TOOLSETS
    if _bad:  # a mistyped or new category would silently never be advertised
        logger.error("delegate_task: tool categories %s are not in _FULL_TOOLSETS", _bad)

    # Resolve toolsets list
    toolsets_list = []
    if isinstance(toolsets, str):
        val_clean = toolsets.strip()
        if val_clean.startswith("[") and val_clean.endswith("]"):
            try:
                toolsets_list = json.loads(val_clean)
            except Exception as e:
                logger.warning("delegate_task: malformed toolsets JSON %r (%s); "
                               "falling back to comma-split", val_clean, e)
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
      max_iterations: Advisory only today -- accepted for forward compatibility; not yet
        enforced by the in-process swarm or the seam.
    """
    is_orchestrator = (str(role).strip().lower() == "orchestrator")

    # The subagent seam (DSH-04) gives the "leaf" path a provider-fallback when
    # the in-process swarm hits a Gemini quota wall. It is used only when it
    # changes nothing else:
    #   * role="orchestrator" -> nested delegation, which the seam does not model
    #   * a restricted `toolsets` -> the seam would hand the child the full tool
    #     surface, widening a deliberately-narrow delegation
    # Either case keeps the original spawn_swarm route with its scoped tools.
    use_seam = not is_orchestrator and not _toolsets_restricted(toolsets)

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

            # per-task: seam only when this task is neither orchestrator-scoped
            # nor toolset-restricted (see the use_seam comment above).
            if not is_orchestrator and not _toolsets_restricted(t_spec.get("toolsets")):
                async_tasks.append(_run_leaf(t_goal, t_context))
            else:
                t_tools = get_tools_for_toolsets(t_toolsets, is_orchestrator=is_orchestrator)
                t_prompt = f"OBJECTIVE: {t_goal}\n\nCONTEXT:\n{t_context}"
                async_tasks.append(spawn_swarm(t_prompt, t_tools, project_path=settings.PROJECT_ROOT))

        logger.info(f"⚡ Spawning {len(async_tasks)} parallel subagents...")
        results = await asyncio.gather(*async_tasks, return_exceptions=True)
        
        report = []
        for i, res in enumerate(results):
            if isinstance(res, BaseException):
                logger.warning("delegate_task: batch task %d raised", i + 1, exc_info=res)
                report.append(f"### Subagent Task {i+1} Failed\nError: {_sanitize_error(res)}\n")
            else:
                report.append(f"### Subagent Task {i+1} Summary\n{res}\n")
        return "\n".join(report)
        
    # 2. Single Task Delegation
    else:
        if not goal:
            return "❌ Parameter 'goal' is required for single task delegation."

        from tools.execution.subagent.definition import task_label
        logger.info("⚡ Spawning single subagent for goal: %s", task_label(goal))
        try:
            if use_seam:
                result = await _run_leaf(goal, context)
            else:
                t_tools = get_tools_for_toolsets(toolsets, is_orchestrator=is_orchestrator)
                t_prompt = f"OBJECTIVE: {goal}\n\nCONTEXT:\n{context}"
                result = await spawn_swarm(t_prompt, t_tools, project_path=settings.PROJECT_ROOT)
            return f"### Subagent Task Summary\n{result}"
        except Exception as e:
            logger.warning("delegate_task: single delegation raised", exc_info=True)
            return f"❌ Subagent execution failed ({_sanitize_error(e)}) -- see delegation_tool logs"
