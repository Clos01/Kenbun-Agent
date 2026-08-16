"""
MCP Server Registry Router
==========================
Handles registration, testing, and lifecycle of external Model Context
Protocol (MCP) servers that Kenbun can connect to.
"""

import os
import json
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException

from tools.infrastructure.config import settings
from tools.infrastructure.server_deps import verify_authorization

router = APIRouter()
logger = logging.getLogger(__name__)

DB_FILE = settings.BRAIN_HEALTH_DIR / "mcp_servers.json"
LOCK_FILE = settings.BRAIN_HEALTH_DIR / "mcp_servers.lock"

# ── Pydantic Request Models ──────────────────────────────────────────────────

class MCPServerRegister(BaseModel):
    name: str = Field(..., min_length=1, description="Unique name for the MCP server")
    type: str = Field("stdio", description="Connection type: stdio or sse")
    command: Optional[str] = Field(None, description="Executable command for stdio server")
    args: Optional[List[str]] = Field(None, description="Command line arguments for stdio server")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables for stdio server")
    url: Optional[str] = Field(None, description="HTTP/SSE URL for sse server")

class MCPEnabledToggle(BaseModel):
    enabled: bool

# ── Lock Protection ──────────────────────────────────────────────────────────

def _acquire_lock(timeout: float = 3.0) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            return True
        except FileExistsError:
            time.sleep(0.05)
    return False

def _release_lock():
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception as e:
        logger.error(f"Error releasing MCP lock: {e}")

def _load_servers() -> List[Dict[str, Any]]:
    if not DB_FILE.exists():
        return []
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else []
    except Exception as e:
        logger.error(f"Failed to load MCP servers: {e}")
        return []

def _save_servers(servers: List[Dict[str, Any]]) -> bool:
    temp_file = DB_FILE.with_suffix(".tmp")
    try:
        settings.BRAIN_HEALTH_DIR.mkdir(parents=True, exist_ok=True)
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(servers, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        if temp_file.exists():
            temp_file.replace(DB_FILE)
        return True
    except Exception as e:
        logger.error(f"Failed to save MCP servers: {e}")
        if temp_file.exists():
            temp_file.unlink()
        return False

def load_servers_safe() -> List[Dict[str, Any]]:
    if _acquire_lock():
        try:
            return _load_servers()
        finally:
            _release_lock()
    return []

def save_servers_safe(servers: List[Dict[str, Any]]) -> bool:
    if _acquire_lock():
        try:
            return _save_servers(servers)
        finally:
            _release_lock()
    return False

# ── API Routes ───────────────────────────────────────────────────────────────

@router.get("/api/v1/mcp/servers", dependencies=[Depends(verify_authorization)])
async def list_mcp_servers():
    """Lists all registered MCP servers, redacting sensitive env values."""
    servers = load_servers_safe()
    redacted_list = []
    for s in servers:
        s_copy = s.copy()
        if "env" in s_copy and s_copy["env"]:
            redacted_env = {}
            for k, v in s_copy["env"].items():
                if any(p in k.upper() for p in ["KEY", "TOKEN", "SECRET", "PASSWORD"]):
                    redacted_env[k] = "********" if v else ""
                else:
                    redacted_env[k] = v
            s_copy["env"] = redacted_env
        redacted_list.append(s_copy)
    return redacted_list

@router.post("/api/v1/mcp/servers", dependencies=[Depends(verify_authorization)])
async def register_mcp_server(payload: MCPServerRegister):
    """Registers or updates an MCP server configuration."""
    if payload.type == "stdio" and not payload.command:
        raise HTTPException(status_code=400, detail="Command is required for stdio type server.")
    if payload.type == "sse" and not payload.url:
        raise HTTPException(status_code=400, detail="URL is required for sse type server.")

    servers = load_servers_safe()
    # Remove existing if any
    servers = [s for s in servers if s["name"] != payload.name]
    
    new_server = {
        "name": payload.name,
        "type": payload.type,
        "command": payload.command,
        "args": payload.args or [],
        "env": payload.env or {},
        "url": payload.url,
        "enabled": True
    }
    servers.append(new_server)
    if save_servers_safe(servers):
        return {"status": "success", "server": new_server}
    raise HTTPException(status_code=500, detail="Failed to save MCP server registry.")

@router.delete("/api/v1/mcp/servers/{name}", dependencies=[Depends(verify_authorization)])
async def delete_mcp_server(name: str):
    """Deletes an MCP server registry by name."""
    servers = load_servers_safe()
    filtered = [s for s in servers if s["name"] != name]
    if len(filtered) == len(servers):
        raise HTTPException(status_code=404, detail="MCP server not found.")
    if save_servers_safe(filtered):
        return {"status": "success", "message": f"MCP server {name} removed."}
    raise HTTPException(status_code=500, detail="Failed to remove MCP server.")

@router.put("/api/v1/mcp/servers/{name}/enabled", dependencies=[Depends(verify_authorization)])
async def toggle_mcp_server(name: str, payload: MCPEnabledToggle):
    """Toggles enabled state of an MCP server."""
    servers = load_servers_safe()
    found = False
    for s in servers:
        if s["name"] == name:
            s["enabled"] = payload.enabled
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="MCP server not found.")
    if save_servers_safe(servers):
        return {"status": "success", "message": f"MCP server {name} enabled state updated."}
    raise HTTPException(status_code=500, detail="Failed to update enabled state.")

@router.post("/api/v1/mcp/servers/{name}/test", dependencies=[Depends(verify_authorization)])
async def test_mcp_server(name: str):
    """Tests connection to the specified MCP server, querying its tool list."""
    servers = load_servers_safe()
    target = None
    for s in servers:
        if s["name"] == name:
            target = s
            break
            
    if not target:
        raise HTTPException(status_code=404, detail="MCP server not found.")
        
    try:
        from mcp import ClientSession, StdioServerParameters
        
        if target["type"] == "stdio":
            from mcp.client.stdio import stdio_client
            
            server_params = StdioServerParameters(
                command=target["command"],
                args=target["args"] or [],
                env={**os.environ, **(target["env"] or {})}
            )
            
            # Connect with short timeout
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await asyncio.wait_for(session.initialize(), timeout=5.0)
                    tools_res = await asyncio.wait_for(session.list_tools(), timeout=5.0)
                    tool_names = [t.name for t in tools_res.tools]
                    return {
                        "status": "success",
                        "connected": True,
                        "tools": tool_names
                    }
                    
        elif target["type"] == "sse":
            from mcp.client.sse import sse_client
            
            async with sse_client(target["url"]) as (read, write):
                async with ClientSession(read, write) as session:
                    await asyncio.wait_for(session.initialize(), timeout=5.0)
                    tools_res = await asyncio.wait_for(session.list_tools(), timeout=5.0)
                    tool_names = [t.name for t in tools_res.tools]
                    return {
                        "status": "success",
                        "connected": True,
                        "tools": tool_names
                    }
    except Exception as e:
        logger.error(f"Connection test failed for MCP server '{name}': {e}")
        return {
            "status": "failed",
            "connected": False,
            "error": str(e)
        }
