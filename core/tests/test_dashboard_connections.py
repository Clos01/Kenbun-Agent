import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Ensure core directory is in Python path
import sys
core_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if core_dir not in sys.path:
    sys.path.insert(0, core_dir)

from tools.infrastructure.api_server import app
from tools.infrastructure.server_deps import get_or_create_config_token
from tools.utils import chat_history_manager

client = TestClient(app)


# ---------------------------------------------------------------------------
# Setup Mocking and Graceful Fallback for External Services
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def mock_external_services():
    """
    Checks if local/remote services (ChromaDB, Planka, LLM) are reachable.
    If not, dynamically mocks the connections to ensure robust test execution.
    """
    # 1. Mock get_project_collection for Chroma DB fallback
    mock_collections = {}
    
    class MockChromaCollection:
        def __init__(self, name):
            self.name = name
            
        def get(self, *args, **kwargs):
            if self.name == "code":
                return {
                    "ids": ["node_1"],
                    "embeddings": [[0.1] * 384],
                    "metadatas": [{
                        "file_path": "core/tools/infrastructure/api_server.py",
                        "start_line": 1,
                        "end_line": 10,
                        "room": "Central_Logic"
                    }],
                    "documents": ["def health_check(): pass"]
                }
            elif self.name == "history":
                return {
                    "ids": ["hist_1"],
                    "documents": ["AST Check"],
                    "metadatas": [{
                        "type": "DECISION",
                        "result": "success",
                        "tool": "audit_guardrail",
                        "confidence": 0.95,
                        "timestamp": "2026-06-23T19:00:00Z",
                        "output": "APPROVED"
                    }]
                }
            return {"ids": [], "embeddings": [], "metadatas": [], "documents": []}
            
        def count(self):
            return 1

    def mock_get_collection(name):
        if name not in mock_collections:
            mock_collections[name] = MockChromaCollection(name)
        return mock_collections[name]

    # 2. Mock Planka request fallback
    def mock_planka_request(path: str, method: str = "GET", body=None):
        if method == "GET":
            if "/api/projects" in path:
                return {
                    "items": [{"id": "p1", "name": "Project 1"}],
                    "included": {"boards": [{"id": "b1", "projectId": "p1", "name": "Board 1"}]}
                }
            elif "/api/boards/" in path:
                return {
                    "item": {"name": "Board 1"},
                    "included": {
                        "lists": [{"id": "l1", "name": "List 1", "type": "active", "position": 1.0}],
                        "cards": [{"id": "c1", "listId": "l1", "name": "Card 1", "position": 1.0, "isClosed": False, "description": "Desc", "dueDate": "2026-12-31"}]
                    }
                }
            elif "/comments" in path:
                return [{"id": "comm1", "text": "Test Comment", "userId": "u1"}]
        elif method == "POST":
            if "/cards" in path:
                return {"item": {"id": "c1", "name": "Card 1", "type": "project"}}
            elif "/comments" in path:
                return {"item": {"id": "comm1", "userId": "u1"}}
            elif "/lists" in path:
                return {"item": {"id": "l1", "name": "List 1"}}
            elif "/boards" in path:
                return {"item": {"id": "b1", "name": "Board 1"}}
        elif method == "PATCH":
            if "/cards/" in path:
                return {"item": {"id": "c1", "name": "Card 1", "description": "Desc", "listId": "l1"}}
            elif "/boards/" in path:
                return {"item": {"id": "b1", "name": "Board 1"}}
        elif method == "DELETE":
            return {"status": "deleted"}
        return {}

    # 3. Mock LLM Gateway call
    def mock_call_llm_gateway(*args, **kwargs):
        return "Mock LLM Response"

    # 4. Mock Swarm Orchestrator run
    def mock_orchestrate(*args, **kwargs):
        return {"status": "completed", "result": "Mock Orchestrate Completed"}

    # 5. Mock supervisor save_checkpoint, restore_checkpoint, and audit_guardrail
    def mock_save_checkpoint(*args, **kwargs):
        return "mock_checkpoint_saved"
    def mock_restore_checkpoint(*args, **kwargs):
        return "mock_checkpoint_restored"
    def mock_audit_guardrail(*args, **kwargs):
        return json.dumps({"status": "approved", "critique": "safe"})
    def mock_consult_supervisor(*args, **kwargs):
        return json.dumps({"status": "approved", "critique": "safe"})

    # Determine if we should attempt live connection or fallback
    import socket
    chroma_live = False
    try:
        from tools.infrastructure.config import settings
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            s.connect((settings.CHROMA_HOST, int(settings.CHROMA_PORT)))
            chroma_live = True
    except Exception:
        pass

    planka_live = False
    try:
        import os
        import urllib.request
        base_url = os.environ.get("PLANKA_BASE_URL", "http://127.0.0.1:1337")
        urllib.request.urlopen(base_url, timeout=0.2)
        planka_live = True
    except Exception:
        pass

    patches = []
    if not chroma_live:
        patches.append(patch("tools.infrastructure.routers.intelligence.get_project_collection", mock_get_collection))
        patches.append(patch("tools.infrastructure.routers.telemetry.get_project_collection", mock_get_collection))
    if not planka_live:
        patches.append(patch("tools.infrastructure.routers.planka._planka_request", mock_planka_request))

    patches.append(patch("tools.utils.llm_router.call_llm_gateway", mock_call_llm_gateway))
    patches.append(patch("tools.infrastructure.routers.swarm.orchestrate", mock_orchestrate))
    
    # Mock server tools used by supervisor router
    patches.append(patch("tools.infrastructure.server.save_checkpoint", mock_save_checkpoint))
    patches.append(patch("tools.infrastructure.server.restore_checkpoint", mock_restore_checkpoint))
    patches.append(patch("tools.infrastructure.server.audit_guardrail", mock_audit_guardrail))
    patches.append(patch("tools.infrastructure.server.consult_supervisor", mock_consult_supervisor))

    # Apply all patches
    for p in patches:
        p.start()
        
    yield
    
    for p in patches:
        try:
            p.stop()
        except RuntimeError:
            pass


