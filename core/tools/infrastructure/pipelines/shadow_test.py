import re
from pathlib import PurePosixPath

from tools.utils.orchestrator_helpers import detect_language


# Matches the first fenced code block in an LLM response. Language tag is
# optional (```python, ```ts, ```, etc.). Non-greedy body so we stop at the
# first closing fence. DOTALL so `.` covers newlines.
_FENCED_BLOCK_RE = re.compile(
    r"```(?:[a-zA-Z0-9_+\-]*)\s*\n?(.*?)```",
    re.DOTALL,
)


def _path_to_module(file_path: str) -> str:
    """Convert a Python file path into the dotted import path used in code.

    The Kenbun source tree puts every package under `core/tools/` but is
    imported as `tools.<sub>` — `sys.path` is rooted at `core/` inside the
    container. So we anchor on the `core/tools/` segment and take everything
    from `tools/` onward.

    Examples (all return `tools.infrastructure.orchestrator`):
      - core/tools/infrastructure/orchestrator.py
      - /app/core/tools/infrastructure/orchestrator.py
      - /Users/dev/Dev/Kenbun/core/tools/infrastructure/orchestrator.py

    Other shapes:
      - tools/utils/llm_router.py     → tools.utils.llm_router  (no `core/`)
      - core/tools/__init__.py        → tools                   (drops __init__)
      - scripts/dev/foo.py            → foo                     (fallback to stem)
      - "" / None                     → ""

    Used by the gemini_draft step to inject the correct fully-qualified
    import path into the prompt so the drafted test imports the module
    the way the rest of the codebase does, instead of doing
    `from orchestrator import ...` based on the bare filename.
    """
    if not file_path:
        return ""
    parts = list(PurePosixPath(str(file_path).replace("\\", "/")).parts)
    if not parts:
        return ""

    # Anchor on `core/tools/` — the canonical Kenbun layout. Handles any
    # absolute-path prefix (host Mac path, container `/app/...`, etc.).
    tools_idx = None
    for i in range(len(parts) - 1):
        if parts[i] == "core" and parts[i + 1] == "tools":
            tools_idx = i + 1
            break

    # Fallback: a path that already starts at `tools/...` (test fixtures,
    # someone passing the relative-from-core form, etc.).
    if tools_idx is None:
        try:
            tools_idx = parts.index("tools")
        except ValueError:
            # Out-of-tree file (scripts/, external/, …). Best-effort: stem.
            return PurePosixPath(parts[-1]).stem

    rel = list(parts[tools_idx:])
    if rel[-1].endswith(".py"):
        rel[-1] = rel[-1][:-3]
    # `__init__.py` belongs to the package itself, not a sub-module.
    if rel and rel[-1] == "__init__":
        rel.pop()
    return ".".join(rel)


def _extract_code(text) -> str:
    """Pull the first fenced code block out of an LLM markdown response.

    The Gemini draft step produces a full markdown review — headings, bullets,
    emojis, and (somewhere in the middle) the actual test code wrapped in a
    ```python ... ``` block. Downstream steps (guardrail, supervisor, sandbox)
    treat `test_draft` as raw executable code, so without this shim the sandbox
    writes lines like `## 🔮 GEMINI CODE REVIEW` to a .py file and Python
    errors out on `SyntaxError: invalid character '⚠'`.

    Behaviour:
    - Returns the body of the first ```...``` block (language tag stripped).
    - If no fence is found, returns the input stripped — so a model that
      already responded with raw code still passes through.
    - Coerces None/non-string input to str so a failed upstream step doesn't
      cascade into a TypeError before the guardrail can flag it.
    - Does NOT try to parse nested fences; if the test code itself contains
      ``` markers, the inner closing fence wins. Rare enough to ignore.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    match = _FENCED_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


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
                "review_context": (
                    # Tell Gemini the fully-qualified import path so the drafted
                    # test uses `from tools.infrastructure.orchestrator import …`
                    # instead of inferring `from orchestrator import …` from the
                    # bare filename (which crashes pytest with ModuleNotFoundError).
                    f"This module is imported as `{_path_to_module(s.get('file_path', ''))}`. "
                    "Draft a unit test for the latest changes in this file. "
                    "Use that fully-qualified import path — do NOT use bare-filename "
                    "imports like `from orchestrator import ...`. "
                    "Prioritize edge cases."
                ),
                "tech_key": s.get("tech_key", ""),
                "thinking": False, # Keep it fast/cheap
            },
            "skip_if": lambda s: not s.get("file_content"),
            "output_key": "test_draft",
        },
        {
            "id": "guardrail_audit",
            "label": "🛡️ System 2c: Local Guardrail Audit ($0)",
            "tool": tools["guardrail_audit"],
            "input": lambda s: {
                "code_snippet": _extract_code(s.get("test_draft", "")),
                "task_context": "Verify the logic of this drafted unit test."
            },
            "skip_if": lambda s: not s.get("test_draft"),
            "output_key": "guardrail_result",
        },
        {
            "id": "supervisor_audit",
            "label": "🏛️ System 2: Executive Supervisor Audit",
            "tool": tools["consult_supervisor"],
            "input": lambda s: {
                "user_proposal": "Verify the logic of this drafted unit test.",
                "code_snippet": _extract_code(s.get("test_draft", "")),
            },
            "skip_if": lambda s: not s.get("test_draft"),
            "output_key": "supervisor_audit",
        },
        {
            "id": "sandbox_run",
            "label": "🐳 Verifying test in Sandbox",
            "tool": tools["run_code_safely"],
            "input": lambda s: {
                "code": _extract_code(s.get("test_draft", "")),
                "language": detect_language(s.get("file_path", "test.py")),
            },
            "skip_if": lambda s: not s.get("test_draft"),
            "output_key": "sandbox_result",
        }
    ]
