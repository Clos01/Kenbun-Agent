"""
E2B Runner — Safe code execution in remote microVMs.

Replaces local Docker sandboxing with E2B's secure, cloud-hosted microVMs.
This prevents container escape vulnerabilities and handles isolation natively.
"""
import os
from e2b_code_interpreter import Sandbox

# --- CONFIGURATION ---
DEFAULT_TIMEOUT_SEC = 60

def run_code_safely(
    code: str,
    language: str = "python",
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> str:
    """
    Execute code in a secure E2B remote microVM.

    Args:
        code: The source code to execute
        language: "python" or "javascript"
        timeout: Execution timeout in seconds

    Returns:
        A formatted string with stdout, stderr, and exit code/status.
    """
    e2b_api_key = os.getenv("E2B_API_KEY")
    if not e2b_api_key:
        return "❌ E2B API Key is missing. Please set E2B_API_KEY in your environment."

    lang = language.lower()
    if lang not in ("python", "javascript", "node"):
        return f"❌ Unsupported language: '{language}'."

    try:
        # Launch a dedicated, ephemeral sandbox VM for this execution
        with Sandbox(api_key=e2b_api_key) as sandbox:
            
            # Execute the code depending on the requested language
            if lang == "python":
                execution = sandbox.run_code(code, timeout=timeout)
            else:
                # E2B natively supports Python via `run_code`. For Node/JS, we create a file.
                sandbox.filesystem.write("/home/user/script.js", code)
                execution = sandbox.commands.run("node /home/user/script.js", timeout=timeout)
            
            stdout_str = ""
            stderr_str = ""
            exit_code = 0

            # e2b_code_interpreter returns Execution object for run_code or CommandResult for commands.run
            if hasattr(execution, 'results'): # run_code
                stdout_str = "\n".join([str(res.text) for res in execution.results if hasattr(res, 'text')])
                stderr_str = execution.error.traceback if execution.error else ""
                exit_code = 1 if execution.error else 0
                
                # Also capture logs (prints)
                if execution.logs:
                    if execution.logs.stdout:
                        stdout_str += "\n" + "\n".join(execution.logs.stdout)
                    if execution.logs.stderr:
                        stderr_str += "\n" + "\n".join(execution.logs.stderr)

            else: # commands.run
                stdout_str = execution.stdout
                stderr_str = execution.stderr
                exit_code = execution.exit_code

            status = "✅ SUCCESS" if exit_code == 0 else "❌ FAILED"
            
            return (
                f"## 🐳 E2B Sandbox Execution ({lang})\n\n"
                f"**Status:** {status} (exit code: {exit_code})\n\n"
                f"### stdout\n```\n{stdout_str or '(no output)'}\n```\n\n"
                f"### stderr\n```\n{stderr_str or '(clean)'}\n```"
            )

    except Exception as e:
        if "Timeout" in str(e):
            return (
                f"## 🐳 E2B Sandbox Execution ({lang})\n\n"
                f"**Status:** ⏰ TIMEOUT (exceeded {timeout}s limit)\n\n"
                f"The code took too long to execute and was killed."
            )
        return f"❌ E2B Sandbox error: {e}"
