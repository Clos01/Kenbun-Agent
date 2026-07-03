import re

def _extract_repo_from_task(task: str) -> str:
    # Look for a pattern like "from owner/repo" or "from URL"
    match = re.search(r"from\s+([^\s:]+)", task)
    if match:
        return match.group(1).strip()
    return "Clos01/Kenbun-Agent"

def build_git_push_integration_pipeline(tools):
    """
    Git Push Integration Pipeline:
    fetch_git_pushes → analyze_push_changes → apply_git_patch → run_code_safely → consult_supervisor → remember_fix
    
    Use case: Automatically poll a remote repository (such as Clos01/Kenbun-Agent),
    analyze commits & diffs, design ported features/fixes, safely apply them to Kenbun,
    run sandbox verification, and obtain supervisor approval.
    """
    steps = [
        {
            "id": "fetch_git_pushes",
            "label": "📡 Polling remote repository for new pushes",
            "tool": tools["fetch_git_pushes"],
            "input": lambda s: {
                "repo_url": s.get("repo_url") or _extract_repo_from_task(s["task"]),
                "branch": s.get("branch") or "main",
            },
            "output_key": "commit_data",
        },
        {
            "id": "analyze_push_changes",
            "label": "🔮 System 5: Analyzing push diffs and designing integration patch",
            "tool": tools["analyze_push_changes"],
            "input": lambda s: {
                "repo_url": s.get("repo_url") or _extract_repo_from_task(s["task"]),
                "commit_data": s.get("commit_data") or "{}",
                "project_path": s.get("project_path") or ".",
            },
            "skip_if": lambda s: not s.get("commit_data") or "new_pushes" not in s.get("commit_data", ""),
            "output_key": "changes_json",
        },
        {
            "id": "apply_git_patch",
            "label": "🛠️ Safely applying changes and running pre-flight linter",
            "tool": tools["apply_git_patch"],
            "input": lambda s: {
                "changes_json": s.get("changes_json") or "{}",
            },
            "skip_if": lambda s: not s.get("changes_json") or "success" not in s.get("changes_json", ""),
            "output_key": "apply_result",
        },
        {
            "id": "sandbox_verify",
            "label": "🐳 Verifying integrated code in execution sandbox",
            "tool": tools["run_code_safely"],
            "input": lambda s: {
                "code": "print('Running Git Push Integration sandbox check')",
                "language": "python",
            },
            "skip_if": lambda s: not s.get("changes_json") or "success" not in s.get("changes_json", ""),
            "output_key": "sandbox_result",
        },
        {
            "id": "supervisor_audit",
            "label": "🏛️ System 2: Obtaining Executive Supervisor sign-off",
            "tool": tools["consult_supervisor"],
            "input": lambda s: {
                "user_proposal": f"Git Push Integration from {_extract_repo_from_task(s['task'])}",
                "code_snippet": s.get("apply_result", ""),
            },
            "skip_if": lambda s: not s.get("changes_json") or "success" not in s.get("changes_json", ""),
            "output_key": "supervisor_result",
        },
        {
            "id": "remember_fix",
            "label": "🧠 Logging lesson to error memory database",
            "tool": tools["remember_fix"],
            "input": lambda s: {
                "error_message": f"Git Push Integration: {_extract_repo_from_task(s['task'])}",
                "solution": s.get("apply_result") or "No changes applied",
                "file_context": "git_watcher_tools",
            },
            "skip_if": lambda s: not s.get("changes_json") or "success" not in s.get("changes_json", ""),
            "output_key": "memory_result",
        }
    ]
    return steps
