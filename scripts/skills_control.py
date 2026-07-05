#!/usr/bin/env python3
"""
Kenbun Skills Manager CLI
=========================
Manages active and optional skills within the Kenbun ecosystem.
"""

import os
import sys
import shutil
import re
import argparse
from pathlib import Path

# Add project root and core directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "core"))

from tools.infrastructure.config import settings

ACTIVE_SKILLS_DIR = root_dir / "core" / "tools" / "skills"
OPTIONAL_SKILLS_DIR = root_dir / "optional_skills"

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
        return False, f"Missing SKILL.md file at {skill_file.name}"
        
    try:
        content = skill_file.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"Failed to read SKILL.md: {e}"
        
    if not content.startswith("---"):
        return False, "SKILL.md must start with YAML frontmatter block (---)"
        
    metadata = parse_yaml_frontmatter(content)
    
    if "kenbun" not in metadata:
        # Check if the skill complies with global customizations rule
        # If it doesn't have a kenbun section, but is just a generic skill, we can accept it
        # or require 'kenbun' namespace. Let's require it to follow PROTOCOL.md.
        return False, "Missing 'kenbun' section in frontmatter"
        
    kenbun_meta = metadata["kenbun"]
    if not isinstance(kenbun_meta, dict):
        return False, "'kenbun' in frontmatter must be a dictionary block"
        
    # Check mode
    mode = kenbun_meta.get("mode")
    if mode not in ["prototype", "deck", "document"]:
        return False, f"Invalid or missing mode '{mode}'. Must be prototype, deck, or document."
        
    # Check fidelity
    fidelity = kenbun_meta.get("fidelity")
    if fidelity not in ["high", "wireframe"]:
        return False, f"Invalid or missing fidelity '{fidelity}'. Must be high or wireframe."
        
    # Check tech_stack
    tech_stack = kenbun_meta.get("tech_stack")
    if not isinstance(tech_stack, list):
        return False, "'tech_stack' must be a list of technologies"
        
    # Check discovery_required
    discovery = kenbun_meta.get("discovery_required")
    if not isinstance(discovery, bool):
        return False, "'discovery_required' must be a boolean"
        
    return True, "Valid"

def list_skills():
    """Lists active and optional available skills."""
    active_skills = []
    if ACTIVE_SKILLS_DIR.exists():
        for p in ACTIVE_SKILLS_DIR.iterdir():
            if p.is_dir() and (p / "SKILL.md").exists():
                is_valid, msg = validate_skill_metadata(p)
                active_skills.append({
                    "name": p.name,
                    "status": "active",
                    "valid": is_valid,
                    "validation_message": msg,
                    "path": str(p)
                })

    optional_skills = []
    if OPTIONAL_SKILLS_DIR.exists():
        for p in OPTIONAL_SKILLS_DIR.iterdir():
            if p.is_dir() and (p / "SKILL.md").exists():
                # Avoid listing as optional if it is already active
                if p.name in [s["name"] for s in active_skills]:
                    continue
                is_valid, msg = validate_skill_metadata(p)
                optional_skills.append({
                    "name": p.name,
                    "status": "available",
                    "valid": is_valid,
                    "validation_message": msg,
                    "path": str(p)
                })

    print("🏛️ Kenbun Active Skills:")
    if not active_skills:
        print("  (None)")
    for s in active_skills:
        val_str = "✅ Valid" if s["valid"] else f"❌ Invalid: {s['validation_message']}"
        print(f"  🟢 {s['name']:<20} ({val_str})")

    print("\n📦 Available Optional Skills:")
    if not optional_skills:
        print("  (None)")
    for s in optional_skills:
        val_str = "✅ Valid" if s["valid"] else f"❌ Invalid: {s['validation_message']}"
        print(f"  ⚪ {s['name']:<20} ({val_str})")

    return active_skills + optional_skills

def install_skill(skill_name: str, force: bool = False):
    """Installs an optional skill to active skills directory."""
    src = OPTIONAL_SKILLS_DIR / skill_name
    dest = ACTIVE_SKILLS_DIR / skill_name

    if not src.exists():
        print(f"Error: Optional skill '{skill_name}' does not exist under {OPTIONAL_SKILLS_DIR.name}/")
        sys.exit(1)

    # Validate first
    is_valid, msg = validate_skill_metadata(src)
    if not is_valid and not force:
        print(f"❌ Validation Failed for '{skill_name}': {msg}")
        print("Installation aborted. Use --force to override validation (not recommended).")
        sys.exit(1)

    print(f"Installing skill '{skill_name}'...")
    ACTIVE_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        print(f"Skill '{skill_name}' is already active. Overwriting...")
        shutil.rmtree(dest)

    shutil.copytree(src, dest)
    print(f"✅ Successfully installed '{skill_name}' to {dest.relative_to(root_dir)}")

def uninstall_skill(skill_name: str):
    """Uninstalls/removes an active skill."""
    dest = ACTIVE_SKILLS_DIR / skill_name

    if not dest.exists():
        print(f"Error: Skill '{skill_name}' is not currently active.")
        sys.exit(1)

    print(f"Uninstalling skill '{skill_name}'...")
    shutil.rmtree(dest)
    print(f"✅ Successfully uninstalled '{skill_name}'.")

def reset_skill(skill_name: str, restore: bool = False):
    """Resets/restores a skill from optional catalog."""
    if not restore:
        print("Error: Please provide --restore flag to reset/restore a skill.")
        sys.exit(1)
    install_skill(skill_name, force=True)

def main():
    parser = argparse.ArgumentParser(description="Kenbun Skills Manager CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # List command
    subparsers.add_parser("list", help="List active and available optional skills")

    # Install command
    install_parser = subparsers.add_parser("install", help="Install an optional skill")
    install_parser.add_argument("skill_name", help="Name of the optional skill to install")
    install_parser.add_argument("--force", action="store_true", help="Force install and skip validation")

    # Uninstall command
    uninstall_parser = subparsers.add_parser("uninstall", help="Uninstall/remove an active skill")
    uninstall_parser.add_argument("skill_name", help="Name of the active skill to uninstall")

    # Reset command
    reset_parser = subparsers.add_parser("reset", help="Reset/restore a skill")
    reset_parser.add_argument("skill_name", help="Name of the skill to restore")
    reset_parser.add_argument("--restore", action="store_true", required=True, help="Must be set to confirm restore")

    args = parser.parse_args()

    if args.command == "list":
        list_skills()
    elif args.command == "install":
        install_skill(args.skill_name, args.force)
    elif args.command == "uninstall":
        uninstall_skill(args.skill_name)
    elif args.command == "reset":
        reset_skill(args.skill_name, args.restore)

if __name__ == "__main__":
    main()
