import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

# Ensure core is in path
import sys
core_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if core_dir not in sys.path:
    sys.path.insert(0, core_dir)

from tools.infrastructure.proxy_server import app
from tools.infrastructure.config import settings

client = TestClient(app)

class TestSubscriptionProxy:

    def test_list_models(self):
        """Tests the /v1/models endpoint."""
        # Force a specific model name for the test
        with patch.object(settings, "PRIMARY_LLM_MODEL", "test-model-123"):
            response = client.get("/v1/models")
            assert response.status_code == 200
            data = response.json()
            assert data["object"] == "list"
            assert len(data["data"]) == 1
            assert data["data"][0]["id"] == "test-model-123"
            assert data["data"][0]["object"] == "model"

    def test_list_providers(self):
        """Tests the /v1/providers endpoint."""
        with patch.object(settings, "GEMINI_API_KEY", MagicMock(get_secret_value=lambda: "key1")):
            with patch.object(settings, "DEEPSEEK_API_KEY", MagicMock(get_secret_value=lambda: "key2")):
                with patch.object(settings, "OPENAI_API_KEY", None):
                    response = client.get("/v1/providers")
                    assert response.status_code == 200
                    providers = response.json()["providers"]
                    assert "gemini" in providers
                    assert "deepseek" in providers
                    assert "openai" not in providers

    @pytest.mark.asyncio
    async def test_chat_completions_non_streaming(self):
        """Tests non-streaming /v1/chat/completions proxying."""
        # We will use an AsyncMock to mock httpx.AsyncClient.post
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "choices": [{"message": {"role": "assistant", "content": "Hello, human!"}}]
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            # Call endpoint through test client (which runs in an event loop)
            # TestClient supports async endpoints automatically
            payload = {
                "model": "auto",
                "messages": [{"role": "user", "content": "Hi"}],
                "stream": False
            }
            response = client.post("/v1/chat/completions", json=payload)
            assert response.status_code == 200
            assert response.json()["choices"][0]["message"]["content"] == "Hello, human!"
            
            # Verify upstream request parameters
            mock_post.assert_called_once()
            called_args, called_kwargs = mock_post.call_args
            assert called_kwargs["json"]["model"] == settings.PRIMARY_LLM_MODEL

    @pytest.mark.asyncio
    async def test_chat_completions_streaming(self):
        """Tests streaming /v1/chat/completions proxying."""
        # Mock httpx.AsyncClient.stream context manager
        mock_stream_response = AsyncMock()
        mock_stream_response.status_code = 200
        
        async def mock_iter_bytes():
            yield b"data: {\"choices\": [{\"delta\": {\"content\": \"Hello\"}}]}\n\n"
            yield b"data: {\"choices\": [{\"delta\": {\"content\": \" world\"}}]}\n\n"
            yield b"data: [DONE]\n\n"

        mock_stream_response.aiter_bytes = mock_iter_bytes
        
        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__.return_value = mock_stream_response

        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_stream.return_value = mock_stream_ctx

            payload = {
                "model": "auto",
                "messages": [{"role": "user", "content": "Hi"}],
                "stream": True
            }
            
            # Using TestClient's stream method to read chunk by chunk
            with client.stream("POST", "/v1/chat/completions", json=payload) as response:
                assert response.status_code == 200
                chunks = [line for line in response.iter_lines() if line.strip()]
                assert len(chunks) >= 3
                assert "Hello" in chunks[0]
                assert "world" in chunks[1]
                assert "[DONE]" in chunks[2]

            mock_stream.assert_called_once()

    @pytest.mark.asyncio
    async def test_embeddings(self):
        """Tests /v1/embeddings proxying."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "object": "list",
            "data": [{"object": "embedding", "embedding": [0.1, 0.2, 0.3], "index": 0}]
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            payload = {
                "model": "text-embedding-ada-002",
                "input": "test embedding"
            }
            response = client.post("/v1/embeddings", json=payload)
            assert response.status_code == 200
            assert response.json()["data"][0]["embedding"] == [0.1, 0.2, 0.3]
            
            mock_post.assert_called_once()

    def test_invalid_path(self):
        """Verifies that an unhandled path returns 404."""
        response = client.get("/v1/invalid-route")
        assert response.status_code == 404
