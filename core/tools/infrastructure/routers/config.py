"""
Configuration & Secrets Router
===============================
Handles all configuration management and secrets endpoints for Kenbun Mission Control.

Routes:
- GET  /api/v1/active-model       — Returns the currently active LLM model name.
- GET  /api/v1/config             — Reads .env and returns masked config values.
- POST /api/v1/config             — Atomically updates .env with validation, locking, and hot-reload.
- GET  /api/v1/secrets/status     — Checks if critical API keys are configured (no raw values).
- POST /api/v1/secrets/encrypt    — Encrypts a plain text value using the master key.
- POST /api/v1/secrets/update_env — Saves & auto-encrypts a secret key/value in .env atomically.
"""

import os
import re
import logging
import tempfile
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from tools.infrastructure.config import settings
from tools.infrastructure.server_deps import (
    verify_authorization,
    _encrypt_setting,
    project_root,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------

class ConfigUpdateRequest(BaseModel):
    settings: Dict[str, str]


class SecretEncryptRequest(BaseModel):
    plain_text: str = Field(..., min_length=1, description="The plain text secret value to encrypt")


class SecretUpdateEnvRequest(BaseModel):
    key: str = Field(..., min_length=1, description="The environment variable key name")
    value: str = Field(..., min_length=1, description="The value to store (encrypted if it contains credentials)")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/api/v1/active-model")
async def get_active_model():
    """Returns ONLY the currently active Primary LLM model name for secure frontend display."""
    try:
        from tools.infrastructure.config import settings
        return {"model": settings.models.primary_llm_model}
    except Exception:
        return {"model": "Ollama Llama3.2"}


@router.get("/api/v1/config")
async def get_config(request: Request):
    """Reads .env file and masks sensitive API keys with token authorization verification."""
    verify_authorization(request)
    env_path = project_root / ".env"
    config_data = {}

    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'").strip('"')

                    if "KEY" in key or "TOKEN" in key or "SECRET" in key:
                        val = "********" if val else ""

                    config_data[key] = val

    return {"status": "success", "config": config_data}


@router.post("/api/v1/config")
async def update_config(req: ConfigUpdateRequest, request: Request):
    """Safely and atomically updates .env variables with concurrency locking, validation, and metadata preservation."""

    # 0. Secure Token & Loopback Authentication
    verify_authorization(request)

    # 1. Check authorized keys against Pydantic model fields allowlist (including validation aliases)
    valid_fields = set()
    for field_name, field_info in settings.model_fields.items():
        valid_fields.add(field_name)
        if hasattr(field_info, "validation_alias") and field_info.validation_alias:
            from pydantic import AliasChoices, AliasPath
            if isinstance(field_info.validation_alias, str):
                valid_fields.add(field_info.validation_alias)
            elif isinstance(field_info.validation_alias, AliasChoices):
                for choice in field_info.validation_alias.choices:
                    if isinstance(choice, str):
                        valid_fields.add(choice)
                    elif isinstance(choice, AliasPath) and choice.path and isinstance(choice.path[0], str):
                        valid_fields.add(choice.path[0])
            elif isinstance(field_info.validation_alias, AliasPath) and field_info.validation_alias.path and isinstance(field_info.validation_alias.path[0], str):
                valid_fields.add(field_info.validation_alias.path[0])

    for key, val in req.settings.items():
        if key not in valid_fields:
            logging.error(f"UNAUTHORIZED CONFIG KEY: {key}")
            raise HTTPException(status_code=400, detail=f"Unauthorized configuration key: {key}")
        if "\n" in key or "\r" in key or "=" in key:
            raise HTTPException(status_code=400, detail="Invalid characters in key.")
        if "\n" in val or "\r" in val:
            raise HTTPException(status_code=400, detail="Invalid characters in value.")

    # 2. Trigger Pydantic validation BEFORE writing to disk or modifying os.environ
    try:
        # Create a dict of current settings values
        current_dict = {f: getattr(settings, f) for f in settings.model_fields}
        # Overlay proposed updates (skipping masked values)
        proposed_dict = {}
        for f in settings.model_fields:
            if f in req.settings:
                if req.settings[f] != "********":
                    proposed_dict[f] = req.settings[f]
                else:
                    proposed_dict[f] = current_dict[f]
            else:
                proposed_dict[f] = current_dict[f]

        # Trigger Pydantic class validation by instantiating a temporary model
        from tools.infrastructure.config import KenbunSettings
        # Construct and validate
        KenbunSettings(**proposed_dict)
    except Exception as e:
        logging.error(f"Config Validation Failure: {e}")
        raise HTTPException(status_code=400, detail="Invalid configuration parameters or validation failure.")

    env_path = project_root / ".env"
    lock_path = env_path.with_suffix(".lock")

    try:
        import fcntl
    except ImportError:
        fcntl = None
    try:
        import msvcrt
    except ImportError:
        msvcrt = None

    # 3. Acquire exclusive cross-process lock with secure resource cleanup
    lock_fd = None
    try:
        lock_fd = open(lock_path, "w")
        if fcntl:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        elif msvcrt:
            lock_fd.seek(0)
            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_LOCK, 1)
    except Exception:
        if lock_fd:
            try:
                lock_fd.close()
            except Exception:
                pass
        raise HTTPException(status_code=500, detail="Configuration lock acquisition failed.")

    try:
        lines = []
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        # Process existing lines
        updated_keys = set()
        new_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue

            if "=" in stripped:
                key = stripped.split("=")[0].strip()
                if key in req.settings:
                    # Only update if it's not masked
                    if req.settings[key] != "********":
                        enc_val = _encrypt_setting(key, req.settings[key])
                        new_lines.append(f"{key}={enc_val}\n")
                    else:
                        new_lines.append(line)
                    updated_keys.add(key)
                else:
                    new_lines.append(line)

        # Append new keys
        for key, val in req.settings.items():
            if key not in updated_keys and val != "********" and val.strip() != "":
                enc_val = _encrypt_setting(key, val)
                new_lines.append(f"{key}={enc_val}\n")

        # Get original permissions
        original_mode = os.stat(env_path).st_mode if env_path.exists() else 0o600

        # Write atomically using tempfile
        temp_fd, temp_path = tempfile.mkstemp(dir=project_root, prefix=".env.tmp")
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
                f.flush()
                os.fsync(f.fileno())

            # Preserve original permissions
            os.chmod(temp_path, original_mode)
            os.replace(temp_path, env_path)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise HTTPException(status_code=500, detail="Atomic write operation failed.")

    finally:
        # Release lock
        try:
            if fcntl:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            elif msvcrt:
                lock_fd.seek(0)
                msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
            lock_fd.close()
        except Exception:
            pass

    # 4. Hot-reload in current os.environ context (safe now since we verified validation passes)
    for key, val in req.settings.items():
        if val != "********" and val.strip() != "":
            os.environ[key] = val

    # Hot-reload specific components
    if "DAILY_BUDGET" in req.settings:
        try:
            from tools.strategy.token_governor import token_governor
            token_governor.daily_budget = float(req.settings["DAILY_BUDGET"])
        except Exception as e:
            logging.error(f"Failed to hot-reload budget: {e}")

    # Clear Pydantic's get_settings cache and hot-reload in-memory settings instance
    try:
        from tools.infrastructure.config import get_settings
        get_settings.cache_clear()

        # Instantiate a fresh settings model (will match our validated test)
        new_settings = get_settings()

        # Transfer validated fields safely to the global singleton settings instance
        for field in settings.model_fields:
            try:
                setattr(settings, field, getattr(new_settings, field))
            except Exception:
                pass
    except Exception as e:
        logging.error(f"Failed to hot-reload settings dynamically: {e}")

    return {"status": "success", "message": "Configuration updated successfully."}


