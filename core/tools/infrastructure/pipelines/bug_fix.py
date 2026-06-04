from tools.utils.orchestrator_helpers import build_context, detect_language
from tools.audit.reflection_agent import reflect_and_distill

def build_bug_fix_pipeline(tools):
    """
    Pipeline: scan → recall → checkpoint → sandbox → backtrack/remember
    Use case: "Fix this bug in auth.py"
    """
    return [
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
            "label": "🧠 Searching for similar past fixes",
            "tool": tools["recall_fix"],
            "input": lambda s: {"error_message": s["task"]},
            "output_key": "past_fixes",
        },
        {
            "id": "save_checkpoint",
            "label": "🔄 Saving checkpoint before changes",
            "tool": tools["save_checkpoint"],
            "input": lambda s: {"file_path": s["file_path"], "label": "pre_fix"},
            "skip_if": lambda s: not s.get("file_path"),
            "output_key": "checkpoint_result",
        },
        {
            "id": "autofix_linter",
            "label": "🚀 Running pre-flight linter auto-fix (eslint / black)",
            "tool": tools["autofix_linter"],
            "input": lambda s: {"file_path": s.get("file_path", ""), "project_path": s.get("project_path", "")},
            "skip_if": lambda s: not s.get("file_path"),
            "output_key": "linter_autofix_result",
        },
        {
            "id": "gemini_review",
            "label": "🔮 Asking Gemini to analyze the bug",
            "tool": tools["review_code_with_gemini"],
            "input": lambda s: {
                "code_snippet": s.get("code_snippet", s.get("task", "")),
                "review_context": build_context(s),
                "tech_key": s.get("tech_key", ""),
                "cross_check": True,
            },
            "output_key": "gemini_analysis",
            "fallback_to": "consult_supervisor",
        },
        {
            "id": "sandbox_test",
            "label": "🐳 Testing fix in sandbox",
            "tool": tools["run_code_safely"],
            "input": lambda s: {
                "code": s.get("code_snippet", "print(\'No code to test\')"),
                "language": detect_language(s.get("file_path", "test.py")),
            },
            "skip_if": lambda s: not s.get("code_snippet"),
            "output_key": "sandbox_result",
            "on_failure": "backtrack",
        },
        {
            "id": "remember_result",
            "label": "🧠 Saving lesson to error memory",
            "tool": tools["remember_fix"],
            "input": lambda s: {
                "error_message": s["task"],
                "solution": s.get("gemini_analysis", "See report")[:2000],
                "file_context": s.get("file_path", ""),
            },
            "output_key": "memory_result",
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
