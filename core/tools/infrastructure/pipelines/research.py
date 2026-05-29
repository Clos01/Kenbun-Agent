from tools.utils.orchestrator_helpers import build_context, detect_language
from tools.audit.reflection_agent import reflect_and_distill

def build_research_pipeline(tools):
    """
    Pipeline: research → scan → checkpoint → sandbox test → supervisor
    Use case: "Research and implement JWT auth"
    """
    return [
        {
            "id": "research",
            "label": "🔮 Researching with Gemini",
            "tool": tools["research_with_gemini"],
            "input": lambda s: {
                "query": s["task"],
                "tech_key": s.get("tech_key", ""),
            },
            "output_key": "research_result",
        },
        {
            "id": "scan_repo",
            "label": "🗺️ Scanning project structure",
            "tool": tools["scan_repo"],
            "input": lambda s: {"project_path": s["project_path"]},
            "skip_if": lambda s: not s.get("project_path"),
            "output_key": "repo_map",
        },
        {
            "id": "recall_fix",
            "label": "🧠 Checking error memory for relevant history",
            "tool": tools["recall_fix"],
            "input": lambda s: {"error_message": s["task"]},
            "output_key": "past_fixes",
        },
        {
            "id": "save_checkpoint",
            "label": "🔄 Saving checkpoint",
            "tool": tools["save_checkpoint"],
            "input": lambda s: {"file_path": s["file_path"], "label": "pre_implement"},
            "skip_if": lambda s: not s.get("file_path"),
            "output_key": "checkpoint_result",
        },
        {
            "id": "guardrail_audit",
            "label": "🛡️ System 2c: Continuous Guardrail Audit ($0)",
            "tool": tools["guardrail_audit"],
            "input": lambda s: {
                "code_snippet": s.get("code_snippet", ""),
                "task_context": s["task"]
            },
            "output_key": "guardrail_result",
        },
        {
            "id": "supervisor_review",
            "label": "🏛️ System 2: Getting Executive Supervisor sign-off",
            "tool": tools["consult_supervisor"],
            "input": lambda s: {
                "user_proposal": s["task"],
                "code_snippet": s.get("code_snippet", ""),
            },
            "output_key": "supervisor_result",
        },
        {
            "id": "maze_verification",
            "label": "🌀 System 2: Maze Protocol (Backward Walk)",
            "tool": tools["maze_verification"],
            "input": lambda s: {
                "target_file": s.get("file_path", ""),
                "project_root": s.get("project_path", ".")
            },
            "skip_if": lambda s: not s.get("file_path"),
            "output_key": "maze_result",
            "on_failure": "backtrack",
        },
        {
            "id": "reflect",
            "label": "🧠 System 5: Reflecting on task",
            "tool": reflect_and_distill,
            "input": lambda s: {
                "task": s["task"],
                "tool_logs": s.get("full_log", ""),
            },
            "output_key": "reflection_result",
        }
    ]