# ---------------------------------------------------------------------------
# Fixtures for auth and configuration
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_headers():
    """Generates valid Bearer Authorization header using the real token."""
    token = get_or_create_config_token()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def invalid_auth_headers():
    """Generates invalid Bearer Authorization header."""
    return {"Authorization": "Bearer invalid_secret_token_123456"}


@pytest.fixture
def mock_config_env(tmp_path):
    """Sets up a temporary path for config router to prevent modifying the live .env."""
    fake_env = tmp_path / ".env"
    fake_env.write_text("FRONTEND_URL=http://localhost:3000\nAPI_HOST=127.0.0.1\n")
    with patch("tools.infrastructure.routers.config.project_root", tmp_path):
        yield fake_env


@pytest.fixture
def clean_sessions():
    """Backup and restore chat sessions to maintain a clean environment."""
    sessions_file = chat_history_manager.get_sessions_file_path()
    backup_file = sessions_file.with_suffix(".json.bak")
    
    if sessions_file.exists():
        if backup_file.exists():
            backup_file.unlink()
        sessions_file.rename(backup_file)
        
    yield
    
    if sessions_file.exists():
        sessions_file.unlink()
    if backup_file.exists():
        backup_file.rename(sessions_file)


# ---------------------------------------------------------------------------
# 1. Authorization Sanity Checks
# ---------------------------------------------------------------------------

def test_authorization_gates(auth_headers, invalid_auth_headers):
    """Verifies that protected endpoints validate Bearer tokens correctly."""
    # Test GET config:
    # 1. No Authorization header -> 401 Unauthorized
    res = client.get("/api/v1/config")
    assert res.status_code == 401
    
    # 2. Invalid token -> 403 Forbidden
    res = client.get("/api/v1/config", headers=invalid_auth_headers)
    assert res.status_code == 403
    
    # 3. Valid token -> 200 OK
    res = client.get("/api/v1/config", headers=auth_headers)
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# 2. Board Page Endpoints (/board)
# ---------------------------------------------------------------------------

def test_board_structure_endpoint(auth_headers):
    """Tests GET /api/v1/planka/structure."""
    res = client.get("/api/v1/planka/structure", headers=auth_headers)
    assert res.status_code == 200
    assert "items" in res.json() or isinstance(res.json(), list)


def test_board_get_endpoint(auth_headers):
    """Tests GET /api/v1/planka/board/{boardId}."""
    res = client.get("/api/v1/planka/board/b1", headers=auth_headers)
    assert res.status_code == 200
    assert "item" in res.json()


