import os
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Ensure core is in path
import sys
core_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if core_dir not in sys.path:
    sys.path.insert(0, core_dir)

from tools.infrastructure.api_server import app
from tools.infrastructure.routers.logs import log_generator

client = TestClient(app)

from tools.infrastructure.server_deps import verify_authorization
app.dependency_overrides[verify_authorization] = lambda: None

class TestDashboardFeatures:

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        # Patch verify_authorization in config.py since it's called directly in the function body
        self.patch_auth = patch("tools.infrastructure.routers.config.verify_authorization")
        self.mock_auth = self.patch_auth.start()
        yield
        self.patch_auth.stop()

    def test_config_schema_discovery(self):
        """Tests that config schema auto-discovery endpoint categorizes settings."""
        response = client.get("/api/v1/config/schema")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "schema" in data
        schema = data["schema"]
        assert "Models" in schema
        assert "Database" in schema
        assert "Sensory & Voice" in schema
        
        # Verify specific fields are categorized
        models_fields = [f["name"] for f in schema["Models"]]
        assert "SWARM_MODEL" in models_fields or "PRIMARY_LLM_MODEL" in models_fields

    def test_credentials_keys_status(self):
        """Tests that credentials keys status checks configuration state without raw leaks."""
        response = client.get("/api/v1/credentials/keys")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "credentials" in data
        creds = data["credentials"]
        
        # Verify secret keys are listed
        assert "GEMINI_API_KEY" in creds
        assert "is_configured" in creds["GEMINI_API_KEY"]
        assert "category" in creds["GEMINI_API_KEY"]

    @pytest.mark.asyncio
    async def test_logs_sse_streaming(self, tmp_path):
        """Tests that logs endpoint reads, formats, and filters lines for SSE stream."""
        log_file = tmp_path / "test_api.log"
        log_file.write_text("INFO: System initialized\nDEBUG: Querying DB\nERROR: Connection timed out\n")
        
        # Collect lines from generator
        lines = []
        async for line in log_generator(log_file, initial_lines=5, level_filter="ERROR"):
            lines.append(line)
            break
            
        assert len(lines) == 1
        assert "ERROR: Connection timed out" in lines[0]
        assert lines[0].startswith("data: ")
        assert lines[0].endswith("\n\n")

    def test_cron_jobs_crud(self, tmp_path):
        """Tests Cron scheduled jobs CRUD endpoints."""
        mock_jobs_db = tmp_path / "cron_jobs.json"
        
        with patch("tools.infrastructure.routers.cron.DB_FILE", mock_jobs_db):
            with patch("tools.infrastructure.routers.cron.LOCK_FILE", tmp_path / "cron_jobs.lock"):
                # 1. Create a job
                payload = {
                    "name": "Audit Logs Task",
                    "prompt": "Run security audit on logs",
                    "schedule": "*/10 * * * *",
                    "deliver": "local"
                }
                res = client.post("/api/v1/cron/jobs", json=payload)
                assert res.status_code == 200
                data = res.json()
                assert data["status"] == "success"
                job_id = data["job"]["id"]
                assert data["job"]["name"] == "Audit Logs Task"
                
                # 2. List jobs
                res = client.get("/api/v1/cron/jobs")
                assert res.status_code == 200
                jobs = res.json()
                assert len(jobs) == 1
                assert jobs[0]["id"] == job_id
                
                # 3. Pause
                res = client.post(f"/api/v1/cron/jobs/{job_id}/pause")
                assert res.status_code == 200
                res = client.get("/api/v1/cron/jobs")
                assert res.json()[0]["enabled"] is False
                
                # 4. Resume
                res = client.post(f"/api/v1/cron/jobs/{job_id}/resume")
                assert res.status_code == 200
                res = client.get("/api/v1/cron/jobs")
                assert res.json()[0]["enabled"] is True
                
                # 5. Delete
                res = client.delete(f"/api/v1/cron/jobs/{job_id}")
                assert res.status_code == 200
                res = client.get("/api/v1/cron/jobs")
                assert len(res.json()) == 0

    def test_mcp_dynamic_registry_crud(self, tmp_path):
        """Tests external MCP server dynamic registry endpoints."""
        mock_mcp_db = tmp_path / "mcp_servers.json"
        
        with patch("tools.infrastructure.routers.mcp.DB_FILE", mock_mcp_db):
            with patch("tools.infrastructure.routers.mcp.LOCK_FILE", tmp_path / "mcp_servers.lock"):
                # 1. Register Weather stdio MCP server
                payload = {
                    "name": "weather-cli",
                    "type": "stdio",
                    "command": "node",
                    "args": ["weather.js"],
                    "env": {"API_KEY": "weather-secret-123"}
                }
                res = client.post("/api/v1/mcp/servers", json=payload)
                assert res.status_code == 200
                data = res.json()
                assert data["status"] == "success"
                assert data["server"]["name"] == "weather-cli"
                
                # 2. List servers (verifying secret redirection/masking)
                res = client.get("/api/v1/mcp/servers")
                assert res.status_code == 200
                servers = res.json()
                assert len(servers) == 1
                assert servers[0]["env"]["API_KEY"] == "********"
                
                # 3. Toggle Enabled
                res = client.put("/api/v1/mcp/servers/weather-cli/enabled", json={"enabled": False})
                assert res.status_code == 200
                res = client.get("/api/v1/mcp/servers")
                assert res.json()[0]["enabled"] is False

    @pytest.mark.asyncio
    async def test_mcp_server_connection_test(self, tmp_path):
        """Tests that testing an MCP server correctly queries capability list using stdio mock client."""
        mock_mcp_db = tmp_path / "mcp_servers.json"
        mock_mcp_db.write_text(json.dumps([{
            "name": "mock-mcp",
            "type": "stdio",
            "command": "node",
            "args": ["mock.js"],
            "env": {},
            "enabled": True
        }]))
        
        # Mock ClientSession and stdio_client
        mock_tools = MagicMock()
        mock_tool_entry = MagicMock()
        mock_tool_entry.name = "get_forecast"
        mock_tools.tools = [mock_tool_entry]
        
        mock_session = AsyncMock()
        mock_session.list_tools.return_value = mock_tools
        
        mock_client_context = MagicMock()
        mock_client_context.__aenter__.return_value = (MagicMock(), MagicMock())
        mock_session_context = MagicMock()
        mock_session_context.__aenter__.return_value = mock_session
        
        with patch("tools.infrastructure.routers.mcp.DB_FILE", mock_mcp_db):
            with patch("tools.infrastructure.routers.mcp.LOCK_FILE", tmp_path / "mcp_servers.lock"):
                with patch("mcp.client.stdio.stdio_client", return_value=mock_client_context):
                    with patch("mcp.ClientSession", return_value=mock_session_context):
                        res = client.post("/api/v1/mcp/servers/mock-mcp/test")
                        assert res.status_code == 200
                        data = res.json()
                        assert data["status"] == "success"
                        assert data["connected"] is True
                        assert "get_forecast" in data["tools"]

    def test_security_bind_gate_fail_closed(self):
        """Tests that lifespan_context throws RuntimeError on non-loopback bind without security keys."""
        from tools.infrastructure.api_server import lifespan_context
        
        # Mock get_or_create_config_token to return empty/None
        with patch("tools.infrastructure.api_server.get_or_create_config_token", return_value=None):
            with patch("tools.infrastructure.api_server.settings") as mock_settings:
                mock_settings.API_HOST = "0.0.0.0" # Public bind
                
                # We expect SystemExit(1) due to sys.exit(1) on critical startup failure
                with pytest.raises(SystemExit) as exc_info:
                    # Initialize lifespan generator
                    gen = lifespan_context(None)
                    # We enter the generator which triggers token verification
                    import asyncio
                    asyncio.run(gen.__aenter__())
                
                assert exc_info.value.code == 1

    def test_themes_list_and_select(self, tmp_path):
        """Tests dashboard themes query and selection."""
        mock_active_file = tmp_path / "active_theme.json"
        
        with patch("tools.infrastructure.routers.extensions.THEME_ACTIVE_FILE", mock_active_file):
            # 1. Query themes
            res = client.get("/api/dashboard/themes")
            assert res.status_code == 200
            data = res.json()
            assert "active" in data
            assert len(data["themes"]) >= 3  # Assert default built-ins
            
            # 2. Select theme
            res = client.put("/api/dashboard/theme", json={"name": "cyberpunk"})
            assert res.status_code == 200
            
            # 3. Query again to check updated active theme
            res = client.get("/api/dashboard/themes")
            assert res.json()["active"] == "cyberpunk"

    @pytest.mark.asyncio
    async def test_plugins_discovery_and_rescan(self, tmp_path):
        """Tests that dashboard plugins are discovered and manifests returned."""
        # Setup mock plugin directories
        plugin_base = tmp_path / "my-plugin"
        manifest_dir = plugin_base / "dashboard"
        manifest_dir.mkdir(parents=True)
        
        manifest_file = manifest_dir / "manifest.json"
        manifest_content = {
            "name": "my-plugin",
            "label": "My Plugin Tab",
            "version": "1.0.0",
            "entry": "dist/index.js",
            "api": "plugin_api.py"
        }
        manifest_file.write_text(json.dumps(manifest_content))
        
        # Write dummy asset file
        dist_dir = manifest_dir / "dist"
        dist_dir.mkdir()
        asset_file = dist_dir / "index.js"
        asset_file.write_text("console.log('hi');")
        
        with patch("tools.infrastructure.routers.extensions.get_plugin_scan_directories", return_value=[tmp_path]):
            # Force clean rescan to load mock plugin
            res = client.get("/api/dashboard/plugins/rescan")
            assert res.status_code == 200
            
            # 2. Query discovered plugins list
            res = client.get("/api/dashboard/plugins")
            assert res.status_code == 200
            plugins = res.json()
            assert len(plugins) == 1
            assert plugins[0]["name"] == "my-plugin"
            
            # 3. Serve asset
            res = client.get("/dashboard-plugins/my-plugin/dist/index.js")
            assert res.status_code == 200
            assert res.text == "console.log('hi');"
            
            # 4. Check directory traversal blocking
            from tools.infrastructure.routers.extensions import serve_plugin_assets
            with pytest.raises(HTTPException) as exc_info:
                await serve_plugin_assets("my-plugin", "../../manifest.json")
            assert exc_info.value.status_code == 403

    def test_proxy_status_telemetry(self):
        """Tests that /api/v1/proxy/status returns status, port, host, and providers."""
        response = client.get("/api/v1/proxy/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["port"] == 8645
        assert data["host"] == "127.0.0.1"
        assert "providers" in data
