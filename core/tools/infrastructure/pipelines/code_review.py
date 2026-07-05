from tools.utils.orchestrator_helpers import build_context
from tools.utils.ide_context import uses_external_review, log_ide_context

def build_code_review_pipeline(tools):
    """
    IDE-aware code review pipeline.

    When called from Claude Code / Antigravity (or any self-sufficient AI IDE):
        scan_repo → supervisor_review
        (Gemini is skipped — the IDE IS the intelligence layer)

    When called from local CLI, VS Code, or other IDEs:
        scan_repo → gemini_review → supervisor_review
        (Gemini provides the external cloud AI review)

    Use case: "Review this code for security issues"
    Control via: KENBUN_CALLER_IDE env var (claude | cursor | vscode | local)
    """
    import sys
    print(log_ide_context(), file=sys.stderr)

    steps = [
        {
            "id": "scan_repo",
            "label": "🗺️ Scanning project structure",
            "tool": tools["scan_repo"],
            "input": lambda s: {"project_path": s["project_path"]},
            "skip_if": lambda s: not s.get("project_path"),
            "output_key": "repo_map",
        },
        {
            "id": "analyze_review_request",
            "label": "🔬 Analyzing review request (LLM)",
            "tool": tools.get("analyze_bug"),
            "input": lambda s: {
                "task": s["task"],
                "project_path": s.get("project_path", ""),
                "file_path": s.get("file_path", ""),
                "code_snippet": s.get("code_snippet", "")
            },
            "skip_if": lambda s: bool(s.get("code_snippet") or s.get("repo_map")),
            "output_key": "code_snippet",
        },
    ]

    if uses_external_review():
        # Non-Claude IDE: use Gemini as the external AI review layer
        # cross_check=False avoids double-calling the supervisor inside gemini_reviewer
        steps.append({
            "id": "gemini_review",
            "label": "🔮 Running Gemini code review (external AI layer)",
            "tool": tools["review_code_with_gemini"],
            "input": lambda s: {
                "code_snippet": s.get("code_snippet", ""),
                "review_context": build_context(s),
                "tech_key": s.get("tech_key", ""),
                "cross_check": False,  # Supervisor runs as its own separate step below
            },
            "output_key": "review_result",
        })

    # Supervisor runs in all cases — local model cross-check
    steps.append({
        "id": "supervisor_review",
        "label": "🏛️ System 2: Supervisor sign-off",
        "tool": tools["consult_supervisor"],
        "input": lambda s: {
            "user_proposal": s["task"],
            "code_snippet": s.get("code_snippet", ""),
            "iterative_mode": False,
        },
        "skip_if": lambda s: not (s.get("code_snippet") or s.get("repo_map")),
        "output_key": "supervisor_result",
    })

    return steps
