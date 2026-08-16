import os
import sys
from unittest.mock import patch, MagicMock
import tempfile
import pytest

from tools.utils.secrets_bitwarden import (
    get_target_triple,
    get_bws_bin_name,
    load_kenbun_config_raw,
    save_kenbun_config_raw,
    apply_secrets_to_env,
    _CACHE
)

@pytest.fixture
def clean_cache():
    _CACHE["timestamp"] = 0
    _CACHE["secrets"] = {}
    yield
    _CACHE["timestamp"] = 0
    _CACHE["secrets"] = {}

def test_target_triple():
    triple = get_target_triple()
    if sys.platform == "darwin":
        assert "apple-darwin" in triple
    elif sys.platform == "win32":
        assert triple == "x86_64-pc-windows-msvc"
    elif sys.platform.startswith("linux"):
        assert "unknown-linux-gnu" in triple

def test_bws_bin_name():
    name = get_bws_bin_name()
    if sys.platform == "win32":
        assert name == "bws.exe"
    else:
        assert name == "bws"

def test_load_save_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Mock get_kenbun_dir to point to tmpdir
        with patch("tools.utils.secrets_bitwarden.get_kenbun_dir", return_value=tmpdir):
            config = {"secrets": {"bitwarden": {"enabled": True, "project_id": "test-id"}}}
            save_kenbun_config_raw(config)
            
            loaded = load_kenbun_config_raw()
            assert loaded == config

def test_apply_secrets_to_env_disabled():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("tools.utils.secrets_bitwarden.get_kenbun_dir", return_value=tmpdir):
            # Enabled: False
            config = {"secrets": {"bitwarden": {"enabled": False}}}
            save_kenbun_config_raw(config)
            
            with patch("os.environ", {}):
                apply_secrets_to_env()
                # Should not do anything because it is disabled
                assert "BWS_ACCESS_TOKEN" not in os.environ

@patch("subprocess.run")
def test_apply_secrets_to_env_enabled(mock_run, clean_cache):
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("tools.utils.secrets_bitwarden.get_kenbun_dir", return_value=tmpdir):
            config = {
                "secrets": {
                    "bitwarden": {
                        "enabled": True,
                        "access_token_env": "BWS_ACCESS_TOKEN",
                        "project_id": "proj-123",
                        "server_url": "",
                        "cache_ttl_seconds": 300,
                        "override_existing": True,
                        "auto_install": False
                    }
                }
            }
            save_kenbun_config_raw(config)
            
            # Setup environment variables
            mock_env = {
                "BWS_ACCESS_TOKEN": "mock-token"
            }
            
            # Mock subprocess run output for bws secret list
            mock_stdout = '[{"key": "TEST_VAR", "value": "test-value"}, {"key": "API_KEY", "value": "secret-key"}]'
            mock_res = MagicMock()
            mock_res.returncode = 0
            mock_res.stdout = mock_stdout
            mock_run.return_value = mock_res
            
            # Mock bws path to return a fake path so it doesn't try to download
            with patch("tools.utils.secrets_bitwarden.get_bws_path", return_value="/usr/local/bin/bws"), \
                 patch.dict("os.environ", mock_env, clear=True):
                
                apply_secrets_to_env()
                
                # Check subprocess call details
                mock_run.assert_called_once()
                args, kwargs = mock_run.call_args
                cmd = args[0]
                assert cmd[0] == "/usr/local/bin/bws"
                assert cmd[1] == "secret"
                assert cmd[2] == "list"
                assert cmd[3] == "proj-123"
                
                # Verify environment injection
                assert os.environ["TEST_VAR"] == "test-value"
                assert os.environ["API_KEY"] == "secret-key"
