"""
Kenbun Subscription Proxy Server
================================
A local OpenAI-compatible API proxy running on port 8645 (default).
Intercepts requests, attaches configured provider credentials dynamically,
and forwards them to upstream services (Gemini, DeepSeek, Nvidia, OpenAI, etc.).
"""

import logging
import time
import httpx
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from tools.infrastructure.config import settings
from tools.utils.secret_manager import decrypt_value

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("subscription_proxy")

app = FastAPI(title="Kenbun Subscription Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Upstream Resolution Helpers ──────────────────────────────────────────────

def get_auth_token_for_url(base_url: str) -> Optional[str]:
    """Resolves and decrypts the API key for a given base URL from settings."""
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
    elif "googleapis.com" in base_url and settings.GEMINI_API_KEY:
        api_key = decrypt_value(settings.GEMINI_API_KEY.get_secret_value())
    return api_key

# ── Route Implementations ───────────────────────────────────────────────────

@app.get("/v1/models")
async def list_models():
    """Lists the configured primary model."""
    model_name = settings.PRIMARY_LLM_MODEL or "qwen2.5:1.5b"
    return {
        "object": "list",
        "data": [
            {
                "id": model_name,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "kenbun"
            }
        ]
    }

@app.get("/v1/providers")
async def list_providers():
    """Returns status of configured upstream providers."""
    providers = []
    if settings.GEMINI_API_KEY:
        providers.append("gemini")
    if settings.DEEPSEEK_API_KEY:
        providers.append("deepseek")
    if settings.OPENAI_API_KEY:
        providers.append("openai")
    if settings.ANTHROPIC_API_KEY:
        providers.append("anthropic")
    if hasattr(settings, "XAI_API_KEY") and settings.XAI_API_KEY:
        providers.append("xai")
    if hasattr(settings, "NVIDIA_API_KEY") and settings.NVIDIA_API_KEY:
        providers.append("nvidia")
    return {"providers": providers}

@app.post("/v1/chat/completions")
async def chat_completions_proxy(request: Request):
    """Proxies chat completions requests upstream attaching real credentials."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    primary_url = settings.PRIMARY_LLM_URL or "http://localhost:11434/v1"
    
    # Strip trailing slash from primary URL
    if primary_url.endswith("/"):
        primary_url = primary_url[:-1]
        
    upstream_url = f"{primary_url}/chat/completions"
    
    # Clean model resolution override
    if "model" in body and body["model"] == "auto":
        body["model"] = settings.PRIMARY_LLM_MODEL
        
    api_key = get_auth_token_for_url(primary_url)
    
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        
    # Standard logger telemetry
    logger.info(f"Proxying completions request to {upstream_url} using model {body.get('model')}")

    # Handle streaming vs non-streaming
    stream = body.get("stream", False)
    
    async def stream_generator():
        async with httpx.AsyncClient() as client:
            try:
                async with client.stream("POST", upstream_url, json=body, headers=headers, timeout=60.0) as resp:
                    if resp.status_code != 200:
                        yield f"data: [Error upstream status code {resp.status_code}]\n\n".encode()
                        return
                    async for chunk in resp.aiter_bytes():
                        yield chunk
            except Exception as e:
                yield f"data: [Proxy connection failure: {str(e)}]\n\n".encode()

    if stream:
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    else:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(upstream_url, json=body, headers=headers, timeout=60.0)
                return JSONResponse(status_code=resp.status_code, content=resp.json())
            except Exception as e:
                return JSONResponse(status_code=502, content={"error": f"Proxy upstream connection failed: {str(e)}"})

@app.post("/v1/embeddings")
async def embeddings_proxy(request: Request):
    """Proxies embeddings requests upstream attaching real credentials."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    primary_url = settings.PRIMARY_LLM_URL or "http://localhost:11434/v1"
    
    if primary_url.endswith("/"):
        primary_url = primary_url[:-1]
        
    upstream_url = f"{primary_url}/embeddings"
    api_key = get_auth_token_for_url(primary_url)
    
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        
    logger.info(f"Proxying embeddings request to {upstream_url}")

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(upstream_url, json=body, headers=headers, timeout=60.0)
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except Exception as e:
            return JSONResponse(status_code=502, content={"error": f"Proxy upstream connection failed: {str(e)}"})
