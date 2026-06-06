import os
import logging
from fastapi import Request, HTTPException
from core.tools.infrastructure.config import settings

_cached_config_token = None

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
    token = os.getenv("CONFIG_TOKEN")
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
    Eliminates client-IP spoofing vulnerabilities by requiring cryptographic verification for all requests.
    """
    import secrets
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
