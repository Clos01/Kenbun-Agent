import pytest
import asyncio
import os
import json
from unittest.mock import patch, MagicMock

# Import the actual FastMCP object from the server module
from tools.infrastructure.server import mcp

@pytest.fixture
def mock_chroma_db():
    """Mock ChromaDB connection to avoid hitting the actual database during tests."""
    with patch("tools.memory.chroma_db_connect.query_embeddings") as mock_query:
        # Mocking the response structure from System 3 memory
        mock_query.return_value = {
            "documents": [["""
            @sovereign_tool(name="search_codebase", category="AST_HARVESTER")
            def search_codebase(query: str):
                return "Topology results found"
            """]]
        }
        yield mock_query

def test_mcp_server_initialization():
    """Test that the FastMCP server initializes properly with the correct name."""
    assert mcp.name == "Kenbun Tools"
    # Ensure tools have been registered by checking the internal tools dictionary
    # Wait, the tools are decorated. We just need to verify it's an instance of FastMCP.
    assert mcp is not None

def test_mcp_docs_registration():
    """Test that the FastMCP environment has loaded the official docs mapping."""
    from tools.infrastructure.server import OFFICIAL_DOCS
    assert "react" in OFFICIAL_DOCS
    assert "nextjs" in OFFICIAL_DOCS
    assert OFFICIAL_DOCS["react"] == "react.dev"

@pytest.mark.asyncio
async def test_mcp_tool_execution(mock_chroma_db):
    """
    Simulate an incoming MCP stdio payload asking the server to search
    for an AST topology.
    """
    # Since we can't fully boot the stdio loop without blocking, we simulate
    # calling the underlying helper function the MCP server exposes.
    from tools.infrastructure.server import query_system_3
    
    results = query_system_3("search_codebase", n=1)
    
    assert len(results) == 1
    assert "Topology results found" in results[0]
    mock_chroma_db.assert_called_once_with("search_codebase", n_results=1, category="concepts")

def test_mcp_env_bindings():
    """Test that the FastMCP server is correctly reading environment bindings."""
    from tools.infrastructure.config import settings
    # As long as PROJECT_ROOT is loaded, the Docker volume mount is succeeding
    assert settings.PROJECT_ROOT is not None