def test_card_comments_endpoint(auth_headers):
    """Tests GET /api/v1/planka/cards/{cardId}/comments."""
    res = client.get("/api/v1/planka/cards/c1/comments", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_create_project_discrepancy(auth_headers):
    """
    Tests POST /api/v1/planka/projects.
    Note: This endpoint is listed in page_endpoints.json but is NOT defined in FastAPI routers.
    We assert 404 to document the dashboard/API discrepancy.
    """
    res = client.post("/api/v1/planka/projects", json={"name": "New Project"}, headers=auth_headers)
    assert res.status_code == 404


def test_create_board_endpoint(auth_headers):
    """Tests POST /api/v1/planka/projects/{projectId}/boards."""
    res = client.post(
        "/api/v1/planka/projects/p1/boards", 
        json={"name": "New Board", "position": 1.0}, 
        headers=auth_headers
    )
    assert res.status_code == 200
    assert "item" in res.json()


def test_patch_board_endpoint(auth_headers):
    """Tests PATCH /api/v1/planka/boards/{boardId}."""
    res = client.patch(
        "/api/v1/planka/boards/b1", 
        json={"name": "Updated Board Name"}, 
        headers=auth_headers
    )
    assert res.status_code == 200
    assert "item" in res.json()


def test_delete_board_endpoint(auth_headers):
    """Tests DELETE /api/v1/planka/boards/{boardId}."""
    res = client.delete("/api/v1/planka/boards/b1", headers=auth_headers)
    assert res.status_code == 200


def test_create_list_endpoint(auth_headers):
    """Tests POST /api/v1/planka/boards/{boardId}/lists."""
    res = client.post(
        "/api/v1/planka/boards/b1/lists", 
        json={"name": "To Do", "position": 10.0}, 
        headers=auth_headers
    )
    assert res.status_code == 200
    assert "item" in res.json()


def test_create_card_endpoint(auth_headers):
    """Tests POST /api/v1/planka/cards."""
    res = client.post(
        "/api/v1/planka/cards", 
        json={"listId": "l1", "name": "Deploy Core Server", "description": "Task desc"}, 
        headers=auth_headers
    )
    assert res.status_code == 200
    assert "item" in res.json()


def test_patch_card_endpoint(auth_headers):
    """Tests PATCH /api/v1/planka/cards/{cardId}."""
    res = client.patch(
        "/api/v1/planka/cards/c1", 
        json={"name": "Hardened Server Deployment"}, 
        headers=auth_headers
    )
    assert res.status_code == 200
    assert "item" in res.json()


def test_create_card_comment_endpoint(auth_headers):
    """Tests POST /api/v1/planka/cards/{cardId}/comments."""
    res = client.post(
        "/api/v1/planka/cards/c1/comments", 
        json={"text": "This task is critical for System 2 compliance"}, 
        headers=auth_headers
    )
    assert res.status_code == 200
    assert "item" in res.json()


# ---------------------------------------------------------------------------
# 3. Chat Page Endpoints (/chat)
# ---------------------------------------------------------------------------

def test_get_chat_sessions(clean_sessions):
    """Tests GET /api/v1/chat/sessions (Public)."""
    res = client.get("/api/v1/chat/sessions")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_create_chat_session(auth_headers, clean_sessions):
    """Tests POST /api/v1/chat/sessions."""
    res = client.post("/api/v1/chat/sessions", json={"title": "Transmission Alpha"}, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    assert data["title"] == "Transmission Alpha"


def test_get_chat_session_by_id(auth_headers, clean_sessions):
    """Tests GET /api/v1/chat/sessions/{id} (Public)."""
    # Create session first
    create_res = client.post("/api/v1/chat/sessions", json={"title": "Query Target"}, headers=auth_headers)
    session_id = create_res.json()["id"]
    
    res = client.get(f"/api/v1/chat/sessions/{session_id}")
    assert res.status_code == 200
    assert res.json()["title"] == "Query Target"


def test_delete_chat_session(auth_headers, clean_sessions):
    """Tests DELETE /api/v1/chat/sessions/{id}."""
    # Create session
    create_res = client.post("/api/v1/chat/sessions", json={"title": "Prune Target"}, headers=auth_headers)
    session_id = create_res.json()["id"]
    
    res = client.delete(f"/api/v1/chat/sessions/{session_id}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "success"


def test_active_model_endpoint():
    """Tests GET /api/v1/active-model (Public)."""
    res = client.get("/api/v1/active-model")
    assert res.status_code == 200
    assert "model" in res.json()


def test_orchestrate_status_endpoint():
    """Tests GET /orchestrate/status/{jobId} (Public)."""
    # 404 for unknown job ID
    res = client.get("/orchestrate/status/non_existent_job_123")
    assert res.status_code == 404


def test_orchestrate_endpoint(auth_headers):
    """Tests POST /orchestrate."""
    payload = {
        "workflow": "research_implement",
        "task": "Review authentication routing",
        "project_path": "."
    }
    res = client.post("/orchestrate", json=payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "initiated"
    assert "job_id" in data


def test_post_message_to_session(auth_headers, clean_sessions):
    """Tests POST /api/v1/chat/sessions/{sessionId}/message."""
    # Create session
    create_res = client.post("/api/v1/chat/sessions", json={"title": "Message Hub"}, headers=auth_headers)
    session_id = create_res.json()["id"]
    
    res = client.post(
        f"/api/v1/chat/sessions/{session_id}/message", 
        json={"message": "System check. Respond."}, 
        headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert "user_message" in data
    assert "ai_message" in data
    assert "session" in data


# ---------------------------------------------------------------------------
# 4. Fleet, Hivemind, Observatory, Settings, Telemetry Shared Endpoints (/stats, /logs, /kanban)
# ---------------------------------------------------------------------------

def test_global_stats_endpoint():
    """Tests GET /stats (Public)."""
    res = client.get("/stats")
    assert res.status_code == 200
    assert "budget" in res.json() or "system" in res.json() or "tools" in res.json()


def test_global_logs_endpoint():
    """Tests GET /logs (Public)."""
    res = client.get("/logs")
    assert res.status_code == 200
    assert "logs" in res.json()


def test_global_kanban_endpoint():
    """Tests GET /kanban (Public)."""
    res = client.get("/kanban")
    assert res.status_code == 200
    assert isinstance(res.json(), list) or "tasks" in res.json()


def test_build_status_endpoint():
    """Tests GET /api/v1/build/status (Public)."""
    res = client.get("/api/v1/build/status")
    assert res.status_code == 200
    assert "status" in res.json()


def test_memory_signals_endpoint():
    """Tests GET /api/v1/memory/signals (Public)."""
    res = client.get("/api/v1/memory/signals")
    assert res.status_code == 200
    assert "signals" in res.json()


def test_intelligence_history_endpoint():
    """Tests GET /api/v1/intelligence/history (Public)."""
    res = client.get("/api/v1/intelligence/history")
    assert res.status_code == 200
    assert "history" in res.json()


def test_hivemind_concepts_endpoint():
    """Tests GET /api/v1/hivemind/concepts (Public)."""
    res = client.get("/api/v1/hivemind/concepts")
    assert res.status_code == 200
    assert "concepts" in res.json()


# ---------------------------------------------------------------------------
# 5. Config Endpoints (/settings)
# ---------------------------------------------------------------------------

def test_get_config_endpoint(auth_headers):
    """Tests GET /api/v1/config."""
    res = client.get("/api/v1/config", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert "config" in res.json()


def test_update_config_endpoint(auth_headers, mock_config_env):
    """Tests POST /api/v1/config."""
    # We patch update_config's Settings class validation to bypass strict validation issues
    with patch("tools.infrastructure.config.KenbunSettings") as mock_settings_class:
        res = client.post(
            "/api/v1/config", 
            json={"settings": {"FRONTEND_URL": "http://localhost:3000"}}, 
            headers=auth_headers
        )
        assert res.status_code == 200
        assert res.json()["status"] == "success"


# ---------------------------------------------------------------------------
# 6. Supervisor Endpoints (/supervisor)
# ---------------------------------------------------------------------------

def test_supervisor_checkpoints_get_endpoint():
    """Tests GET /api/v1/supervisor/checkpoints (Public)."""
    res = client.get("/api/v1/supervisor/checkpoints")
    assert res.status_code == 200
    assert "data" in res.json()


def test_supervisor_guardrails_endpoint():
    """Tests GET /api/v1/supervisor/guardrails (Public)."""
    res = client.get("/api/v1/supervisor/guardrails")
    assert res.status_code == 200
    assert "data" in res.json()


def test_supervisor_stats_endpoint():
    """Tests GET /api/v1/supervisor/stats (Public)."""
    res = client.get("/api/v1/supervisor/stats")
    assert res.status_code == 200
    assert "data" in res.json()


def test_supervisor_create_checkpoint(auth_headers):
    """Tests POST /api/v1/supervisor/checkpoints."""
    payload = {"name": "test_chkpt", "description": "dashboard connection test checkpoint"}
    res = client.post("/api/v1/supervisor/checkpoints", json=payload, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "success"


def test_supervisor_restore_checkpoint(auth_headers):
    """Tests POST /api/v1/supervisor/checkpoints/{checkpoint_hash}/restore."""
    res = client.post("/api/v1/supervisor/checkpoints/somehash123/restore", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "success"


def test_supervisor_audit_endpoint(auth_headers):
    """Tests POST /api/v1/supervisor/audit."""
    payload = {
        "code_snippet": "def test(): print('Secure Code')",
        "audit_type": "security",
        "iterative_mode": False
    }
    res = client.post("/api/v1/supervisor/audit", json=payload, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert "data" in res.json()


# ---------------------------------------------------------------------------
# 7. Telemetry SSE Logs Stream Endpoint (/telemetry)
# ---------------------------------------------------------------------------

def test_logs_stream_endpoint():
    """Verifies that GET /api/v1/logs/stream is registered in FastAPI routes."""
    routes = []
    for r in app.routes:
        if hasattr(r, "path"):
            routes.append(r.path)
        elif hasattr(r, "original_router") and hasattr(r.original_router, "routes"):
            prefix = getattr(r, "prefix", "")
            for sr in r.original_router.routes:
                if hasattr(sr, "path"):
                    routes.append(prefix + sr.path)
    assert "/api/v1/logs/stream" in routes