# ---------------------------------------------------------------------------
# Secrets Routes
# ---------------------------------------------------------------------------

@router.get("/api/v1/secrets/status")
async def api_secrets_status():
    """
    Checks if critical keys are configured in settings or active .env file.
    Does NOT return actual decrypted or raw keys for security.
    """
    try:
        from tools.infrastructure.config import discover_env_file

        # Read directly from env file
        env_path = Path(discover_env_file())
        env_vars = {}
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    match = re.match(r"^\s*([A-Za-z0-9_]+)\s*=\s*(.*)$", line)
                    if match:
                        k = match.group(1)
                        val = match.group(2).strip()
                        if val:
                            env_vars[k] = val

        twentyone_key = settings.TWENTYONE_DEV_API_KEY.get_secret_value() if settings.TWENTYONE_DEV_API_KEY else None
        if not twentyone_key:
            twentyone_key = env_vars.get("TWENTYONE_DEV_API_KEY") or os.environ.get("TWENTYONE_DEV_API_KEY")

        return {
            "TWENTYONE_DEV_API_KEY": bool(twentyone_key)
        }
    except Exception as e:
        logging.error(f"Failed to check secret status: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Failed to check secret status."})


@router.post("/api/v1/secrets/encrypt", dependencies=[Depends(verify_authorization)])
async def api_encrypt_secret(payload: SecretEncryptRequest):
    """
    Encrypts a plain text value using the master key.
    """
    try:
        from tools.utils.secret_manager import encrypt_value
        return {"encrypted_text": f"enc:{encrypt_value(payload.plain_text)}"}
    except Exception as e:
        logging.error(f"Secret encryption failed: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Encryption failed."})


