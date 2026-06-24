import requests
import json
import logging
import urllib.request
import urllib.error
import os
from typing import List, Optional, Tuple
from tools.infrastructure.config import settings
from tools.utils.secret_manager import decrypt_value

def _lmstudio_server_root(base_url: Optional[str]) -> Optional[str]:
    """Strip `/v1` suffix from a base URL to get the native API root."""
    root = (base_url or "").strip().rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3].rstrip("/")
    return root or None

def _lmstudio_request_headers(api_key: Optional[str] = None) -> dict:
    """Build HTTP headers for LM Studio native API requests."""
    headers = {"User-Agent": "Kenbun-Agent/1.0"}
    token = str(api_key or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def _lmstudio_fetch_raw_models(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 3.0,
) -> Optional[list]:
    """Fetch raw model list from LM Studio's `/api/v1/models`."""
    server_root = _lmstudio_server_root(base_url)
    if not server_root:
        return None

    headers = _lmstudio_request_headers(api_key)
    url = server_root + "/api/v1/models"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except Exception as exc:
        logging.debug(f"LM Studio probe at {url} failed: {exc}")
        return None

    raw_models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(raw_models, list):
        return None
    return raw_models

def probe_lmstudio_models(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 3.0,
) -> Optional[List[str]]:
    """Probe LM Studio's model listing. Filters out embedding models."""
    raw_models = _lmstudio_fetch_raw_models(api_key=api_key, base_url=base_url, timeout=timeout)
    if raw_models is None:
        return None

    keys = []
    for raw in raw_models:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("type") or "").strip().lower() == "embedding":
            continue
        key = str(raw.get("key") or raw.get("id") or "").strip()
        if key and key not in keys:
            keys.append(key)
    return keys

