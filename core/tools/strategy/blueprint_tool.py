import os
import yaml
import json
import logging
from pathlib import Path
from tools.registry import sovereign_tool
from tools.infrastructure.config import settings
from tools.strategy.cronjob_tool import cronjob

logger = logging.getLogger("blueprint_tool")

def get_skills_search_paths():
    paths = []
    # 1. Repository-native skills
    paths.append(Path(settings.PROJECT_ROOT) / "core" / "tools" / "skills")
    # 2. Workspace customizations root
    paths.append(Path(settings.PROJECT_ROOT) / ".agents" / "skills")
    # 3. Global customizations root
    paths.append(Path.home() / ".gemini" / "config" / "skills")
    return [p for p in paths if p.exists()]

def find_blueprints():
    blueprints = {}
    search_paths = get_skills_search_paths()
    
    for base_dir in search_paths:
        for skill_dir in base_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md_path = skill_dir / "SKILL.md"
            if not skill_md_path.exists():
                continue
                
            try:
                content = skill_md_path.read_text(encoding="utf-8")
                if not content.startswith("---"):
                    continue
                    
                parts = content.split("---", 2)
                if len(parts) < 3:
                    continue
                    
                metadata = yaml.safe_load(parts[1])
                if not metadata or "blueprint" not in metadata:
                    continue
                    
                bp_meta = metadata["blueprint"]
                bp_name = metadata.get("name", skill_dir.name)
                
                blueprints[bp_name] = {
                    "name": bp_name,
                    "description": metadata.get("description", bp_meta.get("description", "No description provided.")),
                    "default_schedule": bp_meta.get("default_schedule", "0 9 * * *"),
                    "inputs": bp_meta.get("inputs", []),
                    "prompt_template": bp_meta.get("prompt_template", ""),
                    "path": str(skill_md_path)
                }
            except Exception as e:
                logger.debug(f"Failed parsing blueprint in {skill_dir}: {e}")
                
    return blueprints

