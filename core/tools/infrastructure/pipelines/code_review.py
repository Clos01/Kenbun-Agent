from tools.utils.orchestrator_helpers import build_context

def build_code_review_pipeline(tools):
    """
    Pipeline: scan → gemini review → docs → supervisor → consensus
    Use case: "Review this code for security issues"
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
            "id": "gemini_review",
            "label": "🔮 Running full Gemini code review pipeline",
            "tool": tools["review_code_with_gemini"],
            "input": lambda s: {
                "code_snippet": s["code_snippet"],
                "review_context": build_context(s),
                "tech_key": s.get("tech_key", ""),
                "cross_check": True,
            },
            "output_key": "review_result",
        },
    ]
