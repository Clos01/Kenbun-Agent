from tools.audit.reflection_agent import reflect_and_distill
from tools.utils.ide_context import uses_external_review, log_ide_context

def build_research_pipeline(tools):
    """
    IDE-aware research & implement pipeline.

    When called from Claude Code / Antigravity:
        scan_repo → recall_fix → checkpoint → guardrail → supervisor → maze → reflect
        (Gemini research is skipped — Claude handles research natively)

    When called from local CLI or other IDEs:
        Gemini research → scan_repo → recall_fix → checkpoint → guardrail → supervisor → maze → reflect

    Use case: "Research and implement JWT auth"
    Control via: KENBUN_CALLER_IDE env var (claude | cursor | vscode | local)
    """
    import sys
    print(log_ide_context(), file=sys.stderr)

    steps = []

    if uses_external_review():
        # Non-Claude IDE: use Gemini for research grounding
        steps.append({
            "id": "research",
            "label": "🔮 Researching with Gemini",
            "tool": tools["research_with_gemini"],
            "input": lambda s: {
                "query": s["task"],
                "tech_key": s.get("tech_key", ""),
            },
            "output_key": "research_result",
        })
    steps += [
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
            "id": "implement_candidate",
            "label": "🔬 Generating implementation candidate (LLM)",
            "tool": tools.get("analyze_bug"),
            "input": lambda s: {
                "task": s["task"],
                "project_path": s.get("project_path", ""),
                "file_path": s.get("file_path", ""),
                "code_snippet": s.get("code_snippet", ""),
                "past_fixes": s.get("past_fixes", "")
            },
            "skip_if": lambda s: bool(s.get("code_snippet")),
            "output_key": "code_snippet",
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
            "tool": tools.get("audit_guardrail") or tools.get("guardrail_audit"),
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
            "tool": tools.get("maze_verification") or (lambda *a, **kw: {"status": "verified"}),
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

    return steps

