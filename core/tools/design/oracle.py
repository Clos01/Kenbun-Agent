import os
import json
import re
import yaml
from pathlib import Path

class DesignOracle:
    """
    The Design Oracle retrieves architectural and visual rules 
    from the Sovereign Design library (DESIGN.md).
    """
    
    from tools.infrastructure.config import settings
    DESIGN_FILE = settings.PROJECT_ROOT / "DESIGN.md"

    @classmethod
    def get_rules(cls):
        if not cls.DESIGN_FILE.exists():
            # Fallback to legacy structure if root DESIGN.md is missing
            legacy_path = cls.settings.PROJECT_ROOT / "design_systems" / "sovereign-sharp" / "DESIGN.md"
            if legacy_path.exists():
                with open(legacy_path, 'r') as f:
                    return {"name": "Sovereign Sharp (Legacy)", "rules": f.read(), "tokens": {}}
            return {"error": "Design system source (DESIGN.md) not found."}
            
        with open(cls.DESIGN_FILE, 'r') as f:
            content = f.read()

        # Parse YAML front matter
        tokens = {}
        rules_text = content
        if content.startswith('---'):
            try:
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    tokens = yaml.safe_load(parts[1])
                    rules_text = parts[2].strip()
            except Exception as e:
                print(f"Error parsing DESIGN.md YAML: {e}")

        return {
            "name": tokens.get("name", "Unknown System"),
            "tokens": tokens,
            "rules": rules_text,
            "constraints": cls.extract_constraints(tokens)
        }

    @classmethod
    def extract_constraints(cls, tokens):
        """Extracts machine-readable constraints from tokens."""
        constraints = {
            "no_go": [],
            "mandates": []
        }
        
        # Colors
        colors = tokens.get("colors", {})
        if colors:
            constraints["mandates"].append(f"Colors: {', '.join(colors.keys())}")
            
        # Radii
        rounded = tokens.get("rounded", {})
        if rounded:
            constraints["mandates"].append(f"Radii: {', '.join([f'{k}:{v}' for k,v in rounded.items()])}")
        else:
            constraints["no_go"].append("rounded corners")

        return constraints

    @classmethod
    def get_prompt_segment(cls):
        data = cls.get_rules()
        if "error" in data:
            return f"DESIGN ERROR: {data['error']}"
            
        tokens_json = json.dumps(data['tokens'], indent=2)
        return f"""
### 🏛️ DESIGN GOVERNANCE: {data['name'].upper()}
Source: {cls.DESIGN_FILE}

TOKENS (Source of Truth):
{tokens_json}

PRINCIPLES:
{data['rules'][:500]}... (truncated)

CRITICAL DIRECTIVE:
You MUST adhere to the tokens above. If a token specifies a color or radius, DO NOT override it with hardcoded values.
"""

if __name__ == "__main__":
    oracle = DesignOracle()
    print(json.dumps(oracle.get_rules(), indent=2))