def probe_openai_models(base_url: str, api_key: Optional[str] = None, timeout: float = 3.0) -> Optional[List[str]]:
    """Generic probe for OpenAI-compatible /v1/models endpoints."""
    root = (base_url or "").strip().rstrip("/")
    url = root + "/models" if root.endswith("/v1") else root + "/v1/models"
    headers = {"User-Agent": "Kenbun-Agent/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            models = data.get("data", [])
            if isinstance(models, list):
                keys = []
                for m in models:
                    mid = str(m.get("id", "")).strip()
                    if mid and "embed" not in mid.lower():
                        keys.append(mid)
                return keys
    except Exception as e:
        logging.debug(f"OpenAI /v1/models probe failed at {url}: {e}")
    return None

def ensure_lmstudio_model_loaded(
    model: str,
    base_url: Optional[str],
    api_key: Optional[str] = None,
    target_context_length: int = 8192,
    timeout: float = 60.0,
) -> Optional[int]:
    """Ensure LM Studio has `model` loaded with at least `target_context_length` context."""
    server_root = _lmstudio_server_root(base_url)
    if not server_root:
        return None

    try:
        raw_models = _lmstudio_fetch_raw_models(api_key=api_key, base_url=base_url, timeout=5.0)
    except Exception:
        raw_models = None
    if raw_models is None:
        return None

    target_entry = None
    for raw in raw_models:
        if not isinstance(raw, dict):
            continue
        if raw.get("key") == model or raw.get("id") == model:
            target_entry = raw
            break
    if target_entry is None:
        return None

    max_ctx = target_entry.get("max_context_length")
    if isinstance(max_ctx, int) and max_ctx > 0:
        target_context_length = min(target_context_length, max_ctx)

    for inst in target_entry.get("loaded_instances") or []:
        cfg = inst.get("config") if isinstance(inst, dict) else None
        loaded_ctx = cfg.get("context_length") if isinstance(cfg, dict) else None
        if isinstance(loaded_ctx, int) and loaded_ctx >= target_context_length:
            return loaded_ctx

    # Load model
    body = json.dumps({
        "model": model,
        "context_length": target_context_length,
    }).encode()
    load_headers = _lmstudio_request_headers(api_key)
    load_headers["Content-Type"] = "application/json"
    load_url = server_root + "/api/v1/models/load"
    try:
        req = urllib.request.Request(
            load_url,
            data=body,
            headers=load_headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
    except Exception as e:
        logging.warning(f"Failed to load model {model} in LM Studio: {e}")
        return None
    return target_context_length

def resolve_google_endpoint_and_model(
    base_url: str,
    model_name: str,
    api_key_set: bool = False,
    project_id: Optional[str] = None
) -> Tuple[str, str]:
    """
    Dynamically rewrites legacy/placeholder Google Cloud Code Assist URL
    and model name to production-ready Gemini endpoints.
    """
    if "cloudaidoc-pa.googleapis.com" not in base_url:
        return base_url, model_name

    # If API key is set, use Google AI Studio endpoint
    if api_key_set:
        rewritten_url = "https://generativelanguage.googleapis.com/v1beta/openai"
        rewritten_model = "gemini-1.5-pro" if model_name == "code-assist" else model_name
        return rewritten_url, rewritten_model

    # If no API key, use Vertex AI endpoint with OAuth
    resolved_project = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT") or os.environ.get("PROJECT_ID")
    if not resolved_project:
        # Check if project-specific credentials JSON exists in project root
        from tools.utils.path_utils import get_project_root
        proj_creds_path = get_project_root() / ".google_credentials.json"
        if proj_creds_path.exists():
            try:
                import json
                with open(proj_creds_path, "r") as f:
                    creds_data = json.load(f)
                    resolved_project = creds_data.get("project_id") or creds_data.get("quota_project_id")
            except Exception:
                pass

    if not resolved_project:
        try:
            import google.auth
            _, resolved_project = google.auth.default()
        except Exception:
            pass

    if resolved_project:
        location = os.environ.get("VERTEX_AI_LOCATION") or os.environ.get("GOOGLE_CLOUD_REGION") or "us-central1"
        rewritten_url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{resolved_project}/locations/{location}/endpoints/openapi"
        rewritten_model = "google/gemini-1.5-pro-001" if model_name == "code-assist" else model_name
        return rewritten_url, rewritten_model
    else:
        # Fallback to AI Studio
        rewritten_url = "https://generativelanguage.googleapis.com/v1beta/openai"
        rewritten_model = "gemini-1.5-pro" if model_name == "code-assist" else model_name
        return rewritten_url, rewritten_model

def _make_openai_compatible_call(
    base_url: str,
    model_name: str,
    system_prompt: str,
    user_message: str,
    temperature: float = 0.1,
    max_tokens: int = 4000
) -> Optional[str]:
    # Resolve dynamic Google URL/Model rewrites
    base_url, model_name = resolve_google_endpoint_and_model(
        base_url, model_name, api_key_set=bool(settings.GEMINI_API_KEY)
    )

    # Formulate endpoint
    url = f"{base_url}/chat/completions"
    
    # Build headers with security keys dynamically
    headers = {"Content-Type": "application/json"}
    
    # Resolve Authorization dynamically
    api_key = None
    if "api.openai.com" in base_url and settings.OPENAI_API_KEY:
        api_key = decrypt_value(settings.OPENAI_API_KEY.get_secret_value())
    elif "api.deepseek.com" in base_url and settings.DEEPSEEK_API_KEY:
        api_key = decrypt_value(settings.DEEPSEEK_API_KEY.get_secret_value())
    elif "openrouter.ai" in base_url and hasattr(settings, "OPENROUTER_API_KEY") and settings.OPENROUTER_API_KEY:
        api_key = decrypt_value(settings.OPENROUTER_API_KEY.get_secret_value())
    elif "nous.mesolitica.com" in base_url and hasattr(settings, "NOUS_PORTAL_API_KEY") and settings.NOUS_PORTAL_API_KEY:
        api_key = decrypt_value(settings.NOUS_PORTAL_API_KEY.get_secret_value())
    elif "nvidia" in base_url and hasattr(settings, "NVIDIA_API_KEY") and settings.NVIDIA_API_KEY:
        api_key = decrypt_value(settings.NVIDIA_API_KEY.get_secret_value())
    elif "x.ai" in base_url and hasattr(settings, "XAI_API_KEY") and settings.XAI_API_KEY:
        api_key = decrypt_value(settings.XAI_API_KEY.get_secret_value())
    elif "bigmodel.cn" in base_url and hasattr(settings, "ZHIPU_API_KEY") and settings.ZHIPU_API_KEY:
        api_key = decrypt_value(settings.ZHIPU_API_KEY.get_secret_value())
    elif "api.kimi.com" in base_url and hasattr(settings, "KIMI_API_KEY") and settings.KIMI_API_KEY:
        api_key = decrypt_value(settings.KIMI_API_KEY.get_secret_value())
    elif "api.moonshot.cn" in base_url and hasattr(settings, "MOONSHOT_API_KEY") and settings.MOONSHOT_API_KEY:
        api_key = decrypt_value(settings.MOONSHOT_API_KEY.get_secret_value())
    elif "stepfun.com" in base_url and hasattr(settings, "STEPFUN_API_KEY") and settings.STEPFUN_API_KEY:
        api_key = decrypt_value(settings.STEPFUN_API_KEY.get_secret_value())
    elif "dashscope" in base_url and hasattr(settings, "DASHSCOPE_API_KEY") and settings.DASHSCOPE_API_KEY:
        api_key = decrypt_value(settings.DASHSCOPE_API_KEY.get_secret_value())
    elif "api.mimo.xiaomi.com" in base_url and hasattr(settings, "MIMO_API_KEY") and settings.MIMO_API_KEY:
        api_key = decrypt_value(settings.MIMO_API_KEY.get_secret_value())
    elif "tokenhub.tencentmaas.com" in base_url and hasattr(settings, "TOKENHUB_API_KEY") and settings.TOKENHUB_API_KEY:
        api_key = decrypt_value(settings.TOKENHUB_API_KEY.get_secret_value())
    elif "api-inference.huggingface.co" in base_url and hasattr(settings, "HF_API_KEY") and settings.HF_API_KEY:
        api_key = decrypt_value(settings.HF_API_KEY.get_secret_value())
    elif "generativelanguage.googleapis.com" in base_url and settings.GEMINI_API_KEY:
        api_key = decrypt_value(settings.GEMINI_API_KEY.get_secret_value())
    elif "cloudaidoc-pa.googleapis.com" in base_url or "googleapis.com" in base_url:
        if settings.GEMINI_API_KEY:
            api_key = decrypt_value(settings.GEMINI_API_KEY.get_secret_value())
        else:
            try:
                from google.auth.transport.requests import Request as AuthRequest
                from tools.utils.path_utils import get_project_root
                proj_creds_path = get_project_root() / ".google_credentials.json"
                
                if proj_creds_path.exists():
                    from google.oauth2.credentials import Credentials
                    credentials = Credentials.from_authorized_user_file(str(proj_creds_path))
                    credentials.refresh(AuthRequest())
                    api_key = credentials.token
                    logging.info("Successfully acquired Google OAuth access token via custom client credentials")
                else:
                    import google.auth
                    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
                    credentials, project_id = google.auth.default(scopes=scopes)
                    credentials.refresh(AuthRequest())
                    api_key = credentials.token
                    logging.info("Successfully acquired Google OAuth access token via ADC")
            except Exception as oauth_err:
                logging.warning(f"Failed to acquire Google OAuth access token: {oauth_err}")
        
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        
    if "api.anthropic.com" in base_url and settings.ANTHROPIC_API_KEY:
        # Handle Anthropic custom gateway mapping
        headers["x-api-key"] = decrypt_value(settings.ANTHROPIC_API_KEY.get_secret_value())
        headers["anthropic-version"] = "2023-06-01"
        
        # Map Anthropic request format
        payload = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": f"{system_prompt}\n\n{user_message}"}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        url = f"{base_url}/messages"
        response = requests.post(url, json=payload, headers=headers, timeout=settings.models.lm_studio_read_timeout)
        response.raise_for_status()
        res_json = response.json()
        content = res_json["content"][0]["text"]
        
        # Dynamic Token Tracking (System 4)
        try:
            usage = res_json.get("usage", {})
            in_t = usage.get("input_tokens", 0)
            out_t = usage.get("output_tokens", 0)
            from tools.strategy.token_governor import token_governor
            token_governor.track_usage(model_name, in_t, out_t, "anthropic_call")
        except Exception as e:
            logging.debug(f"Token Governor failed to track Anthropic usage: {e}")
            
        return content
        
    # Standard OpenAI payload
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    response = requests.post(url, json=payload, headers=headers, timeout=settings.models.lm_studio_read_timeout)
    response.raise_for_status()
    res_json = response.json()
    content = res_json["choices"][0]["message"]["content"]
    
    # Dynamic Token Tracking (System 4)
    try:
        usage = res_json.get("usage", {})
        in_t = usage.get("prompt_tokens", 0)
        out_t = usage.get("completion_tokens", 0)
        from tools.strategy.token_governor import token_governor
        token_governor.track_usage(model_name, in_t, out_t, "openai_call")
    except Exception as e:
        logging.debug(f"Token Governor failed to track OpenAI/Gemini usage: {e}")
        
    return content

def call_llm_gateway(system_prompt: str, user_message: str, temperature: float = 0.1, max_tokens: int = 4000) -> str:
    """
    Standardized, hardware-agnostic LLM router.
    Routes queries to PRIMARY_LLM_URL and falls back to FALLBACK_LLM_URL upon failure.
    Supports local Ollama/LM Studio and cloud gateways (OpenAI, Anthropic, Gemini).
    """
    primary_url = settings.PRIMARY_LLM_URL or "http://localhost:11434/v1"
    primary_model = settings.PRIMARY_LLM_MODEL or "llama3.2:3b"
    fallback_url = settings.FALLBACK_LLM_URL or ""
    fallback_model = settings.FALLBACK_LLM_MODEL or ""
    
    # Auto-resolve models from OpenAI-compatible local servers (LM Studio / Ollama)
    def resolve_auto_model(url: str, model: str) -> str:
        if not model or model.lower() == "auto":
            try:
                models = probe_openai_models(base_url=url, timeout=3.0)
                if models:
                    logging.info(f"✨ Auto-resolved model for {url}: {models[0]}")
                    return models[0]
            except Exception as e:
                logging.warning(f"Auto-model resolution failed for {url}: {e}")
            return "local-model"  # generic fallback
        return model

    primary_model = resolve_auto_model(primary_url, primary_model)
    if fallback_url:
        fallback_model = resolve_auto_model(fallback_url, fallback_model)
    
    # Dynamic Budget-Aware Swapping (System 4)
    try:
        from tools.strategy.token_governor import token_governor
        resolved_model = token_governor.get_budget_aware_model(primary_model)
        if resolved_model != primary_model:
            logging.info(f"📉 Budget Governor dynamically swapped model '{primary_model}' ➔ '{resolved_model}'")
            primary_model = resolved_model
            # If forced to local, prefer the user's configured PRIMARY_LLM_URL.
            # Only fall back to the docker-internal `ollama_server` hostname when
            # PRIMARY_LLM_URL is unset — otherwise we'd clobber an externally
            # reachable endpoint (e.g. http://127.0.0.1:11434/v1 on the host)
            # with a name that only resolves on the compose network.
            if primary_model == "local":
                if not settings.PRIMARY_LLM_URL:
                    primary_url = "http://ollama_server:11434/v1"
                primary_model = "llama3.2:1b"
    except Exception as e:
        logging.warning(f"Failed to resolve budget-aware model from TokenGovernor: {e}")
    
    # Clean trailing slash in URLs
    if primary_url and primary_url.endswith("/"):
        primary_url = primary_url[:-1]
    if fallback_url and fallback_url.endswith("/"):
        fallback_url = fallback_url[:-1]
        
    # Attempt an endpoint; treat empty/whitespace content as a failure so the
    # caller falls back instead of silently returning None (e.g. a reasoning
    # model that spends its whole token budget on `reasoning_content`).
    def _try_endpoint(url: str, model: str, label: str) -> str:
        if not url:
            raise RuntimeError(f"{label} endpoint not configured")
        try:
            is_lmstudio = (
                "127.0.0.1" in url
                or "localhost" in url
                or "lmstudio" in url.lower()
                or (settings.SWARM_PC_IP and settings.SWARM_PC_IP in url)
                or str(settings.models.lm_studio_port) in url
                or "lg2025" in url.lower()
            )
            if is_lmstudio:
                ensure_lmstudio_model_loaded(
                    model, url, timeout=settings.models.lm_studio_read_timeout
                )
        except Exception as pre_err:
            logging.debug(f"LM Studio pre-load failed or skipped for {label.lower()}: {pre_err}")
        content = _make_openai_compatible_call(
            url, model, system_prompt, user_message, temperature, max_tokens
        )
        if not content or not str(content).strip():
            raise RuntimeError(f"{label} endpoint returned empty content")
        return content

    # Try Primary, then Fallback. Either an exception OR empty content advances
    # to the next endpoint; if both fail we raise (never silently return None).
    logging.info(f"🔮 LLM_ROUTER: Attempting Primary Endpoint: {primary_url} ({primary_model})")
    try:
        return _try_endpoint(primary_url, primary_model, "Primary")
    except Exception as primary_err:
        logging.warning(
            f"⚠️ LLM_ROUTER: Primary failed: {primary_err}. "
            f"Attempting Fallback: {fallback_url} ({fallback_model})"
        )
        try:
            return _try_endpoint(fallback_url, fallback_model, "Fallback")
        except Exception as fallback_err:
            try:
                logging.warning("⚠️ LLM_ROUTER: Both OpenAI primary/fallback failed. Attempting native Google GenAI SDK fallback...")
                from tools.audit.gemini_reviewer import _call_gemini
                return _call_gemini(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    temperature=temperature,
                    model_override=None
                )
            except Exception as gemini_err:
                error_msg = (
                    f"❌ LLM_ROUTER CRITICAL: All endpoints failed (Primary, Fallback, and Native Gemini). "
                    f"Primary error: {primary_err}. Fallback error: {fallback_err}. Native Gemini error: {gemini_err}"
                )
                logging.error(error_msg)
                raise RuntimeError(error_msg)

