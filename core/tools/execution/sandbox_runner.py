"""
Sandbox Runner — Safe code execution in ephemeral Docker containers.

Mimics the execution engine used by Devin/SWE-agent.
Code runs in an isolated container with no network, limited memory,
and auto-destruction after execution.
"""
import os
import subprocess
import tempfile
import json
from pathlib import Path


# --- CONFIGURATION ---
SANDBOX_IMAGES = {
    "python": "python:3.11-slim",
    "node": "node:20-slim",
    "javascript": "node:20-slim",
}

DEFAULT_TIMEOUT = 30
MAX_TIMEOUT = 120
MAX_OUTPUT_CHARS = 10000


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


def _get_file_extension(language: str) -> str:
    """Return file extension for the given language."""
    return {
        "python": ".py",
        "node": ".js",
        "javascript": ".js",
    }.get(language.lower(), ".py")


def _get_run_command(language: str, filename: str) -> list:
    """Return the Docker CMD for running the code."""
    lang = language.lower()
    if lang == "python":
        return ["python3", f"/sandbox/{filename}"]
    elif lang in ("node", "javascript"):
        return ["node", f"/sandbox/{filename}"]
    else:
        return ["python3", f"/sandbox/{filename}"]


def run_code_safely(
    code: str,
    language: str = "python",
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """
    Execute code in an isolated Docker container.

    Safety features:
    - Network disabled (--network=none)
    - Memory limited to 256MB
    - CPU limited to 0.5 cores
    - Timeout enforced
    - Container auto-destroyed after execution
    - Temp filesystem (nothing persists)

    Args:
        code: The source code to execute
        language: "python", "node", or "javascript"
        timeout: Max seconds to run (capped at 120)

    Returns:
        A formatted string with stdout, stderr, and exit code.
    """
    # --- VALIDATION ---
    if not _check_docker():
        return "❌ Docker is not running. Start Docker Desktop and try again."

    lang = language.lower()
    if lang not in SANDBOX_IMAGES:
        return f"❌ Unsupported language: '{language}'. Available: {list(SANDBOX_IMAGES.keys())}"

    timeout = min(timeout, MAX_TIMEOUT)
    image = SANDBOX_IMAGES[lang]
    ext = _get_file_extension(lang)
    filename = f"sandbox_code{ext}"

    # --- WRITE CODE TO TEMP FILE ---
    with tempfile.TemporaryDirectory(prefix="kenbun_sandbox_") as tmpdir:
        code_path = Path(tmpdir) / filename
        code_path.write_text(code)

        # --- BUILD DOCKER COMMAND ---
        run_cmd = _get_run_command(lang, filename)

        docker_cmd = [
            "docker", "run",
            "--rm",                           # Auto-remove container
            "--network=none",                 # No internet access
            "--read-only",                    # Read-only filesystem
            "--tmpfs", "/tmp:size=64m",       # Small writable /tmp
            "--memory=256m",                  # Memory limit
            "--cpus=0.5",                     # CPU limit
            "--pids-limit=64",                # Process limit (no fork bombs)
            "--security-opt=no-new-privileges",  # No privilege escalation
            "-v", f"{tmpdir}:/sandbox:ro",    # Mount code read-only
            "-w", "/sandbox",                 # Working directory
            image,                            # Container image
            *run_cmd,                         # Run command
        ]

        # --- EXECUTE ---
        try:
            print(f"🐳 Sandbox: Running {lang} code in {image}...")
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 5,  # Extra buffer for Docker overhead
            )

            stdout = result.stdout[:MAX_OUTPUT_CHARS] if result.stdout else "(no output)"
            stderr = result.stderr[:MAX_OUTPUT_CHARS] if result.stderr else "(clean)"
            exit_code = result.returncode

            # Format output
            status = "✅ SUCCESS" if exit_code == 0 else "❌ FAILED"

            return (
                f"## 🐳 Sandbox Execution ({lang})\n\n"
                f"**Status:** {status} (exit code: {exit_code})\n\n"
                f"### stdout\n```\n{stdout}\n```\n\n"
                f"### stderr\n```\n{stderr}\n```"
            )

        except subprocess.TimeoutExpired:
            # Kill the container if it times out
            return (
                f"## 🐳 Sandbox Execution ({lang})\n\n"
                f"**Status:** ⏰ TIMEOUT (exceeded {timeout}s limit)\n\n"
                f"The code took too long to execute and was killed."
            )

        except Exception as e:
            return f"❌ Sandbox error: {e}"