@router.post("/api/v1/secrets/update_env", dependencies=[Depends(verify_authorization)])
async def api_update_env_key(payload: SecretUpdateEnvRequest):
    """
    Saves and automatically encrypts a dynamic secret key/value in the active .env using atomic writes.
    """
    key = payload.key.strip()
    value = payload.value.strip()

    # Restrict keys to protect core system parameters
    allowed_keys = ["TWENTYONE_DEV_API_KEY", "GEMINI_API_KEY", "DEEPSEEK_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    if key not in allowed_keys:
        return JSONResponse(status_code=403, content={"error": f"Modifying key {key} is forbidden."})

    try:
        from tools.infrastructure.config import discover_env_file
        from tools.utils.secret_manager import encrypt_value

        env_path = Path(discover_env_file())
        final_value = value

        # Auto-encrypt keys that hold sensitive API access tokens
        if not value.startswith("enc:") and any(k in key.upper() for k in ["KEY", "PASSWORD", "TOKEN", "SECRET"]):
            final_value = f"enc:{encrypt_value(value)}"

        lines = []
        key_found = False
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        for i, line in enumerate(lines):
            # Matches optional spaces, the key name, optional spaces, and the equals sign
            if re.match(rf"^\s*{re.escape(key)}\s*=", line):
                lines[i] = f"{key}={final_value}\n"
                key_found = True
                break

        if not key_found:
            # Add line break if file does not end with one
            if lines and not lines[-1].endswith("\n"):
                lines.append("\n")
            lines.append(f"{key}={final_value}\n")

        # Atomic Write Pattern: Write to temp file then rename
        env_dir = env_path.parent
        if not env_dir.exists():
            env_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile("w", dir=env_dir, delete=False, encoding="utf-8") as temp_file:
            temp_path = Path(temp_file.name)
            try:
                temp_file.writelines(lines)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            except Exception as write_err:
                if temp_path.exists():
                    os.unlink(temp_path)
                raise write_err

        os.replace(temp_path, env_path)
        return {"status": "success", "message": f"Successfully updated and encrypted {key} in the .env file."}
    except Exception as e:
        logging.error(f"Failed to update .env: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Failed to update environment file."})


