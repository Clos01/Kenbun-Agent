from tools.utils.orchestrator_helpers import build_context, detect_language


def _has_useful_recall(state) -> bool:
    """Return True only when recall_fix produced a usable past-fix payload."""
    past = state.get("past_fixes")
    if not past:
        return False
    if isinstance(past, str):
        # error_memory returns markdown like "## 🧠 Error Memory\n\nNo similar errors..."
        return "no similar errors" not in past.lower() and "not found" not in past.lower()
    if isinstance(past, (list, dict)):
        return bool(past)
    return True


def build_bug_fix_pipeline(tools):
    """
    Pipeline: recall → analyze → checkpoint → autofix → sandbox → remember
    Use case: Deterministic execution wrapper for a bug fix.

    The `analyze_bug` step closes the previous gap where the pipeline would
    skip every action when no memory hit and no file_path/code_snippet were
    supplied, then save the run as "Unresolved" without ever asking an LLM
    to look at the problem.
    """
    steps = [
        {
            "id": "recall_fix",
            "label": "🧠 Searching for similar past fixes",
            "tool": tools["recall_fix"],
            "input": lambda s: {"error_message": s["task"]},
            "output_key": "past_fixes",
        },
    ]

    # Only register the analyzer step if the orchestrator wired the tool in.
    if "analyze_bug" in tools:
        steps.append({
            "id": "analyze_bug",
            "label": "🔬 Diagnosing bug and proposing patch (LLM analyzer)",
            "tool": tools["analyze_bug"],
            "input": lambda s: {
                "task": s["task"],
                "file_path": s.get("file_path", ""),
                "code_snippet": s.get("code_snippet", ""),
                "project_path": s.get("project_path", ""),
                "past_fixes": s.get("past_fixes", ""),
            },
            # Skip if we already have a strong memory hit OR the caller pre-supplied
            # a concrete code_snippet to test. Otherwise always run the analyzer so
            # we never silently exit with "Unresolved".
            "skip_if": lambda s: s.get("fast") or (_has_useful_recall(s) and bool(s.get("code_snippet"))),
            "output_key": "analysis",
        })

    steps.extend([
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
                # Prefer concrete code, then the analyzer's diagnosis, then a placeholder
                "solution": (
                    s.get("code_snippet")
                    or (str(s.get("analysis"))[:2000] if s.get("analysis") else "See report")
                ),
                "file_context": s.get("file_path", ""),
            },
            "output_key": "memory_result",
        },
    ])
    return steps
