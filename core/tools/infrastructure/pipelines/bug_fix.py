from tools.utils.orchestrator_helpers import build_context, detect_language

def build_bug_fix_pipeline(tools):
    """
    Pipeline: recall → checkpoint → autofix → sandbox → remember
    Use case: Deterministic execution wrapper for a bug fix.
    """
    return [
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
            "id": "sandbox_test",
            "label": "🐳 Testing fix in sandbox",
            "tool": tools["run_code_safely"],
            "input": lambda s: {
                "code": s.get("code_snippet", "print(\'No code to test\')"),
                "language": detect_language(s.get("file_path", "test.py")),
            },
            "skip_if": lambda s: not s.get("code_snippet"),
            "output_key": "sandbox_result",
        },
        {
            "id": "remember_result",
            "label": "🧠 Saving lesson to error memory",
            "tool": tools["remember_fix"],
            "input": lambda s: {
                "error_message": s["task"],
                "solution": s.get("code_snippet", "See report")[:2000],
                "file_context": s.get("file_path", ""),
            },
            "output_key": "memory_result",
        }
    ]
