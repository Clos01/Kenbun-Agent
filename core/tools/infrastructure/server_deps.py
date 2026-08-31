import os
import asyncio
import logging
from pathlib import Path
from fastapi import Request, HTTPException

from tools.infrastructure.config import settings

project_root = settings.PROJECT_ROOT

# Shared File Paths
LOG_FILE = project_root / "brain_health" / "live_telemetry.json"
TASKS_FILE = project_root / "brain_health" / "swarm_tasks.json"
BENCHMARKS_FILE = project_root / "brain_health" / "BENCHMARKS.json"

# Projects to scan for AG_TASKS.md

_cached_config_token = None
_signals_count_cache = 0

def get_or_create_config_token() -> str:
    """
    Retrieves or generates a secure hex token.
    Prioritizes environment-based secret injection for absolute secure secret management (Least Privilege).
    Falls back to a securely restricted file within the private application directory with strict caching.
    Fails closed immediately if paths are misconfigured to guarantee system integrity.
    """
    global _cached_config_token
    if _cached_config_token is not None:
        return _cached_config_token

    # 1. Prioritize secure Environment-Based Secret Injection (Least Privilege)
    token = getattr(settings, "CONFIG_TOKEN", None) or os.getenv("CONFIG_TOKEN")
    if token:
        _cached_config_token = token
        return token

    # 2. Secure file-based fallback (FAIL-CLOSED if directory is missing)
    if not settings.BRAIN_HEALTH_DIR:
        raise RuntimeError("CRITICAL FAIL-CLOSED: settings.BRAIN_HEALTH_DIR is unconfigured or missing. Access denied.")

    token_file = settings.BRAIN_HEALTH_DIR / "config_token.secret"

    if token_file.exists():
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                token = f.read().strip()
                if token:
                    _cached_config_token = token
                    return token
        except Exception as e:
            logging.error(f"Failed to read config token file: {e}")
            raise RuntimeError(f"CRITICAL FAIL-CLOSED: Secure config token unreadable: {e}")

    # Generate a secure fallback token in memory if no environment variable or file is present
    import secrets
    token = secrets.token_hex(32)
    try:
        import tempfile
        fd, temp_path = tempfile.mkstemp(dir=str(settings.BRAIN_HEALTH_DIR), prefix=".token.tmp")
        try:
            os.chmod(temp_path, 0o600)  # Restrict permissions immediately (race-free)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(token)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, token_file)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise
    except Exception as e:
        logging.error(f"Failed to store fallback config token: {e}")
        raise RuntimeError(f"CRITICAL FAIL-CLOSED: Failed to initialize secure configuration key: {e}")

    _cached_config_token = token
    return token



def verify_authorization(request: Request):
    """
    Enforces strict Bearer token authorization for configuration endpoints.
    Allows internal loopback/Docker network requests while requiring cryptographic verification for external calls.
    """
    import secrets
    client_ip = request.client.host if request.client else ""
    if client_ip in ("127.0.0.1", "localhost", "100.100.199.127") or client_ip.startswith("172."):
        return

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Missing or invalid Authorization header. Cryptographic Bearer token is required."
        )

    provided_token = auth_header.split(" ", 1)[1].strip()
    try:
        expected_token = get_or_create_config_token()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not expected_token or not secrets.compare_digest(provided_token, expected_token):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Invalid cryptographic authorization token."
        )



async def update_signals_count_task():
    """Background task to scaleably and verifiably update the signals count without blocking the event loop."""
    global _signals_count_cache
    while True:
        try:
            if settings.BRAIN_HEALTH_DIR:
                routing_history_path = settings.BRAIN_HEALTH_DIR / "routing_history.jsonl"
                if routing_history_path.exists():
                    # Count lines in a non-blocking background thread (eliminates DoS blocking vector)
                    count = await asyncio.to_thread(_count_lines_sync, routing_history_path)
                    _signals_count_cache = count
        except Exception as e:
            logging.error(f"Error updating signals count: {e}")
        await asyncio.sleep(30)


def _count_lines_sync(file_path: Path) -> int:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def _encrypt_setting(key: str, val: str) -> str:
    from tools.utils.secret_manager import encrypt_value
    if "KEY" in key or "TOKEN" in key or "SECRET" in key:
        if val and not val.startswith("enc:"):
            return "enc:" + encrypt_value(val)
    return val


def execute_cli_command(command: str) -> str:
    """
    Safely executes a CLI command on the user's hardware.

    Hardened (chore/security-spring-cleaning):
      * No shell. ``shell=True`` has been removed.
      * Command is parsed with ``shlex.split`` and dispatched as an argv list.
      * argv[0] must be in ``tools.utils.safe_exec.ALLOWED_BINARIES``.
      * Shell metacharacters (``;``, ``&&``, ``|``, backtick, ``$()``, ``>``…)
        in the raw string cause an immediate refusal.

    The previous ``is_yolo_safe`` substring filter is intentionally NOT used:
    it inspected *shell* strings, which is fragile. The argv allowlist below
    is strictly stronger because the shell is never invoked.

    DSH-02 s2: dispatched through the ``shell`` capability seam
    (``tools.execution.shell``) rather than ``safe_run`` directly, so an operator
    can point this at a sandbox provider for a session without touching this code.
    The default ``local`` provider *is* ``safe_run`` -- identical behaviour.
    """
    from tools.execution.shell import shell

    try:
        res = shell.run(command, cwd=str(settings.PROJECT_ROOT), timeout=30.0)
    except FileNotFoundError as e:
        return f"❌ Error: Binary not found: {e}"
    except Exception as e:  # noqa: BLE001 -- surface any provider failure to the caller
        return f"❌ Error: Command execution failed: {e}"

    if res.blocked:
        return f"❌ Security Violation: {res.stderr or 'blocked by allowlist'}"
    if res.timed_out:
        return "❌ Error: Command execution timed out after 30 seconds."

    output = res.stdout or ""
    if res.stderr:
        output += f"\n{res.stderr}"

    # Scrub secrets defensively before returning command output to client
    from scripts.terminal_chat import scrub_secrets
    output = scrub_secrets(output)

    if not output.strip():
        output = f"Command completed with exit code {res.exit_code}."
    return f"```\n{output}\n```"

