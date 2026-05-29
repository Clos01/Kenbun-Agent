import json
import os
from pathlib import Path
from typing import List, Dict, Any

class WorkspaceManager:
    """
    Manages the Kenbun project registry and auto-discovery logic.
    """
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to workspace_config.json in project root
            from tools.infrastructure.config import settings
            self.config_path = settings.PROJECT_ROOT / "workspace_config.json"
        else:
            self.config_path = Path(config_path)
            
    def load_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return {"projects": [], "workspace_root": str(self.config_path.parent.parent), "auto_discovery": False}
        
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Failed to load workspace config: {e}")
            return {"projects": [], "workspace_root": str(self.config_path.parent.parent), "auto_discovery": False}

    def get_projects(self) -> List[str]:
        config = self.load_config()
        projects = config.get("projects", [])
        
        # Ensure paths are expanded and absolute
        projects = [str(Path(p).expanduser().resolve()) for p in projects]
        
        # Auto-discovery if enabled
        if config.get("auto_discovery"):
            root = Path(config.get("workspace_root", "")).expanduser().resolve()
            if root.exists() and str(root) != "/":
                # Scan for directories containing .kenbun_rules.md or AG_TASKS.md
                for item in root.iterdir():
                    if item.is_dir() and str(item) not in projects:
                        if (item / ".kenbun_rules.md").exists() or (item / "AG_TASKS.md").exists():
                            projects.append(str(item))
        
        return list(set(projects)) # Deduplicate

    def add_project(self, project_path: str):
        config = self.load_config()
        projects = config.get("projects", [])
        abs_path = str(Path(project_path).expanduser().resolve())
        
        if abs_path not in projects:
            projects.append(abs_path)
            config["projects"] = projects
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=4)
            return True
        return False

# Global Instance
workspace_manager = WorkspaceManager()
