import json
from unittest.mock import patch

from tools.strategy.codex_runtime_tool import codex_runtime, check_codex_installed

def test_check_codex_installed():
    # Verify that check_codex_installed doesn't raise exceptions
    res = check_codex_installed()
    assert isinstance(res, bool)

def test_codex_runtime_status():
    res = codex_runtime(action="status")
    data = json.loads(res)
    assert data["status"] == "success"
    assert "current_runtime" in data
    assert "is_enabled" in data

def test_codex_runtime_off():
    with patch("tools.strategy.codex_runtime_tool.update_env_variable") as mock_update:
        res = codex_runtime(action="off")
        data = json.loads(res)
        assert data["status"] == "success"
        assert data["openai_runtime"] == "auto"
        mock_update.assert_called_once_with("OPENAI_RUNTIME", "auto")

def test_codex_runtime_on_installed():
    with patch("tools.strategy.codex_runtime_tool.check_codex_installed", return_value=True), \
         patch("tools.strategy.codex_runtime_tool.update_env_variable") as mock_update, \
         patch("tools.strategy.codex_runtime_tool.update_codex_config") as mock_config:
         
        res = codex_runtime(action="on")
        data = json.loads(res)
        assert data["status"] == "success"
        assert data["openai_runtime"] == "codex_app_server"
        mock_update.assert_called_once_with("OPENAI_RUNTIME", "codex_app_server")
        mock_config.assert_called_once()

def test_codex_runtime_on_missing():
    with patch("tools.strategy.codex_runtime_tool.check_codex_installed", return_value=False):
        res = codex_runtime(action="on")
        data = json.loads(res)
        assert data["status"] == "error"
        assert "not installed" in data["message"]