@sovereign_tool(name="blueprint", category="Strategy")
def blueprint(
    action: str,
    name: str = "",
    schedule: str = "",
    params: str = "",
    job_name: str = ""
) -> str:
    """
    Manage ready-to-run scheduled automation templates (blueprints) in Kenbun.
    
    Supported Actions:
      - 'list': List all available blueprints.
      - 'get': Retrieve parameters and details of a specific blueprint.
      - 'schedule': Instantiates and schedules a blueprint as a Chronos cronjob.
      
    Args:
      action: The blueprint operation to perform ('list', 'get', 'schedule').
      name: Name of the target blueprint (required for 'get' and 'schedule').
      schedule: Optional custom schedule string. Overrides the blueprint's default_schedule if provided.
      params: Comma-separated key=value inputs or a JSON object string of parameters for the blueprint template.
      job_name: Custom name for the created cronjob. Defaults to 'blueprint_<name>'.
    """
    action_clean = action.strip().lower()
    
    # Load all discovered blueprints
    all_blueprints = find_blueprints()
    
    if action_clean == "list":
        # Format a clean list overview
        brief_list = []
        for bp in all_blueprints.values():
            brief_list.append({
                "name": bp["name"],
                "description": bp["description"],
                "default_schedule": bp["default_schedule"],
                "inputs": [{"name": i["name"], "default": i.get("default"), "description": i.get("description", "")} for i in bp["inputs"]]
            })
        return json.dumps(brief_list, indent=2)
        
    elif action_clean == "get":
        if not name:
            return json.dumps({"status": "error", "message": "Parameter 'name' is required for action 'get'."}, indent=2)
            
        bp = all_blueprints.get(name)
        if not bp:
            return json.dumps({"status": "error", "message": f"Blueprint '{name}' not found. Use 'list' to see available options."}, indent=2)
            
        return json.dumps(bp, indent=2)
        
    elif action_clean == "schedule":
        if not name:
            return json.dumps({"status": "error", "message": "Parameter 'name' is required for action 'schedule'."}, indent=2)
            
        bp = all_blueprints.get(name)
        if not bp:
            return json.dumps({"status": "error", "message": f"Blueprint '{name}' not found. Use 'list' to see available options."}, indent=2)
            
        # Parse inputs
        parsed_params = {}
        if params:
            params_clean = params.strip()
            if params_clean.startswith("{") and params_clean.endswith("}"):
                try:
                    parsed_params = json.loads(params_clean)
                except json.JSONDecodeError as e:
                    return json.dumps({"status": "error", "message": f"Failed to parse params JSON: {e}"}, indent=2)
            else:
                # Parse as comma-separated key=value pairs (e.g. time=08:00,deliver=origin)
                pairs = [p.strip() for p in params_clean.split(",") if "=" in p]
                for pair in pairs:
                    k, v = pair.split("=", 1)
                    parsed_params[k.strip()] = v.strip()
                    
        # Apply defaults and validate inputs
        resolved_params = {}
        missing_required = []
        
        for input_spec in bp["inputs"]:
            i_name = input_spec["name"]
            i_required = input_spec.get("required", False)
            i_default = input_spec.get("default")
            
            val = parsed_params.get(i_name)
            if val is None:
                if i_required:
                    missing_required.append(i_name)
                else:
                    resolved_params[i_name] = i_default
            else:
                # Convert type if necessary
                i_type = input_spec.get("type", "string")
                try:
                    if i_type == "integer":
                        resolved_params[i_name] = int(val)
                    elif i_type == "boolean":
                        resolved_params[i_name] = str(val).lower() in ("true", "1", "yes")
                    else:
                        resolved_params[i_name] = str(val)
                except ValueError:
                    return json.dumps({"status": "error", "message": f"Invalid type for parameter '{i_name}': expected {i_type}."}, indent=2)
                    
        if missing_required:
            return json.dumps({
                "status": "error",
                "message": f"Missing required parameters for blueprint '{name}': {', '.join(missing_required)}"
            }, indent=2)
            
        # Format the prompt template
        try:
            formatted_prompt = bp["prompt_template"].format(**resolved_params)
        except KeyError as ke:
            return json.dumps({"status": "error", "message": f"Template formatting error: missing key {ke} in parameters."}, indent=2)
            
        # Resolve schedule and targets
        target_schedule = schedule if schedule else bp["default_schedule"]
        deliver_val = resolved_params.get("deliver", "origin")
        
        cron_job_name = job_name if job_name else f"blueprint_{name}"
        
        # Determine if it's a watchdog (e.g. important-mail) to enable no_agent mode
        no_agent_flag = False
        script_val = ""
        # If watchdog requires a specific pre-check script
        if name == "important-mail":
            # For important-mail, we can set no_agent = False but pass prompt since it triages.
            # But wait, we can also customize it as desired.
            pass
            
        # Invoke the cronjob tool directly
        cron_res_str = cronjob(
            action="create",
            name=cron_job_name,
            schedule=target_schedule,
            prompt=formatted_prompt,
            delivery_targets=deliver_val
        )
        
        try:
            cron_res = json.loads(cron_res_str)
            if cron_res.get("status") == "success":
                return json.dumps({
                    "status": "success",
                    "message": f"Successfully scheduled blueprint '{name}' as job '{cron_job_name}'",
                    "job_id": cron_res.get("job_id"),
                    "schedule": target_schedule,
                    "next_run_at": cron_res.get("next_run_at")
                }, indent=2)
            else:
                return json.dumps({
                    "status": "error",
                    "message": f"Failed to create cron job for blueprint: {cron_res.get('message')}"
                }, indent=2)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"Failed to parse cron creation response: {e}. Raw response: {cron_res_str}"
            }, indent=2)
            
    else:
        return json.dumps({"status": "error", "message": f"Unknown action '{action}'. Action must be list, get, or schedule."}, indent=2)
