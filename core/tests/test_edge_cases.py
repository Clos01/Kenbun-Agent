import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

# Ensure core is in path
import sys
core_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if core_dir not in sys.path:
    sys.path.insert(0, core_dir)

from tools.infrastructure.config import settings
from tools.strategy.strategy_manager import BayesianGovernor, PulseStatus
from tools.sensory.imessage_tools import list_imessage_chats, get_imessage_history, send_imessage
from tools.infrastructure.routers.skills import parse_yaml_frontmatter, validate_skill_metadata
from tools.infrastructure.api_server import app as api_app
from tools.infrastructure.proxy_server import app as proxy_app

# Dependency overrides for safety/authorization bypass
from tools.infrastructure.server_deps import verify_authorization
api_app.dependency_overrides[verify_authorization] = lambda: None

client_api = TestClient(api_app)
client_proxy = TestClient(proxy_app)

class TestEdgeCases:

    # ==========================================
    # 1. BAYESIAN GOVERNOR EDGE CASES
    # ==========================================

    def test_bayesian_governor_local_fallback(self, monkeypatch):
        """Verify that BayesianGovernor falls back to SQLite when remote connection checks fail."""
        gov = BayesianGovernor()
        
        # Force a hostname/port check to fail by mocking socket.create_connection to raise TimeoutError
        import socket
        def mock_create_connection(*args, **kwargs):
            raise socket.timeout("Connection timed out")
            
        monkeypatch.setattr(socket, "create_connection", mock_create_connection)
        
        # Run init
        gov._init_remote_db()
        assert gov.use_local is True

    def test_bayesian_governor_sqlite_operations(self, tmp_path, monkeypatch):
        """Verify get_tool_stats and update_intelligence using SQLite database."""
        gov = BayesianGovernor()
        gov.use_local = True
        
        db_path = tmp_path / "test_intel.db"
        # Overwrite settings / local DB path
        monkeypatch.setattr("tools.strategy.strategy_manager.LOCAL_DB_PATH", str(db_path))
        
        # Test bootstrapping
        gov._init_local_db()
        assert db_path.exists()
        
        # Check defaults are bootstrapped (should have default tools)
        stats = gov.get_all_stats()
        assert len(stats) > 0
        
        # Check initial stats for a default tool
        alpha, beta, s, f = gov.get_tool_stats("token_governor")
        assert alpha == 2.0
        assert beta == 2.0
        assert s == 0
        assert f == 0
        
        # Update intelligence with a success
        gov.update_intelligence("token_governor", "Strategy", success=True)
        alpha, beta, s, f = gov.get_tool_stats("token_governor")
        assert alpha == 3.0
        assert beta == 2.0
        assert s == 1
        assert f == 0
        
        # Update intelligence with a failure
        gov.update_intelligence("token_governor", "Strategy", success=False)
        alpha, beta, s, f = gov.get_tool_stats("token_governor")
        assert alpha == 3.0
        assert beta == 3.0
        assert s == 1
        assert f == 1

    def test_bayesian_governor_sample_strategy(self, tmp_path, monkeypatch):
        """Verify Thompson Sampling picks the best tool based on weights."""
        gov = BayesianGovernor()
        gov.use_local = True
        db_path = tmp_path / "test_intel_sample.db"
        monkeypatch.setattr("tools.strategy.strategy_manager.LOCAL_DB_PATH", str(db_path))
        gov._init_local_db()
        
        # Clean table and insert isolated custom tools to prevent discovery dependency noise
        cursor = gov.local_conn.cursor()
        cursor.execute("DELETE FROM intelligence")
        cursor.execute("INSERT INTO intelligence (tool_id, category, alpha, beta, success_count, failure_count) VALUES ('tool_a', 'global', 100.0, 1.0, 0, 0)")
        cursor.execute("INSERT INTO intelligence (tool_id, category, alpha, beta, success_count, failure_count) VALUES ('tool_b', 'global', 1.0, 100.0, 0, 0)")
        gov.local_conn.commit()
        gov.get_tool_stats.cache_clear()
        
        # Run sample_strategy multiple times; it should pick tool_a almost 100% of the time
        picks = []
        for _ in range(50):
            tool, score = gov.sample_strategy(["tool_a", "tool_b"])
            picks.append(tool)
            
        assert "tool_a" in picks
        assert picks.count("tool_a") > 45

    def test_bayesian_governor_telemetry_pulse(self, tmp_path, monkeypatch):
        """Verify telemetry pulse generation under different tool stats states."""
        gov = BayesianGovernor()
        gov.use_local = True
        db_path = tmp_path / "test_intel_telemetry.db"
        monkeypatch.setattr("tools.strategy.strategy_manager.LOCAL_DB_PATH", str(db_path))
        gov._init_local_db()
        
        # 1. Healthy State (alpha / beta mean is high)
        cursor = gov.local_conn.cursor()
        cursor.execute("UPDATE intelligence SET alpha = 10.0, beta = 1.0")
        gov.local_conn.commit()
        gov.get_tool_stats.cache_clear()
        
        pulse = gov.get_telemetry_pulse()
        assert pulse.status == PulseStatus.STABLE
        assert pulse.accuracy >= 0.9
        
        # 2. Warning State (alpha / beta mean is moderate)
        cursor.execute("UPDATE intelligence SET alpha = 5.0, beta = 4.0")
        gov.local_conn.commit()
        gov.get_tool_stats.cache_clear()
        
        pulse = gov.get_telemetry_pulse()
        assert pulse.status == PulseStatus.WARNING
        
        # 3. Critical State (alpha / beta mean is low)
        cursor.execute("UPDATE intelligence SET alpha = 1.0, beta = 5.0")
        gov.local_conn.commit()
        gov.get_tool_stats.cache_clear()
        
        pulse = gov.get_telemetry_pulse()
        assert pulse.status == PulseStatus.CRITICAL

    def test_bayesian_governor_postgres_operations(self, monkeypatch):
        """Verify get_tool_stats, update_intelligence and tune_swarm with PostgreSQL mocking."""
        gov = BayesianGovernor()
        gov.use_local = False
        gov._ensure_db = lambda: None
        
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        # Mock get_connection
        mock_get_connection = MagicMock(return_value=mock_conn)
        monkeypatch.setattr("tools.memory.postgres_client.get_connection", mock_get_connection, raising=False)
        monkeypatch.setattr("tools.utils.bayesian.get_connection", mock_get_connection, raising=False)
        
        # Test get_tool_stats when row exists
        mock_cursor.fetchone.return_value = {
            "alpha": 3.5,
            "beta": 1.2,
            "success_count": 5,
            "failure_count": 2
        }
        
        # We need to clear lru_cache since get_tool_stats is cached
        gov.get_tool_stats.cache_clear()
        alpha, beta, s, f = gov.get_tool_stats("mock_tool")
        assert alpha == 3.5
        assert beta == 1.2
        assert s == 5
        assert f == 2
        
        # Verify query was correct
        mock_cursor.execute.assert_called_with(
            "SELECT alpha, beta, success_count, failure_count FROM bayesian_weights WHERE tool_id = %s AND category = %s",
            ("mock_tool", "global")
        )
        
        # Test update_intelligence remote PostgreSQL update
        # Clear cache first
        gov.get_tool_stats.cache_clear()
        gov.update_intelligence("mock_tool", "Strategy", success=True)
        # It updates both 'global' and 'Strategy'. Let's inspect the INSERT/UPDATE query execution args for category-specific row.
        called_args = mock_cursor.execute.call_args_list[-1][0]
        query = called_args[0]
        params = called_args[1]
        
        assert "INSERT INTO bayesian_weights" in query
        assert "success_count = bayesian_weights.success_count + EXCLUDED.success_count" in query
        assert params[0] == "mock_tool"
        assert params[1] == "Strategy"
        assert params[2] == 2.0 # alpha_inc + 1.0
        assert params[3] == 1.0 # beta_inc + 1.0
        assert params[4] == 1   # s_inc
        assert params[5] == 0   # f_inc
        
        # Test tune_swarm remote PostgreSQL update
        from tools.utils.bayesian import tune_swarm
        tune_swarm("mock_tool", success=True, category="Strategy")
        
        # Verify last query execution args in tune_swarm
        # It does:
        # 1. Update global (Insert global weight/counts)
        # 2. Category-specific: insert category record seeding from global
        # 3. Category-specific: update category record
        
        # Let's check the update query execution args
        update_call = mock_cursor.execute.call_args_list[-1][0]
        update_query = update_call[0]
        update_params = update_call[1]
        
        assert "UPDATE bayesian_weights" in update_query
        assert "success_count = success_count + %s" in update_query
        assert update_params[0] == 1.0 # alpha inc
        assert update_params[1] == 0.0 # beta inc
        assert update_params[2] == 1   # s inc
        assert update_params[3] == 0   # f inc
        assert update_params[4] == "mock_tool"
        assert update_params[5] == "Strategy"

    # ==========================================
    # 2. iMESSAGE TOOLS EDGE CASES
    # ==========================================

    @pytest.mark.asyncio
    async def test_list_imessage_chats_malformed_json(self):
        """Test list_imessage_chats handles non-JSON garbage output from imsg CLI."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"THIS IS NOT VALID JSON", b"")
        
        with patch("tools.sensory.imessage_tools.get_imsg_path", return_value="/usr/local/bin/imsg"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            res = await list_imessage_chats()
            assert not res["success"]
            assert "Failed to list iMessage chats" in res["error"]

    @pytest.mark.asyncio
    async def test_get_imessage_history_subprocess_failure(self):
        """Test get_imessage_history handles non-zero exit code from subprocess."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate.return_value = (b"", b"Error fetching history from macOS DB")
        
        with patch("tools.sensory.imessage_tools.get_imsg_path", return_value="/usr/local/bin/imsg"), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            res = await get_imessage_history(chat_id=99)
            assert not res["success"]
            assert "Error fetching history from macOS DB" in res["error"]

    @pytest.mark.asyncio
    async def test_send_imessage_empty_service(self):
        """Test send_imessage with invalid service parameter."""
        with patch("tools.sensory.imessage_tools.get_imsg_path", return_value="/usr/local/bin/imsg"):
            res = await send_imessage(to="+1555", text="hello", service="invalid_service")
            assert not res["success"]
            assert "Invalid service" in res["error"]

    # ==========================================
    # 3. SKILLS MANAGEMENT ENDPOINTS EDGE CASES
    # ==========================================

    def test_parse_yaml_frontmatter_malformed(self):
        """Test parsing malformed or edge frontmatter text."""
        # 1. No frontmatter
        assert parse_yaml_frontmatter("Hello World") == {}
        
        # 2. Unclosed frontmatter block
        unclosed = "---\nkenbun:\n  mode: prototype"
        assert parse_yaml_frontmatter(unclosed) == {}
        
        # 3. Line with missing colon (with trailing newline)
        missing_colon = "---\nkenbun:\n  mode prototype\n---\n"
        res = parse_yaml_frontmatter(missing_colon)
        assert res.get("kenbun") == {}

    def test_validate_skill_metadata_malformed_details(self, tmp_path):
        """Test validate_skill_metadata with non-compliant fidelity or mode values."""
        skill_dir = tmp_path / "skill-test"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        
        # Invalid mode
        skill_file.write_text("---\nkenbun:\n  mode: invalid_mode\n  fidelity: high\n  tech_stack: []\n  discovery_required: false\n---\n")
        is_valid, msg = validate_skill_metadata(skill_dir)
        assert not is_valid
        assert "Invalid or missing mode" in msg
        
        # Invalid fidelity
        skill_file.write_text("---\nkenbun:\n  mode: prototype\n  fidelity: ultra_hd\n  tech_stack: []\n  discovery_required: false\n---\n")
        is_valid, msg = validate_skill_metadata(skill_dir)
        assert not is_valid
        assert "Invalid or missing fidelity" in msg
        
        # Invalid tech_stack type (should be list)
        skill_file.write_text("---\nkenbun:\n  mode: prototype\n  fidelity: high\n  tech_stack: not-a-list\n  discovery_required: false\n---\n")
        is_valid, msg = validate_skill_metadata(skill_dir)
        assert not is_valid
        assert "must be a list of technologies" in msg

    # ==========================================
    # 4. SUBSCRIPTION PROXY ENDPOINTS EDGE CASES
    # ==========================================

    def test_proxy_chat_completions_malformed_json(self):
        """Test proxy completions endpoint with malformed/non-JSON body."""
        response = client_proxy.post(
            "/v1/chat/completions",
            content="NOT A VALID JSON",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        assert "Invalid JSON body" in response.json()["detail"]

    def test_proxy_chat_completions_missing_fields(self):
        """Test proxy completions endpoint with valid JSON but empty payload returns 502 (falls upstream)."""
        import httpx
        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
            response = client_proxy.post("/v1/chat/completions", json={})
            assert response.status_code == 502
            assert "Proxy upstream connection failed" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_proxy_chat_completions_upstream_500(self):
        """Test proxy completions endpoint when upstream provider returns 500."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Internal Provider Server Error"}
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            payload = {
                "model": "auto",
                "messages": [{"role": "user", "content": "Hi"}]
            }
            response = client_proxy.post("/v1/chat/completions", json=payload)
            assert response.status_code == 500
            assert response.json() == {"error": "Internal Provider Server Error"}

    # ==========================================
    # 5. CHAT HISTORY MANAGER EDGE CASES
    # ==========================================

    def test_chat_history_lock_contention(self, tmp_path, monkeypatch):
        """Test lock contention in chat_history_manager."""
        # Overwrite BRAIN_HEALTH_DIR settings to a temp path
        monkeypatch.setattr(settings, "BRAIN_HEALTH_DIR", tmp_path)
        
        # Manually create the lock file to simulate contention
        from tools.utils import chat_history_manager
        lock_file = tmp_path / "chat_sessions.lock"
        lock_file.write_text("locked by process 1234")
        
        # Call load_sessions with a short timeout to prevent long test wait
        # We can patch _acquire_lock to call with a 0.05s timeout
        original_acquire = chat_history_manager._acquire_lock
        def short_acquire():
            return original_acquire(timeout=0.05)
            
        monkeypatch.setattr(chat_history_manager, "_acquire_lock", short_acquire)
        
        sessions = chat_history_manager.load_sessions()
        assert sessions == []
        
        # Clean up lock
        chat_history_manager._release_lock()
        assert not lock_file.exists()

    def test_chat_history_corrupted_json(self, tmp_path, monkeypatch):
        """Test loading corrupted JSON file returns [] safely."""
        monkeypatch.setattr(settings, "BRAIN_HEALTH_DIR", tmp_path)
        
        from tools.utils import chat_history_manager
        sessions_file = chat_history_manager.get_sessions_file_path()
        sessions_file.write_text("INVALID JSON DATA }---{")
        
        sessions = chat_history_manager.load_sessions()
        assert sessions == []

    def test_chat_history_long_title(self, tmp_path, monkeypatch):
        """Test auto-title truncation logic for long first messages."""
        monkeypatch.setattr(settings, "BRAIN_HEALTH_DIR", tmp_path)
        from tools.utils import chat_history_manager
        
        session = chat_history_manager.create_session()
        long_prompt = "Verify that the entire docker container deployment configuration is highly scalable"
        msg = chat_history_manager.add_message_to_session(session["id"], "user", long_prompt)
        
        fetched = chat_history_manager.get_session(session["id"])
        # The title should be truncated to less than or equal to 25 characters (plus '...')
        assert len(fetched["title"]) <= 25
        assert fetched["title"].endswith("...")

    def test_chat_history_search(self, tmp_path, monkeypatch):
        """Test case-insensitive search across sessions with snippet extraction."""
        monkeypatch.setattr(settings, "BRAIN_HEALTH_DIR", tmp_path)
        from tools.utils import chat_history_manager
        
        session = chat_history_manager.create_session()
        chat_history_manager.add_message_to_session(session["id"], "user", "Deploying a Redis cluster on Kubernetes")
        
        # Search for "kUbErNeTeS"
        results = chat_history_manager.search_sessions("kUbErNeTeS")
        assert len(results) == 1
        assert results[0]["id"] == session["id"]
        assert "Kubernetes" in results[0]["matches"][0]["snippet"]

    # ==========================================
    # 6. LLM ROUTER PROBING EDGE CASES
    # ==========================================

    def test_probe_lmstudio_models_exception(self, monkeypatch):
        """Test probe_lmstudio_models handles connection errors gracefully."""
        from tools.utils import llm_router
        import urllib.error
        
        # Mock urllib.request.urlopen to raise URLError
        def mock_urlopen(*args, **kwargs):
            raise urllib.error.URLError("Connection refused")
            
        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        
        models = llm_router.probe_lmstudio_models(base_url="http://localhost:1234/v1")
        assert models is None

    def test_probe_openai_models_malformed(self, monkeypatch):
        """Test probe_openai_models handles invalid response formats gracefully."""
        from tools.utils import llm_router
        
        # Mock urlopen to return malformed dict
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"data": "not-a-list"}'
        
        class MockUrlOpen:
            def __enter__(self):
                return mock_resp
            def __exit__(self, *args):
                pass
                
        monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: MockUrlOpen())
        
        models = llm_router.probe_openai_models(base_url="http://localhost:1234/v1")
        assert models is None

    # ==========================================
    # 7. API SERVER AUTHORIZATION EDGE CASES
    # ==========================================

    def test_api_server_verify_authorization(self, monkeypatch):
        """Test API server verify_authorization enforces token requirements."""
        from fastapi.testclient import TestClient
        from tools.infrastructure.api_server import app as auth_app
        from tools.infrastructure.server_deps import get_or_create_config_token
        
        # Temporarily clear overrides to test actual authorization logic
        original_overrides = dict(auth_app.dependency_overrides)
        auth_app.dependency_overrides.clear()
        
        try:
            auth_client = TestClient(auth_app)
            
            # 1. Access without authorization header -> 401
            response = auth_client.get("/api/v1/mcp/servers")
            assert response.status_code == 401
            assert "Missing or invalid Authorization header" in response.json()["detail"]
            
            # 2. Access with invalid Bearer token -> 403
            response = auth_client.get("/api/v1/mcp/servers", headers={"Authorization": "Bearer invalid_secret_token"})
            assert response.status_code == 403
            assert "Invalid cryptographic authorization token" in response.json()["detail"]
            
            # 3. Access with valid token -> 200 (not 401 or 403)
            valid_token = get_or_create_config_token()
            response = auth_client.get("/api/v1/mcp/servers", headers={"Authorization": f"Bearer {valid_token}"})
            assert response.status_code == 200
        finally:
            auth_app.dependency_overrides.update(original_overrides)


