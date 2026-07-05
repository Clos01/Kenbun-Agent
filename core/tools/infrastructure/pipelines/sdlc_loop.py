from tools.utils.orchestrator_helpers import detect_language

def build_sdlc_loop_pipeline(tools):
    """
    SDLC Loop: sync_jira_issue → recall_fix → save_checkpoint → autofix_linter → run_code_safely → consult_supervisor → create_bitbucket_pr → remember_fix
    Use case: Fully automated loop from task intake (Jira) to pull request generation (Bitbucket) with quality checks.
    """
    steps = [
        {
            "id": "jira_intake",
            "label": "📋 Syncing issue details from Jira",
            "tool": tools["sync_jira_issue"],
            "input": lambda s: {
                "issue_key": s["task"].split(":")[0].strip() if ":" in s["task"] else s["task"],
                "status_update": "In Progress"
            },
            "output_key": "jira_details",
        },
        {
            "id": "recall_fix",
            "label": "🧠 Searching memory for similar error patterns",
            "tool": tools["recall_fix"],
            "input": lambda s: {"error_message": s["task"]},
            "output_key": "past_fixes",
        },
        {
            "id": "save_checkpoint",
            "label": "🔄 Saving safety checkpoint",
            "tool": tools["save_checkpoint"],
            "input": lambda s: {"file_path": s.get("file_path", ""), "label": "pre_sdlc_fix"},
            "skip_if": lambda s: not s.get("file_path"),
            "output_key": "checkpoint_result",
        },
        {
            "id": "autofix_linter",
            "label": "🚀 Running linter pre-flight check",
            "tool": tools["autofix_linter"],
            "input": lambda s: {"file_path": s.get("file_path", ""), "project_path": s.get("project_path", "")},
            "skip_if": lambda s: not s.get("file_path"),
            "output_key": "linter_result",
        },
        {
            "id": "sandbox_verify",
            "label": "🐳 Verifying candidate code in execution sandbox",
            "tool": tools["run_code_safely"],
            "input": lambda s: {
                "code": s.get("code_snippet") or "print('Running default SDLC test')",
                "language": detect_language(s.get("file_path", "test.py")),
            },
            "output_key": "sandbox_result",
        },
        {
            "id": "supervisor_audit",
            "label": "🏛️ System 2: Obtaining Executive Supervisor sign-off",
            "tool": tools["consult_supervisor"],
            "input": lambda s: {
                "user_proposal": s["task"],
                "code_snippet": s.get("code_snippet", ""),
            },
            "output_key": "supervisor_result",
        },
        {
            "id": "bitbucket_pr",
            "label": "🚀 Filing Bitbucket Pull Request",
            "tool": tools["create_bitbucket_pr"],
            "input": lambda s: {
                "repo_slug": s.get("repo_slug") or "kenbun-agent",
                "source_branch": s.get("source_branch") or "feature/sdlc-auto-patch",
                "target_branch": s.get("target_branch") or "master",
                "title": s.get("pr_title") or f"Auto-patch for {s['task'].split(':')[0].strip() if ':' in s['task'] else 'Task'}",
                "description": s.get("pr_description") or f"Automated patch addressing task: {s['task']}"
            },
            "output_key": "bitbucket_pr_result",
        },
        {
            "id": "remember_fix",
            "label": "🧠 Logging lesson to error memory database",
            "tool": tools["remember_fix"],
            "input": lambda s: {
                "error_message": s["task"],
                "solution": s.get("code_snippet") or "Task completed successfully",
                "file_context": s.get("file_path", ""),
            },
            "output_key": "memory_result",
        },
        {
            "id": "jira_complete",
            "label": "📋 Updating Jira ticket to Done",
            "tool": tools["sync_jira_issue"],
            "input": lambda s: {
                "issue_key": s["task"].split(":")[0].strip() if ":" in s["task"] else s["task"],
                "status_update": "Done"
            },
            "output_key": "jira_complete_details",
        }
    ]
    return steps
