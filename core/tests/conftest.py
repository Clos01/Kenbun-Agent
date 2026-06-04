"""Shared pytest fixtures."""
import sys
from unittest.mock import MagicMock, patch
import pytest
from tools.infrastructure.config import settings

ROOT = settings.PROJECT_ROOT
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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