"""Shared pytest fixtures."""
from unittest.mock import MagicMock, patch
import pytest


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
def isolate_calibration_store(tmp_path_factory):
    """Keep test runs out of the real audit-calibration store.

    Any test that exercises the supervisor end-to-end reaches record_pair(), and
    without this the run writes fabricated verdict pairs into the production
    table — which then gates (or ungates) real auto-approvals. A calibration
    store contaminated by mocked verdicts is worse than an empty one: it looks
    like evidence.
    """
    import sqlite3
    from tools.audit.calibration import calibration

    db = tmp_path_factory.mktemp("calibration") / "test_intelligence.db"
    calibration._initialized = False
    with patch.object(calibration, "_connect",
                      lambda: sqlite3.connect(db, timeout=5.0)):
        yield
    calibration._initialized = False


@pytest.fixture(autouse=True)
def mock_databases_for_testing():
    """Globally mock remote database reachability to prevent socket timeouts and connection hangs."""
    try:
        import psycopg
    except ImportError:
        yield
        return

    # Mock BayesianGovernor remote DB initialization to bypass socket checks
    def mock_init_remote_db(self):
        self.use_local = True
        
    # Mock psycopg.connect to fail fast (0ms) instead of 3s timeout
    def mock_psycopg_connect(*args, **kwargs):
        raise psycopg.OperationalError("Mocked connection failure for testing")

    with patch("tools.strategy.strategy_manager.BayesianGovernor._init_remote_db", mock_init_remote_db), \
         patch("psycopg.connect", mock_psycopg_connect):
        yield