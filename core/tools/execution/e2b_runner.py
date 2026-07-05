"""
E2B Runner — Safe code execution in remote microVMs or local Docker fallback.

Replaces local Docker sandboxing with E2B's secure, cloud-hosted microVMs.
If E2B_API_KEY is missing, gracefully falls back to local Docker sandboxing.
"""
import os
import subprocess
import logging

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
DEFAULT_TIMEOUT_SEC = 60

SANDBOX_IMAGES = {
    "python": "python:3.11-slim",
    "node": "node:20-slim",
    "javascript": "node:20-slim",
}

def _check_docker():
    """Verify Docker is available and running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False

def _get_stdin_command(language: str) -> list:
    """Return the interpreter command that reads the program from stdin."""
    lang = language.lower()
    if lang == "python":
        return ["python3", "-"]   # `-` => read script from stdin
    elif lang in ("node", "javascript"):
        return ["node"]           # node executes piped stdin when not a TTY
    else:
        return ["python3", "-"]

def _run_docker_safely(
    code: str,
    language: str = "python",
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> str:
    """Execute code in an isolated local Docker container (Free offline fallback).

    The program is streamed to the interpreter via stdin rather than bind-mounted
    from a host directory. A bind mount (``-v {tmpdir}:/sandbox``) is resolved by
    the Docker *daemon's* filesystem, which differs from this process's filesystem
    whenever Kenbun runs inside a container talking to the host's docker.sock
    (docker-out-of-docker). In that setup the temp dir written here does not exist
    on the host, so an empty dir was mounted and the script was "not found".
    Piping via stdin avoids host paths entirely and keeps the container read-only.
    """
    if not _check_docker():
        return (
            "❌ Sandbox Failed: Neither E2B_API_KEY is set nor is local Docker daemon accessible.\n"
            "To resolve:\n"
            "1. Either add E2B_API_KEY=sk_... to your .env file to use the cloud sandbox,\n"
            "2. Or ensure Docker is running and /var/run/docker.sock is mounted into the container."
        )

    lang = language.lower()
    if lang not in SANDBOX_IMAGES:
        return f"❌ Unsupported language for local sandbox: '{language}'."

    image = SANDBOX_IMAGES[lang]
    run_cmd = _get_stdin_command(lang)

    docker_cmd = [
        "docker", "run",
        "--rm",                           # Auto-remove container
        "-i",                             # Keep stdin open so we can pipe the code
        "--network=none",                 # No internet access
        "--read-only",                    # Read-only filesystem
        "--tmpfs", "/tmp:size=64m",       # Small writable /tmp
        "--memory=256m",                  # Memory limit
        "--cpus=0.5",                     # CPU limit
        "--pids-limit=64",                # Process limit (no fork bombs)
        "--security-opt=no-new-privileges",  # No privilege escalation
        image,                            # Container image
        *run_cmd,                         # Interpreter reading from stdin
    ]

    try:
        logger.info(f"🐳 Fallback Sandbox: Running local Docker container with {image}...")
        result = subprocess.run(
            docker_cmd,
            input=code,                   # Stream the program to the interpreter
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )

        stdout = result.stdout[:10000] if result.stdout else "(no output)"
        stderr = result.stderr[:10000] if result.stderr else "(clean)"
        exit_code = result.returncode
        status = "✅ SUCCESS" if exit_code == 0 else "❌ FAILED"

        return (
            f"## 🐳 Local Docker Sandbox Execution ({lang})\n\n"
            f"**Status:** {status} (exit code: {exit_code})\n\n"
            f"### stdout\n```\n{stdout}\n```\n\n"
            f"### stderr\n```\n{stderr}\n```"
        )

    except subprocess.TimeoutExpired:
        return (
            f"## 🐳 Local Docker Sandbox Execution ({lang})\n\n"
            f"**Status:** ⏰ TIMEOUT (exceeded {timeout}s limit)\n\n"
            f"The code took too long to execute and was killed."
        )
    except Exception as e:
        return f"❌ Local Docker Sandbox error: {e}"

def _run_on_host(
    code: str,
    language: str = "python",
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> str:
    """Execute code directly on the host machine using subprocess."""
    import sys
    import tempfile
    from tools.utils.path_utils import get_project_root
    
    lang = language.lower()
    suffix = ".py" if lang == "python" else ".js"
    interpreter = [sys.executable] if lang == "python" else ["node"]
    
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode="w", encoding="utf-8") as temp_file:
        temp_file.write(code)
        temp_file_path = temp_file.name
        
    try:
        # Include the project root and core in PYTHONPATH for python execution
        env = os.environ.copy()
        root = get_project_root()
        env["PYTHONPATH"] = f"{root}:{root}/core:{env.get('PYTHONPATH', '')}"
        
        result = subprocess.run(
            interpreter + [temp_file_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(root),
            env=env
        )
        
        stdout = result.stdout[:10000] if result.stdout else "(no output)"
        stderr = result.stderr[:10000] if result.stderr else "(clean)"
        exit_code = result.returncode
        status = "✅ SUCCESS" if exit_code == 0 else "❌ FAILED"
        
        return (
            f"## 💻 Host Execution ({lang})\n\n"
            f"**Status:** {status} (exit code: {exit_code})\n\n"
            f"### stdout\n```\n{stdout}\n```\n\n"
            f"### stderr\n```\n{stderr}\n```"
        )
    except subprocess.TimeoutExpired:
        return f"❌ Host Execution: ⏰ TIMEOUT (exceeded {timeout}s limit)"
    except Exception as e:
        return f"❌ Host Execution error: {e}"
    finally:
        try:
            os.unlink(temp_file_path)
        except Exception:
            pass

def run_code_safely(
    code: str,
    language: str = "python",
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> str:
    """
    Execute code in a secure E2B remote microVM, with local Docker fallback.
    """
    from tools.infrastructure.config import settings
    if settings.security.sandbox_mode == "host":
        return _run_on_host(code, language, timeout)

    e2b_api_key = os.getenv("E2B_API_KEY")
    if not e2b_api_key:
        # Graceful fallback to local Docker container execution
        return _run_docker_safely(code, language, timeout)

    lang = language.lower()
    if lang not in ("python", "javascript", "node"):
        return f"❌ Unsupported language: '{language}'."

    try:
        from e2b_code_interpreter import Sandbox
        # Launch a dedicated, ephemeral sandbox VM for this execution
        with Sandbox.create(api_key=e2b_api_key) as sandbox:
            
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
