import os
import requests
import json
import logging
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional
from tools.infrastructure.config import settings

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

def _make_openai_compatible_call(
    base_url: str,
    model_name: str,
    system_prompt: str,
    user_message: str,
    temperature: float = 0.1,
    max_tokens: int = 4000
) -> Optional[str]:
    # Formulate endpoint
    url = f"{base_url}/chat/completions"
    
    # Build headers with security keys dynamically
    headers = {"Content-Type": "application/json"}
    
    # Resolve Authorization dynamically
    api_key = None
    if "api.openai.com" in base_url and settings.OPENAI_API_KEY:
        api_key = settings.OPENAI_API_KEY.get_secret_value()
    elif "api.deepseek.com" in base_url and settings.DEEPSEEK_API_KEY:
        api_key = settings.DEEPSEEK_API_KEY.get_secret_value()
    elif "openrouter.ai" in base_url and hasattr(settings, "OPENROUTER_API_KEY") and settings.OPENROUTER_API_KEY:
        api_key = settings.OPENROUTER_API_KEY.get_secret_value()
    elif "nous.mesolitica.com" in base_url and hasattr(settings, "NOUS_PORTAL_API_KEY") and settings.NOUS_PORTAL_API_KEY:
        api_key = settings.NOUS_PORTAL_API_KEY.get_secret_value()
    elif "nvidia" in base_url and hasattr(settings, "NVIDIA_API_KEY") and settings.NVIDIA_API_KEY:
        api_key = settings.NVIDIA_API_KEY.get_secret_value()
    elif "x.ai" in base_url and hasattr(settings, "XAI_API_KEY") and settings.XAI_API_KEY:
        api_key = settings.XAI_API_KEY.get_secret_value()
    elif "bigmodel.cn" in base_url and hasattr(settings, "ZHIPU_API_KEY") and settings.ZHIPU_API_KEY:
        api_key = settings.ZHIPU_API_KEY.get_secret_value()
    elif "api.kimi.com" in base_url and hasattr(settings, "KIMI_API_KEY") and settings.KIMI_API_KEY:
        api_key = settings.KIMI_API_KEY.get_secret_value()
    elif "api.moonshot.cn" in base_url and hasattr(settings, "MOONSHOT_API_KEY") and settings.MOONSHOT_API_KEY:
        api_key = settings.MOONSHOT_API_KEY.get_secret_value()
    elif "stepfun.com" in base_url and hasattr(settings, "STEPFUN_API_KEY") and settings.STEPFUN_API_KEY:
        api_key = settings.STEPFUN_API_KEY.get_secret_value()
    elif "dashscope" in base_url and hasattr(settings, "DASHSCOPE_API_KEY") and settings.DASHSCOPE_API_KEY:
        api_key = settings.DASHSCOPE_API_KEY.get_secret_value()
    elif "api.mimo.xiaomi.com" in base_url and hasattr(settings, "MIMO_API_KEY") and settings.MIMO_API_KEY:
        api_key = settings.MIMO_API_KEY.get_secret_value()
    elif "tokenhub.tencentmaas.com" in base_url and hasattr(settings, "TOKENHUB_API_KEY") and settings.TOKENHUB_API_KEY:
        api_key = settings.TOKENHUB_API_KEY.get_secret_value()
    elif "api-inference.huggingface.co" in base_url and hasattr(settings, "HF_API_KEY") and settings.HF_API_KEY:
        api_key = settings.HF_API_KEY.get_secret_value()
    elif "generativelanguage.googleapis.com" in base_url and settings.GEMINI_API_KEY:
        api_key = settings.GEMINI_API_KEY.get_secret_value()
        
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        
    if "api.anthropic.com" in base_url and settings.ANTHROPIC_API_KEY:
        # Handle Anthropic custom gateway mapping
        headers["x-api-key"] = settings.ANTHROPIC_API_KEY.get_secret_value()
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
        response = requests.post(url, json=payload, headers=headers, timeout=60.0)
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
    
    response = requests.post(url, json=payload, headers=headers, timeout=60.0)
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
    primary_url = settings.models.primary_llm_url
    primary_model = settings.models.primary_llm_model
    fallback_url = settings.models.fallback_llm_url
    fallback_model = settings.models.fallback_llm_model
    
    # Dynamic Budget-Aware Swapping (System 4)
    try:
        from tools.strategy.token_governor import token_governor
        resolved_model = token_governor.get_budget_aware_model(primary_model)
        if resolved_model != primary_model:
            logging.info(f"📉 Budget Governor dynamically swapped model '{primary_model}' ➔ '{resolved_model}'")
            primary_model = resolved_model
            # If forced to local, dynamically map the local container endpoint
            if primary_model == "local":
                primary_url = "http://ollama_server:11434/v1"
                primary_model = "llama3.2:1b"
    except Exception as e:
        logging.warning(f"Failed to resolve budget-aware model from TokenGovernor: {e}")
    
    # Clean trailing slash in URLs
    if primary_url.endswith("/"):
        primary_url = primary_url[:-1]
    if fallback_url.endswith("/"):
        fallback_url = fallback_url[:-1]
        
    # Try Primary
    logging.info(f"🔮 LLM_ROUTER: Attempting Primary Endpoint: {primary_url} ({primary_model})")
    
    # Ensure LM Studio model is loaded if running on LM Studio
    try:
        if "127.0.0.1" in primary_url or "localhost" in primary_url or "2065" in primary_url:
            ensure_lmstudio_model_loaded(primary_model, primary_url)
    except Exception as e:
        logging.debug(f"LM Studio pre-load failed or skipped for primary: {e}")

    try:
        content = _make_openai_compatible_call(
            primary_url, primary_model, system_prompt, user_message, temperature, max_tokens
        )
        if content:
            return content
    except Exception as e:
        logging.warning(f"⚠️ LLM_ROUTER: Primary call failed: {e}. Attempting Fallback: {fallback_url} ({fallback_model})")
        
        # Try Fallback
        try:
            if "127.0.0.1" in fallback_url or "localhost" in fallback_url or "2065" in fallback_url:
                ensure_lmstudio_model_loaded(fallback_model, fallback_url)
        except Exception as pre_err:
            logging.debug(f"LM Studio pre-load failed or skipped for fallback: {pre_err}")

        try:
            content = _make_openai_compatible_call(
                fallback_url, fallback_model, system_prompt, user_message, temperature, max_tokens
            )
            if content:
                return content
        except Exception as fallback_err:
            error_msg = f"❌ LLM_ROUTER CRITICAL: Both primary and fallback endpoints failed. Fallback error: {fallback_err}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)

