import os
import json
import pytest
from unittest.mock import patch, MagicMock
from tools.utils.browser_engine import BrowserEngine, is_private_url
from tools.infrastructure.config import settings

def test_is_private_url():
    """Asserts loopback, private LAN, and local hostnames resolve as private."""
    assert is_private_url("http://127.0.0.1:8000/test") is True
    assert is_private_url("http://localhost:3000") is True
    assert is_private_url("https://[::1]:8080") is True
    assert is_private_url("http://192.168.1.1/admin") is True
    assert is_private_url("http://10.0.0.2") is True
    assert is_private_url("https://mywebsite.local") is True
    assert is_private_url("https://service.internal/status") is True
    assert is_private_url("http://router.lan") is True

    # Public URLs
    assert is_private_url("https://github.com/NousResearch") is False
    assert is_private_url("http://google.com") is False

@patch("subprocess.run")
def test_browser_navigate_public(mock_run):
    """Verifies that navigation to a public URL forwards the provider configuration."""
    mock_resp = MagicMock()
    mock_resp.returncode = 0
    mock_resp.stdout = json.dumps({"success": True, "data": {"status": "ok"}, "error": None})
    mock_run.return_value = mock_resp

    with patch.object(settings, "BROWSER_CLOUD_PROVIDER", "browserbase"):
        engine = BrowserEngine()
        # Reset engine state
        engine.session_is_local = False
        
        res = engine.navigate("https://google.com")
        assert res["success"] is True
        
        # Verify provider environment variable was passed to subprocess
        args, kwargs = mock_run.call_args
        env = kwargs.get("env", {})
        assert env.get("AGENT_BROWSER_PROVIDER") == "browserbase"
        assert "open" in args[0]
        assert "https://google.com" in args[0]

@patch("subprocess.run")
def test_browser_navigate_private_block(mock_run):
    """Verifies private URLs are blocked when allow_private and auto_local are disabled."""
    engine = BrowserEngine()
    
    with patch.object(settings, "BROWSER_ALLOW_PRIVATE_URLS", False):
        with patch.object(settings, "BROWSER_AUTO_LOCAL_FOR_PRIVATE_URLS", False):
            with pytest.raises(ValueError, match="Blocked: URL targets a private or internal address"):
                engine.navigate("http://127.0.0.1:8001")

@patch("subprocess.run")
def test_browser_navigate_private_hybrid(mock_run):
    """Verifies hybrid routing drops cloud provider flags for private targets."""
    mock_resp = MagicMock()
    mock_resp.returncode = 0
    mock_resp.stdout = json.dumps({"success": True, "data": {"status": "ok"}, "error": None})
    mock_run.return_value = mock_resp

    engine = BrowserEngine()
    
    with patch.object(settings, "BROWSER_CLOUD_PROVIDER", "browserbase"):
        with patch.object(settings, "BROWSER_ALLOW_PRIVATE_URLS", False):
            with patch.object(settings, "BROWSER_AUTO_LOCAL_FOR_PRIVATE_URLS", True):
                res = engine.navigate("http://localhost:3000/dashboard")
                assert res["success"] is True
                assert engine.session_is_local is True
                
                # Assert AGENT_BROWSER_PROVIDER is omitted in the environment
                args, kwargs = mock_run.call_args
                env = kwargs.get("env", {})
                assert "AGENT_BROWSER_PROVIDER" not in env

@patch("subprocess.run")
@patch("tools.utils.llm_router.call_llm_gateway")
def test_browser_snapshot_compress(mock_call, mock_run):
    """Asserts snapshots over 8000 characters trigger LLM compression."""
    mock_resp = MagicMock()
    mock_resp.returncode = 0
    # Simulate a very long snapshot (8005 characters)
    long_snapshot = "A" * 8005
    mock_resp.stdout = json.dumps({"success": True, "data": {"snapshot": long_snapshot}, "error": None})
    mock_run.return_value = mock_resp

    # LLM Mock return
    mock_call.return_value = "Compressed snapshot output."

    engine = BrowserEngine()
    res = engine.snapshot(full=True)
    
    assert res["success"] is True
    assert res["data"]["snapshot"] == "Compressed snapshot output."
    mock_call.assert_called_once()

@patch("subprocess.run")
def test_browser_actions(mock_run):
    """Tests basic interaction subcommands mapping to CLI executions."""
    mock_resp = MagicMock()
    mock_resp.returncode = 0
    mock_resp.stdout = json.dumps({"success": True, "data": {}, "error": None})
    mock_run.return_value = mock_resp

    engine = BrowserEngine()
    
    # Click
    engine.click("e5")
    args, _ = mock_run.call_args
    assert "click" in args[0]
    assert "e5" in args[0]
    
    # Type (Fill)
    engine.type("e3", "hello world")
    args, _ = mock_run.call_args
    assert "fill" in args[0]
    assert "e3" in args[0]
    assert "hello world" in args[0]
    
    # Scroll
    engine.scroll("down")
    args, _ = mock_run.call_args
    assert "scroll" in args[0]
    assert "down" in args[0]

@patch("subprocess.run")
def test_browser_get_images_eval(mock_run):
    """Verifies browser_get_images evaluates custom script query on page DOM."""
    mock_resp = MagicMock()
    mock_resp.returncode = 0
    mock_resp.stdout = json.dumps({
        "success": True,
        "data": {
            "result": [{"url": "https://example.com/logo.png", "alt": "Logo"}]
        },
        "error": None
    })
    mock_run.return_value = mock_resp

    engine = BrowserEngine()
    res = engine.get_images()
    assert res["success"] is True
    assert len(res["data"]["result"]) == 1
    assert res["data"]["result"][0]["url"] == "https://example.com/logo.png"

@patch("subprocess.run")
@patch("os.path.exists")
@patch("shutil.copy2")
@patch("tools.utils.browser_engine.BrowserEngine._analyze_image")
def test_browser_vision(mock_analyze, mock_copy, mock_exists, mock_run):
    """Tests browser_vision screenshot trigger and analysis flow."""
    mock_resp = MagicMock()
    mock_resp.returncode = 0
    mock_resp.stdout = json.dumps({"success": True, "data": {"path": "/tmp/screenshot.png"}, "error": None})
    mock_run.return_value = mock_resp
    
    mock_exists.return_value = True
    mock_analyze.return_value = "Detailed analysis report."

    engine = BrowserEngine()
    res = engine.vision("Describe this website")
    
    assert res["success"] is True
    assert res["data"]["analysis"] == "Detailed analysis report."
    mock_analyze.assert_called_once_with(res["data"]["screenshot_path"], "Describe this website")

@patch("requests.get")
def test_browser_cdp_get_targets(mock_get):
    """Asserts browser_cdp handles Target.getTargets by hitting debug port endpoints."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"id": "tab-1", "type": "page", "title": "Index Page", "url": "https://google.com", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/tab-1"}
    ]
    mock_get.return_value = mock_resp

    engine = BrowserEngine()
    res = engine.cdp(method="Target.getTargets")
    
    assert res["success"] is True
    target_infos = res["result"]["targetInfos"]
    assert len(target_infos) == 1
    assert target_infos[0]["targetId"] == "tab-1"
    assert target_infos[0]["title"] == "Index Page"
