"""
DeepSeek Cloud Client - Secure integration with DeepSeek-V3 / DeepSeek-R1.
Ensures end-to-end encryption, non-blocking async execution, and System 4 Token budget compliance.
"""

import os
import time
import requests
import asyncio
from typing import Dict, Any, Optional
from tools.infrastructure.config import settings
from tools.utils.secret_manager import decrypt_value
from tools.strategy.token_governor import token_governor

# Lazy client setup
_deepseek_api_key = None

def _get_api_key() -> str:
    """Retrieves and decrypts the DeepSeek API key securely."""
    global _deepseek_api_key
    if _deepseek_api_key is None:
        import dotenv
        from tools.infrastructure.config import discover_env_file
        
        # Load directly from .env file to bypass stale process environments
        env_file = discover_env_file()
        raw_key = None
        if os.path.exists(env_file):
            env_vars = dotenv.dotenv_values(env_file)
            raw_key = env_vars.get("DEEPSEEK_API_KEY")
            
        if not raw_key:
            # Fallback to Pydantic parsed setting
            raw_key = settings.DEEPSEEK_API_KEY.get_secret_value() if settings.DEEPSEEK_API_KEY else None
            
        if not raw_key:
            # Secondary fallback: check if OPENAI_API_KEY was used instead (DeepSeek compatibility mode)
            raw_key = settings.OPENAI_API_KEY.get_secret_value() if settings.OPENAI_API_KEY else None
            
        if not raw_key:
            raise ValueError(
                "❌ DEEPSEEK_API_KEY not found in Sovereign Settings. "
                "Please add DEEPSEEK_API_KEY to your core/.env file."
            )
        
        _deepseek_api_key = decrypt_value(raw_key)
        
    return _deepseek_api_key

def call_deepseek(
    system_prompt: str,
    user_message: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_retries: int = 3
) -> str:
    """
    Synchronous direct HTTP call to official DeepSeek Cloud API.
    Auto-governs spend and implements exponential retry backoff.
    """
    api_key = _get_api_key()
    model_name = model or settings.models.deepseek_model
    
    # 1. Budget check
    if not token_governor.can_spend(estimated_cost=0.01):
        raise ResourceWarning("⚠️ DeepSeek call blocked: Daily Sovereign Budget has been fully depleted.")

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": temperature
    }

    base_delay = 2.0
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, timeout=60.0)
            
            # Handle rate limiting or server overloads gracefully
            if response.status_code == 429 and attempt < max_retries - 1:
                sleep_time = base_delay * (2 ** attempt)
                print(f"⚠️ DeepSeek Cloud 429 (Rate Limit). Retrying in {sleep_time:.1f}s...")
                time.sleep(sleep_time)
                continue
                
            response.raise_for_status()
            res_data = response.json()
            
            # 2. Extract content
            content = res_data["choices"][0]["message"]["content"]
            
            # 3. Track Sovereign Token spend atomically
            try:
                usage = res_data.get("usage", {})
                token_governor.track_usage(
                    model=model_name,
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    task_id="deepseek_cloud_call"
                )
            except Exception as usage_err:
                print(f"⚠️ Usage tracking failed for DeepSeek: {usage_err}")
                
            return content
            
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"❌ DeepSeek API Connection failure: {e}")
                raise e
            time.sleep(base_delay * (2 ** attempt))

async def call_deepseek_async(
    system_prompt: str,
    user_message: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_retries: int = 3
) -> str:
    """
    Non-blocking async wrapper executing DeepSeek HTTP requests inside an executor thread.
    Completely protects the event loop.
    """
    return await asyncio.to_thread(
        call_deepseek,
        system_prompt=system_prompt,
        user_message=user_message,
        model=model,
        temperature=temperature,
        max_retries=max_retries
    )
