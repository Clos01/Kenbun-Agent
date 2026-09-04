"""Tests for chat session lifecycle hooks (UserPromptSubmit and Stop)."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from tools.infrastructure.api_server import app
from tools.infrastructure.server_deps import get_or_create_config_token

client = TestClient(app)


@pytest.fixture
def auth_headers():
    token = get_or_create_config_token()
    return {"Authorization": f"Bearer {token}"}


def test_post_message_fires_user_prompt_submit_and_stop_hooks(auth_headers):
    """Verifies that post_message_to_session fires UserPromptSubmit and Stop hooks."""
    mock_registry = MagicMock()
    mock_fire_result = MagicMock(blocked=False, context_blob="")
    mock_registry.fire.return_value = mock_fire_result

    with patch("tools.hooks.default_registry", return_value=mock_registry), \
         patch("tools.utils.chat_history_manager.get_session", return_value={"id": "test-s1", "messages": []}), \
         patch("tools.utils.chat_history_manager.add_message_to_session", return_value={"id": "m1", "sender": "user", "content": "hi"}), \
         patch("tools.utils.llm_router.call_llm_gateway", return_value="Hello, agent!"):

        res = client.post(
            "/api/v1/chat/sessions/test-s1/message",
            json={"message": "hello swarm"},
            headers=auth_headers
        )
        assert res.status_code == 200

        # Verify hook calls
        hook_points = [call.args[0] for call in mock_registry.fire.call_args_list]
        assert "UserPromptSubmit" in hook_points
        assert "Stop" in hook_points


def test_post_message_blocks_when_user_prompt_submit_returns_blocked(auth_headers):
    """Verifies that post_message_to_session halts and returns 400 when UserPromptSubmit blocks."""
    mock_registry = MagicMock()
    mock_fire_result = MagicMock(blocked=True, reason="Prompt policy violation")
    mock_registry.fire.return_value = mock_fire_result

    with patch("tools.hooks.default_registry", return_value=mock_registry), \
         patch("tools.utils.chat_history_manager.get_session", return_value={"id": "test-s1", "messages": []}), \
         patch("tools.utils.chat_history_manager.add_message_to_session", return_value={"id": "m1"}):

        res = client.post(
            "/api/v1/chat/sessions/test-s1/message",
            json={"message": "malicious injection prompt"},
            headers=auth_headers
        )
        assert res.status_code == 400
        assert "Prompt blocked by security hook" in res.json()["error"]
