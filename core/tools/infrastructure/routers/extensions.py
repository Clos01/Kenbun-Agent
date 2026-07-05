"""
Dashboard Extensions (Themes & Plugins) Router
=============================================
Handles loading, normalisation, and switching of dashboard themes,
and discovery and static asset serving for UI plugins.
"""

import os
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from tools.infrastructure.config import settings
from tools.infrastructure.server_deps import verify_authorization

router = APIRouter()
logger = logging.getLogger(__name__)

THEME_ACTIVE_FILE = settings.BRAIN_HEALTH_DIR / "active_theme.json"
_plugins_cache: Optional[List[Dict[str, Any]]] = None

# Curated built-in themes to fallback on
BUILTIN_THEMES = {
    "default": {
        "name": "default",
        "label": "Kenbun Teal",
        "description": "Dark teal + cream (default)",
        "palette": {"background": "#0a1628", "midground": "#a8d0ff"}
    },
    "midnight": {
        "name": "midnight",
        "label": "Midnight",
        "description": "Deep blue-violet theme",
        "palette": {"background": "#0b0914", "midground": "#7c5dfa"}
    },
    "cyberpunk": {
        "name": "cyberpunk",
        "label": "Cyberpunk",
        "description": "Neon green on black",
        "palette": {"background": "#000000", "midground": "#00ff00"}
    }
}

class ThemeSelection(BaseModel):
    name: str

# ── Themes Implementation ────────────────────────────────────────────────────

def get_themes_directories() -> List[Path]:
    return [
        Path.home() / ".kenbun" / "dashboard-themes",
        Path.home() / ".kenbun" / "dashboard-themes",
    ]

def load_user_themes() -> List[Dict[str, Any]]:
    themes = []
    for directory in get_themes_directories():
        if not directory.exists():
            continue
        for file in directory.glob("*.yaml"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f.read())
                    if data and "name" in data:
                        themes.append(data)
            except Exception as e:
                logger.error(f"Failed to parse user theme {file.name}: {e}")
    return themes

# ── Plugins Implementation ───────────────────────────────────────────────────

def get_plugin_scan_directories() -> List[Path]:
    return [
        settings.PROJECT_ROOT / "plugins" / "memory",
        settings.PROJECT_ROOT / "plugins",
        Path.home() / ".kenbun" / "plugins",
        Path.home() / ".kenbun" / "plugins",
    ]

def discover_plugins() -> List[Dict[str, Any]]:
    global _plugins_cache
    if _plugins_cache is not None:
        return _plugins_cache

    discovered = []
    seen_names = set()
    
    for base_dir in get_plugin_scan_directories():
        if not base_dir.exists():
            continue
            
        for path in base_dir.iterdir():
            if not path.is_dir():
                continue
                
            manifest_file = path / "dashboard" / "manifest.json"
            if manifest_file.exists():
                try:
                    with open(manifest_file, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    
                    name = manifest.get("name", path.name)
                    if name in seen_names:
                        continue # Priority wins
                        
                    seen_names.add(name)
                    
                    # Store absolute path for static serving / route loading
                    manifest["_plugin_path"] = str(path)
                    discovered.append(manifest)
                except Exception as e:
                    logger.error(f"Failed to load plugin manifest at {manifest_file}: {e}")
                    
    _plugins_cache = discovered
    return discovered

# ── API Routes ───────────────────────────────────────────────────────────────

@router.get("/api/dashboard/themes")
async def list_dashboard_themes():
    """Lists all available built-in and user-defined themes."""
    user_themes = load_user_themes()
    
    # Merge builtins and user themes
    all_themes = BUILTIN_THEMES.copy()
    for ut in user_themes:
        name = ut["name"]
        all_themes[name] = {
            "name": name,
            "label": ut.get("label", name.capitalize()),
            "description": ut.get("description", ""),
            "definition": ut
        }
        
    active_theme = "default"
    if THEME_ACTIVE_FILE.exists():
        try:
            with open(THEME_ACTIVE_FILE, "r") as f:
                active_theme = json.load(f).get("active", "default")
        except Exception:
            pass
            
    return {
        "active": active_theme,
        "themes": list(all_themes.values())
    }

@router.put("/api/dashboard/theme", dependencies=[Depends(verify_authorization)])
async def set_dashboard_theme(payload: ThemeSelection):
    """Sets the active dashboard theme."""
    # Check if exists
    user_themes = load_user_themes()
    user_theme_names = [t["name"] for t in user_themes]
    
    if payload.name not in BUILTIN_THEMES and payload.name not in user_theme_names:
        raise HTTPException(status_code=404, detail=f"Theme '{payload.name}' not found.")
        
    try:
        settings.BRAIN_HEALTH_DIR.mkdir(parents=True, exist_ok=True)
        with open(THEME_ACTIVE_FILE, "w") as f:
            json.dump({"active": payload.name}, f)
        return {"status": "success", "message": f"Active theme updated to {payload.name}."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save active theme: {e}")

@router.get("/api/dashboard/plugins")
async def list_dashboard_plugins():
    """Lists all discovered dashboard plugins and UI extensions."""
    plugins = discover_plugins()
    # Redact internal paths before sending to client
    client_list = []
    for p in plugins:
        p_copy = p.copy()
        p_copy.pop("_plugin_path", None)
        client_list.append(p_copy)
    return client_list

@router.get("/api/dashboard/plugins/rescan")
async def rescan_dashboard_plugins():
    """Forces rediscovery and rebuilds the plugin manifest cache."""
    global _plugins_cache
    _plugins_cache = None
    discover_plugins()
    return {"status": "success", "message": "Plugin cache cleared and rebuilt successfully."}

@router.get("/dashboard-plugins/{name}/{file_path:path}")
async def serve_plugin_assets(name: str, file_path: str):
    """Serves static files (JS, CSS, images) from the plugin's dashboard directory."""
    plugins = discover_plugins()
    target_plugin = None
    for p in plugins:
        if p.get("name") == name:
            target_plugin = p
            break
            
    if not target_plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found.")
        
    # Prevent Directory Traversal / Path Injection
    plugin_base = Path(target_plugin["_plugin_path"]) / "dashboard"
    resolved_path = (plugin_base / file_path).resolve()
    
    if not resolved_path.is_relative_to(plugin_base.resolve()):
        raise HTTPException(status_code=403, detail="Access denied: Directory Traversal Detected.")
        
    if not resolved_path.exists() or resolved_path.is_dir():
        raise HTTPException(status_code=404, detail="Resource file not found.")
        
    return FileResponse(resolved_path)
