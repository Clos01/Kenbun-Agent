import json
import pytest
from unittest.mock import patch, MagicMock
from tools.utils import llm_router

def test_lmstudio_server_root():
    """Verifies that the /v1 suffix is correctly stripped from URLs."""
    assert llm_router._lmstudio_server_root("http://localhost:1234/v1") == "http://localhost:1234"
    assert llm_router._lmstudio_server_root("http://127.0.0.1:2065/v1/") == "http://127.0.0.1:2065"
    assert llm_router._lmstudio_server_root("http://localhost:1234") == "http://localhost:1234"
    assert llm_router._lmstudio_server_root("") is None

@patch("urllib.request.urlopen")
def test_probe_lmstudio_models(mock_urlopen):
    """Verifies that model probing returns chat model keys while filtering embeddings."""
    mock_resp = MagicMock()
    payload = {
        "models": [
            {"id": "qwen-coder-14b", "key": "qwen-coder-14b", "type": "chat"},
            {"id": "nomic-embed", "key": "nomic-embed", "type": "embedding"},
            {"id": "deepseek-r1-7b", "type": "chat"}
        ]
    }
    mock_resp.read.return_value = json.dumps(payload).encode()
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    models = llm_router.probe_lmstudio_models(base_url="http://localhost:1234/v1")
    assert models == ["qwen-coder-14b", "deepseek-r1-7b"]

@patch("urllib.request.urlopen")
def test_ensure_lmstudio_model_loaded_already_active(mock_urlopen):
    """Verifies that no POST load call is triggered if the target model and context length are already active."""
    mock_resp = MagicMock()
    payload = {
        "models": [
            {
                "id": "qwen-coder-14b",
                "key": "qwen-coder-14b",
                "max_context_length": 32768,
                "loaded_instances": [
                    {
                        "config": {
                            "context_length": 8192
                        }
                    }
                ]
            }
        ]
    }
    mock_resp.read.return_value = json.dumps(payload).encode()
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    with patch("urllib.request.Request") as mock_req_class:
        ctx_len = llm_router.ensure_lmstudio_model_loaded("qwen-coder-14b", "http://localhost:1234/v1", target_context_length=8192)
        assert ctx_len == 8192
        called_urls = [args[0] for args, kwargs in mock_req_class.call_args_list if len(args) > 0]
        assert any("models/load" in u for u in called_urls) is False

@patch("urllib.request.urlopen")
def test_ensure_lmstudio_model_loaded_triggers_load(mock_urlopen):
    """Verifies that a POST request is triggered to load a model if it is offline or has insufficient context length."""
    mock_resp_probe = MagicMock()
    probe_payload = {
        "models": [
            {
                "id": "qwen-coder-14b",
                "key": "qwen-coder-14b",
                "max_context_length": 16384,
                "loaded_instances": []
            }
        ]
    }
    mock_resp_probe.read.return_value = json.dumps(probe_payload).encode()

    mock_resp_load = MagicMock()
    mock_resp_load.read.return_value = b'{"status": "loaded"}'

    mock_urlopen.return_value.__enter__.side_effect = [mock_resp_probe, mock_resp_load]

    ctx_len = llm_router.ensure_lmstudio_model_loaded("qwen-coder-14b", "http://localhost:1234/v1", target_context_length=8192)
    assert ctx_len == 8192
    assert mock_urlopen.call_count == 2

def test_decrypt_value_compatibility():
    """Verifies that decrypt_value handles plain text, enc:v1:, and enc: prefixes."""
    from tools.infrastructure.config import decrypt_value, get_master_key
    from cryptography.fernet import Fernet
    
    # 1. Plain text
    assert decrypt_value("hello_world") == "hello_world"
    assert decrypt_value("") == ""
    
    # 2. enc:v1: using master key
    key = get_master_key()
    f = Fernet(key)
    plain = "super_secret_api_key_123"
    encrypted_v1 = f"enc:v1:{f.encrypt(plain.encode()).decode()}"
    
    assert decrypt_value(encrypted_v1) == plain

    # 3. enc: using local key if it exists, or fallback
    encrypted_normal = f"enc:{f.encrypt(plain.encode()).decode()}"
    assert decrypt_value(encrypted_normal) == plain

def test_make_openai_compatible_call_keys_mapping():
    """Verifies that _make_openai_compatible_call dynamically selects and injects the correct bearer keys."""
    from unittest.mock import patch, MagicMock
    from tools.infrastructure.config import settings
    from pydantic import SecretStr
    
    # Mock settings keys
    settings.OPENROUTER_API_KEY = SecretStr("mock_openrouter_key")
    settings.ZHIPU_API_KEY = SecretStr("mock_zhipu_key")
    settings.GEMINI_API_KEY = SecretStr("mock_gemini_key")
    
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Response content"}}]
        }
        mock_post.return_value = mock_resp
        
        # Test OpenRouter mapping
        llm_router._make_openai_compatible_call("https://openrouter.ai/api/v1", "model", "sys", "usr")
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer mock_openrouter_key"
        
        # Test Zhipu mapping
        llm_router._make_openai_compatible_call("https://open.bigmodel.cn/api/paas/v4", "model", "sys", "usr")
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer mock_zhipu_key"
        
        # Test Gemini mapping
        llm_router._make_openai_compatible_call("https://generativelanguage.googleapis.com/v1beta", "model", "sys", "usr")
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer mock_gemini_key"