@router.get("/api/v1/config/schema")
async def get_config_schema(request: Request):
    """
    Returns the JSON Schema of KenbunSettings, organized into logical categories
    to power form rendering in the frontend settings view.
    """
    verify_authorization(request)
    try:
        from tools.infrastructure.config import KenbunSettings
        # Extract raw schema using pydantic's model_json_schema
        schema = KenbunSettings.model_json_schema()
        properties = schema.get("properties", {})
        
        # Categorized registry
        categories = {
            "Models": [],
            "Database": [],
            "Sensory & Voice": [],
            "Worker & Swarm": [],
            "Security": [],
            "Paths & Project": [],
            "Other": []
        }
        
        for field_name, prop in properties.items():
            field_info = {
                "name": field_name,
                "title": prop.get("title", field_name),
                "type": prop.get("type", "string"),
                "default": prop.get("default", None),
                "description": prop.get("description", ""),
                "enum": prop.get("enum", None)
            }
            
            # Categorize based on prefix or name
            upper_name = field_name.upper()
            if any(p in upper_name for p in ["MODEL", "LLM", "GEMINI", "DEEPSEEK", "ANTHROPIC", "OPENROUTER", "NOUS", "NVIDIA", "XAI", "ZHIPU", "KIMI", "MOONSHOT", "STEPFUN", "DASHSCOPE", "MIMO", "TOKENHUB"]):
                categories["Models"].append(field_info)
            elif any(p in upper_name for p in ["CHROMA", "SUPABASE", "POSTGRES", "DB", "SQLITE"]):
                categories["Database"].append(field_info)
            elif any(p in upper_name for p in ["TTS", "STT", "VOICE", "AUDIO", "SPEECH"]):
                categories["Sensory & Voice"].append(field_info)
            elif any(p in upper_name for p in ["WORKER", "SWARM", "PC_IP"]):
                categories["Worker & Swarm"].append(field_info)
            elif any(p in upper_name for p in ["SECURITY", "CRON_MODE", "APPROVAL", "SANDBOX", "HOOK"]):
                categories["Security"].append(field_info)
            elif any(p in upper_name for p in ["ROOT", "PATH", "DIR", "HOME", "VAULT"]):
                categories["Paths & Project"].append(field_info)
            else:
                categories["Other"].append(field_info)
                
        return {"status": "success", "schema": categories}
    except Exception as e:
        logging.error(f"Failed to generate config schema: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate configuration schema.")


@router.get("/api/v1/credentials/keys")
async def get_credentials_status(request: Request):
    """
    Returns a status list of all API keys / credentials, grouping them by category,
    indicating whether they are currently configured (True/False) without exposing the secret values.
    """
    verify_authorization(request)
    try:
        from tools.infrastructure.config import discover_env_file
        
        # Read from environment/settings or .env file
        env_path = Path(discover_env_file())
        env_vars = {}
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    match = re.match(r"^\s*([A-Za-z0-9_]+)\s*=\s*(.*)$", line)
                    if match:
                        k = match.group(1)
                        val = match.group(2).strip().strip("'").strip('"')
                        if val:
                            env_vars[k] = val

        # Populate a credential status dictionary
        credential_status = {}
        
        # Gather all model fields in KenbunSettings that represent credentials
        for field_name, field_field in settings.model_fields.items():
            upper_name = field_name.upper()
            is_secret = "SecretStr" in str(field_field.annotation) or any(p in upper_name for p in ["KEY", "TOKEN", "SECRET", "PASSWORD"])
            if is_secret:
                # Resolve value safely
                val = getattr(settings, field_name, None)
                if val:
                    # Unwrap SecretStr
                    val_str = val.get_secret_value() if hasattr(val, "get_secret_value") else str(val)
                else:
                    # Fallback to env or .env file
                    val_str = env_vars.get(field_name) or os.environ.get(field_name)
                
                credential_status[field_name] = {
                    "is_configured": bool(val_str and val_str != "********" and not val_str.startswith("enc:Error")),
                    "category": "LLM Providers" if any(p in upper_name for p in ["GEMINI", "DEEPSEEK", "ANTHROPIC", "OPENROUTER", "NOUS", "NVIDIA", "XAI", "ZHIPU", "KIMI", "MOONSHOT", "STEPFUN", "DASHSCOPE", "MIMO", "TOKENHUB"]) else "Integrations"
                }

        return {"status": "success", "credentials": credential_status}
    except Exception as e:
        logging.error(f"Failed to check credentials status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to check credentials status.")
