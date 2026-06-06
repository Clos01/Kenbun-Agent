import os
import re
import logging
from pathlib import Path
from typing import Dict
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.tools.infrastructure.config import settings, discover_env_file
from core.tools.infrastructure.auth import verify_authorization

router = APIRouter()
project_root = settings.PROJECT_ROOT

class ConfigUpdateRequest(BaseModel):
    settings: Dict[str, str]

class SecretEncryptRequest(BaseModel):
    plain_text: str

class SecretUpdateEnvRequest(BaseModel):
    key: str
    value: str

def _encrypt_setting(key: str, val: str) -> str:
    from core.tools.utils.secret_manager import encrypt_value
    if "KEY" in key or "TOKEN" in key or "SECRET" in key:
        if val and not val.startswith("enc:"):
            return "enc:" + encrypt_value(val)
    return val

@router.get("/api/v1/active-model")
async def get_active_model():
    """Returns ONLY the currently active Primary LLM model name for secure frontend display."""
    try:
        from core.tools.infrastructure.config import settings
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
    verify_authorization(request)
    
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

    try:
        current_dict = {f: getattr(settings, f) for f in settings.model_fields}
        proposed_dict = {}
        for f in settings.model_fields:
            if f in req.settings:
                if req.settings[f] != "********":
                    proposed_dict[f] = req.settings[f]
                else:
                    proposed_dict[f] = current_dict[f]
            else:
                proposed_dict[f] = current_dict[f]

        from core.tools.infrastructure.config import KenbunSettings
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
    import tempfile
    
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
                    if req.settings[key] != "********":
                        enc_val = _encrypt_setting(key, req.settings[key])
                        new_lines.append(f"{key}={enc_val}\n")
                    else:
                        new_lines.append(line)
                    updated_keys.add(key)
                else:
                    new_lines.append(line)
                    
        for key, val in req.settings.items():
            if key not in updated_keys and val != "********" and val.strip() != "":
                enc_val = _encrypt_setting(key, val)
                new_lines.append(f"{key}={enc_val}\n")
                
        original_mode = os.stat(env_path).st_mode if env_path.exists() else 0o600
        
        temp_fd, temp_path = tempfile.mkstemp(dir=project_root, prefix=".env.tmp")
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
                f.flush()
                os.fsync(f.fileno())
            
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
        try:
            if fcntl:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            elif msvcrt:
                lock_fd.seek(0)
                msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
            lock_fd.close()
        except Exception:
            pass
            
    for key, val in req.settings.items():
        if val != "********" and val.strip() != "":
            os.environ[key] = val
            
    if "DAILY_BUDGET" in req.settings:
        try:
            from core.tools.strategy.token_governor import token_governor
            token_governor.daily_budget = float(req.settings["DAILY_BUDGET"])
        except Exception as e:
            logging.error(f"Failed to hot-reload budget: {e}")
            
    try:
        from core.tools.infrastructure.config import get_settings
        get_settings.cache_clear()
        
        new_settings = get_settings()
        
        for field in settings.model_fields:
            try:
                setattr(settings, field, getattr(new_settings, field))
            except Exception:
                pass
    except Exception as e:
        logging.error(f"Failed to hot-reload settings dynamically: {e}")

    return {"status": "success", "message": "Configuration updated successfully."}


@router.get("/api/v1/secrets/status")
async def api_secrets_status():
    """
    Checks if critical keys are configured in settings or active .env file.
    Does NOT return actual decrypted or raw keys for security.
    """
    try:
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


@router.post("/api/v1/secrets/encrypt")
async def api_encrypt_secret(payload: SecretEncryptRequest):
    """
    Encrypts a plain text value using the master key.
    """
    try:
        from core.tools.utils.secret_manager import encrypt_value
        return {"encrypted_text": f"enc:{encrypt_value(payload.plain_text)}"}
    except Exception as e:
        logging.error(f"Secret encryption failed: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Encryption failed."})


@router.post("/api/v1/secrets/update_env")
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
        from core.tools.utils.secret_manager import encrypt_value
        import tempfile
        
        env_path = Path(discover_env_file())
        enc_value = f"enc:{encrypt_value(value)}"
        
        lines = []
        key_found = False
        
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
        for i, line in enumerate(lines):
            match = re.match(r"^\s*([A-Za-z0-9_]+)\s*=\s*(.*)$", line)
            if match and match.group(1) == key:
                lines[i] = f"{key}={enc_value}\n"
                key_found = True
                break
                
        if not key_found:
            if lines and not lines[-1].endswith("\n"):
                lines.append("\n")
            lines.append(f"{key}={enc_value}\n")
            
        original_mode = os.stat(env_path).st_mode if env_path.exists() else 0o600
        
        temp_fd, temp_path = tempfile.mkstemp(dir=str(env_path.parent), prefix=".env.tmp")
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                f.writelines(lines)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(temp_path, original_mode)
            os.replace(temp_path, env_path)
            
            # Hot reload
            os.environ[key] = enc_value
            
            return JSONResponse(status_code=200, content={"status": "success"})
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise
    except Exception as e:
        logging.error(f"Failed to update env key {key}: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Failed to update env."})
