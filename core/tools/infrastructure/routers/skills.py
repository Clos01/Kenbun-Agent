"""
REST API Router: Skills Manager
===============================
Exposes endpoints to list, install, and uninstall skills.
"""

import re
import shutil
from pathlib import Path
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from tools.infrastructure.config import settings

router = APIRouter()

# Resolve directories relative to project root
ACTIVE_SKILLS_DIR = settings.PROJECT_ROOT / "core" / "tools" / "skills"
OPTIONAL_SKILLS_DIR = settings.PROJECT_ROOT / "optional_skills"

def parse_yaml_frontmatter(content: str) -> dict:
    """Robust, dependency-free YAML-like frontmatter parser for basic metadata."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return {}
    
    frontmatter_text = match.group(1)
    data = {}
    current_key = None
    
    for line in frontmatter_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
            
        if line.startswith("-") or line.startswith("  "):
            item = line.lstrip("- ").strip()
            if current_key and isinstance(data[current_key], list):
                data[current_key].append(item)
            continue
            
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            
            if val == "":
                data[key] = {}
                current_key = key
            elif current_key and isinstance(data.get(current_key), dict):
                if val.startswith("[") and val.endswith("]"):
                    items = [i.strip().strip("'\"") for i in val[1:-1].split(",") if i.strip()]
                    data[current_key][key] = items
                else:
                    if val.lower() == "true":
                        data[current_key][key] = True
                    elif val.lower() == "false":
                        data[current_key][key] = False
                    else:
                        data[current_key][key] = val
            else:
                if val.startswith("[") and val.endswith("]"):
                    data[key] = [i.strip().strip("'\"") for i in val[1:-1].split(",") if i.strip()]
                else:
                    if val.lower() == "true":
                        data[key] = True
                    elif val.lower() == "false":
                        data[key] = False
                    else:
                        data[key] = val
                current_key = key
                
    return data

def validate_skill_metadata(skill_path: Path) -> tuple[bool, str]:
    """Ensures a skill's SKILL.md complies with the Kenbun protocol."""
    skill_file = skill_path / "SKILL.md"
    if not skill_file.exists():
        return False, "Missing SKILL.md file"
        
    try:
        content = skill_file.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"Failed to read SKILL.md: {e}"
        
    if not content.startswith("---"):
        return False, "SKILL.md must start with YAML frontmatter block (---)"
        
    metadata = parse_yaml_frontmatter(content)
    
    if "kenbun" not in metadata:
        return False, "Missing 'kenbun' section in frontmatter"
        
    kenbun_meta = metadata["kenbun"]
    if not isinstance(kenbun_meta, dict):
        return False, "'kenbun' in frontmatter must be a dictionary block"
        
    mode = kenbun_meta.get("mode")
    if mode not in ["prototype", "deck", "document"]:
        return False, f"Invalid or missing mode '{mode}'. Must be prototype, deck, or document."
        
    fidelity = kenbun_meta.get("fidelity")
    if fidelity not in ["high", "wireframe"]:
        return False, f"Invalid or missing fidelity '{fidelity}'. Must be high or wireframe."
        
    tech_stack = kenbun_meta.get("tech_stack")
    if not isinstance(tech_stack, list):
        return False, "'tech_stack' must be a list of technologies"
        
    discovery = kenbun_meta.get("discovery_required")
    if not isinstance(discovery, bool):
        return False, "'discovery_required' must be a boolean"
        
    return True, "Valid"

@router.get("/api/v1/skills")
async def get_skills():
    """Lists active and available optional skills."""
    active_skills = []
    if ACTIVE_SKILLS_DIR.exists():
        for p in ACTIVE_SKILLS_DIR.iterdir():
            if p.is_dir() and (p / "SKILL.md").exists():
                is_valid, msg = validate_skill_metadata(p)
                active_skills.append({
                    "name": p.name,
                    "status": "active",
                    "valid": is_valid,
                    "validation_message": msg
                })

    optional_skills = []
    if OPTIONAL_SKILLS_DIR.exists():
        for p in OPTIONAL_SKILLS_DIR.iterdir():
            if p.is_dir() and (p / "SKILL.md").exists():
                # Avoid listing as optional if already active
                if p.name in [s["name"] for s in active_skills]:
                    continue
                is_valid, msg = validate_skill_metadata(p)
                optional_skills.append({
                    "name": p.name,
                    "status": "available",
                    "valid": is_valid,
                    "validation_message": msg
                })

    return {
        "status": "success",
        "skills": active_skills + optional_skills
    }

@router.post("/api/v1/skills/install")
async def install_skill_route(request: Request):
    """Installs an optional skill to active skills."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    skill_name = body.get("name")
    force = body.get("force", False)

    if not skill_name:
        raise HTTPException(status_code=400, detail="Missing 'name' in request body.")

    src = OPTIONAL_SKILLS_DIR / skill_name
    dest = ACTIVE_SKILLS_DIR / skill_name

    if not src.exists():
        raise HTTPException(status_code=404, detail=f"Optional skill '{skill_name}' does not exist.")

    # Validate metadata
    is_valid, msg = validate_skill_metadata(src)
    if not is_valid and not force:
        raise HTTPException(status_code=400, detail=f"Skill validation failed: {msg}")

    ACTIVE_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        shutil.rmtree(dest)

    try:
        shutil.copytree(src, dest)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to copy skill: {str(e)}")

    return {
        "status": "success",
        "message": f"Skill '{skill_name}' installed successfully."
    }

@router.post("/api/v1/skills/uninstall")
async def uninstall_skill_route(request: Request):
    """Uninstalls/removes an active skill."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    skill_name = body.get("name")

    if not skill_name:
        raise HTTPException(status_code=400, detail="Missing 'name' in request body.")

    dest = ACTIVE_SKILLS_DIR / skill_name

    if not dest.exists():
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' is not currently active.")

    try:
        shutil.rmtree(dest)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove skill: {str(e)}")

    return {
        "status": "success",
        "message": f"Skill '{skill_name}' uninstalled successfully."
    }
