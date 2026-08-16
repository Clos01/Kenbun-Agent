import os
import json
import pytest
from unittest.mock import patch, AsyncMock

# Ensure core is in path
import sys
core_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if core_dir not in sys.path:
    sys.path.insert(0, core_dir)

from tools.sensory.imessage_tools import (
    list_imessage_chats,
    get_imessage_history,
    send_imessage
)

class TestIMessageTools:

    @pytest.mark.asyncio
    async def test_imsg_missing(self):
        """Tests that tools exit gracefully if imsg CLI is missing."""
        with patch("tools.sensory.imessage_tools.get_imsg_path", return_value=None):
            res = await list_imessage_chats()
            assert not res["success"]
            assert "imsg CLI is not installed" in res["error"]

    @pytest.mark.asyncio
    async def test_list_imessage_chats_success(self):
        """Tests list_imessage_chats parses valid json correctly."""
        mock_chats = [
            {"chatId": 1, "displayName": "Mom", "guid": "iMessage;-;+1555123456"},
            {"chatId": 2, "displayName": "Dad", "guid": "iMessage;-;+1555654321"}
        ]
        
        # Mock subprocess execute
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (json.dumps(mock_chats).encode(), b"")

        with patch("tools.sensory.imessage_tools.get_imsg_path", return_value="/usr/local/bin/imsg"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
                res = await list_imessage_chats(limit=5)
                assert res["success"]
                assert len(res["chats"]) == 2
                assert res["chats"][0]["displayName"] == "Mom"
                
                # Check parameters passed to subprocess
                mock_exec.assert_called_once_with(
                    "/usr/local/bin/imsg", "chats", "--limit", "5", "--json",
                    stdout=-1, stderr=-1
                )

    @pytest.mark.asyncio
    async def test_get_imessage_history_success(self):
        """Tests retrieving chat message histories."""
        mock_messages = [
            {"id": 100, "text": "I'll be late", "sender": "me", "isFromMe": True},
            {"id": 99, "text": "Okay drive safe", "sender": "Mom", "isFromMe": False}
        ]

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (json.dumps(mock_messages).encode(), b"")

        with patch("tools.sensory.imessage_tools.get_imsg_path", return_value="/usr/local/bin/imsg"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
                res = await get_imessage_history(chat_id=1, limit=10, attachments=True)
                assert res["success"]
                assert len(res["messages"]) == 2
                assert res["messages"][0]["text"] == "I'll be late"
                
                # Check parameters passed to subprocess
                mock_exec.assert_called_once_with(
                    "/usr/local/bin/imsg", "history", "--chat-id", "1", "--limit", "10", "--json", "--attachments",
                    stdout=-1, stderr=-1
                )

    @pytest.mark.asyncio
    async def test_send_imessage_validations(self):
        """Tests validation failures on send_imessage arguments."""
        with patch("tools.sensory.imessage_tools.get_imsg_path", return_value="/usr/local/bin/imsg"):
            # Empty recipient
            res = await send_imessage("", "hello")
            assert not res["success"]
            assert "Recipient" in res["error"]

            # Empty text
            res = await send_imessage("+1555", "")
            assert not res["success"]
            assert "Message text" in res["error"]

            # Invalid service
            res = await send_imessage("+1555", "hi", service="whatsapp")
            assert not res["success"]
            assert "Invalid service" in res["error"]

            # Missing file path
            res = await send_imessage("+1555", "hi", file="/tmp/ghost_image_123.jpg")
            assert not res["success"]
            assert "Attachment file does not exist" in res["error"]

    @pytest.mark.asyncio
    async def test_send_imessage_success(self, tmp_path):
        """Tests successful iMessage/SMS sending."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"", b"")

        dummy_file = tmp_path / "test.jpg"
        dummy_file.write_text("dummy content")

        with patch("tools.sensory.imessage_tools.get_imsg_path", return_value="/usr/local/bin/imsg"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
                res = await send_imessage(
                    to="+1555123456",
                    text="Hello!",
                    file=str(dummy_file),
                    service="imessage"
                )
                assert res["success"]
                assert "Successfully sent" in res["message"]
                
                mock_exec.assert_called_once_with(
                    "/usr/local/bin/imsg", "send", "--to", "+1555123456", "--text", "Hello!",
                    "--file", str(dummy_file.resolve()), "--service", "imessage",
                    stdout=-1, stderr=-1
                )
