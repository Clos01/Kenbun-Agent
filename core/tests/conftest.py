"""Shared pytest fixtures."""
import sys
from unittest.mock import MagicMock, patch
import pytest
from tools.infrastructure.config import settings


@pytest.fixture(autouse=True)
def mock_security_settings_for_testing():
    """Globally bypass cron_mode deny during pytest runs to prevent false-rejections on unattended tests."""
    mock_sec = MagicMock()
    mock_sec.cron_mode = "allow"
    mock_sec.approval_mode = "smart"
    mock_sec.approval_timeout = 45
    mock_sec.custom_hook_path = None
    
    with patch("tools.infrastructure.config.KenbunSettings.security", new_callable=MagicMock) as mock_settings_sec:
        mock_settings_sec.return_value = mock_sec
        yield


@pytest.fixture(autouse=True)
def mock_databases_for_testing():
    """Globally mock remote database reachability to prevent socket timeouts and connection hangs."""
    import psycopg
    
    # Mock BayesianGovernor remote DB initialization to bypass socket checks
    def mock_init_remote_db(self):
        self.use_local = True
        
    # Mock psycopg.connect to fail fast (0ms) instead of 3s timeout
    def mock_psycopg_connect(*args, **kwargs):
        raise psycopg.OperationalError("Mocked connection failure for testing")

    with patch("tools.strategy.strategy_manager.BayesianGovernor._init_remote_db", mock_init_remote_db), \
         patch("psycopg.connect", mock_psycopg_connect):
        yield