from tools.utils.orchestrator_helpers import build_context
from tools.utils.ide_context import uses_external_review, log_ide_context
from tools.utils.review_targets import load_review_target


def _no_source_report(task: str = "", project_path: str = "", file_path: str = "") -> str:
    """Explain that there is nothing to review, instead of reviewing nothing.

    The reviewers below used to fall back to `repo_map` — a signatures-only
    listing — and sign off having read no implementation. Worse, when the
    caller named no project at all, that repo_map was of Kenbun's own source.
    A review with no code is a failed review and must say so.
    """
    return (
        "🛑 **No source loaded — review aborted.**\n\n"
        "`code_review` needs actual code. Nothing was resolved from the "
        "arguments given, so no reviewer ran.\n\n"
        f"- `code_snippet`: empty\n"
        f"- `file_path`: {file_path or 'not set'}\n"
        f"- `project_path`: {project_path or 'not set'}\n\n"
        "Pass one of:\n"
        "1. `code_snippet=\"<the code>\"` — review code inline. Use this when "
        "the source lives somewhere this container cannot read, such as a "
        "path on the caller's own machine.\n"
        "2. `file_path=\"path/to/file.py\"` together with `project_path` — "
        "both must be readable from inside this container.\n"
        "3. `project_path=\"/path/to/repo\"` alone — reviews `git diff HEAD`.\n\n"
        f"Task was: {task[:300]}"
    )

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
            # Materialize the ACTUAL code under review (real source or a diff)
            # into code_snippet. Without this the reviewers below fall back to
            # the signatures-only repo_map and sign off having seen no
            # implementation. Runs whenever the caller didn't pre-supply code.
            "id": "load_review_target",
            "label": "📄 Loading source under review",
            "tool": load_review_target,
            "input": lambda s: {
                "project_path": s.get("project_path", ""),
                "file_path": s.get("file_path", ""),
                "code_snippet": s.get("code_snippet", ""),
                "task": s.get("task", ""),
            },
            "skip_if": lambda s: bool(s.get("code_snippet")),
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
            "skip_if": lambda s: not s.get("code_snippet"),
            "output_key": "review_result",
        })

    # Supervisor runs in all cases — local model cross-check
    steps.append({
        "id": "supervisor_review",
        "label": "🏛️ System 2: Supervisor sign-off",
        "tool": tools["consult_supervisor"],
        "input": lambda s: {
            "user_proposal": s["task"],
            # Real code only. Feeding the repo_map here made the supervisor
            # read a 24k-char file listing as though it were an implementation,
            # which is both a useless review and what pushed it past its 120s
            # timeout on large repos.
            "code_snippet": s.get("code_snippet", ""),
            "iterative_mode": False,
        },
        "skip_if": lambda s: not s.get("code_snippet"),
        "output_key": "supervisor_result",
    })

    # Runs only when every reviewer above was skipped for lack of code.
    steps.append({
        "id": "no_source",
        "label": "🛑 No source to review",
        "tool": _no_source_report,
        "input": lambda s: {
            "task": s.get("task", ""),
            "project_path": s.get("project_path", ""),
            "file_path": s.get("file_path", ""),
        },
        "skip_if": lambda s: bool(s.get("code_snippet")),
        "output_key": "no_source_report",
    })

    return steps
