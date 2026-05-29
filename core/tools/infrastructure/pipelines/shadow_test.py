from tools.utils.orchestrator_helpers import detect_language

def build_shadow_test_pipeline(tools):
    """
    Pipeline: read → analyze → draft test → supervisor check → sandbox
    Use case: "Background test generation for modified files"
    """
    return [
        {
            "id": "read_file",
            "label": "📄 Reading changed file",
            "tool": tools.get("view_file"),
            "input": lambda s: {"AbsolutePath": s["file_path"]},
            "skip_if": lambda s: not s.get("file_path"),
            "output_key": "file_content",
        },
        {
            "id": "gemini_draft",
            "label": "🔮 Drafting unit tests with Gemini Flash",
            "tool": tools["review_code_with_gemini"],
            "input": lambda s: {
                "code_snippet": s.get("file_content", ""),
                "review_context": "Draft a unit test for the latest changes in this file. Prioritize edge cases.",
                "tech_key": s.get("tech_key", ""),
                "thinking": False, # Keep it fast/cheap
            },
            "output_key": "test_draft",
        },
        {
            "id": "guardrail_audit",
            "label": "🛡️ System 2c: Local Guardrail Audit ($0)",
            "tool": tools["guardrail_audit"],
            "input": lambda s: {
                "code_snippet": s.get("test_draft", ""),
                "task_context": "Verify the logic of this drafted unit test."
            },
            "output_key": "guardrail_result",
        },
        {
            "id": "supervisor_audit",
            "label": "🏛️ System 2: Executive Supervisor Audit",
            "tool": tools["consult_supervisor"],
            "input": lambda s: {
                "user_proposal": "Verify the logic of this drafted unit test.",
                "code_snippet": s.get("test_draft", ""),
            },
            "output_key": "supervisor_audit",
        },
        {
            "id": "sandbox_run",
            "label": "🐳 Verifying test in Sandbox",
            "tool": tools["run_code_safely"],
            "input": lambda s: {
                "code": s.get("test_draft", ""),
                "language": detect_language(s.get("file_path", "test.py")),
            },
            "skip_if": lambda s: not s.get("test_draft"),
            "output_key": "sandbox_result",
        }
    ]
