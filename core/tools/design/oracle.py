import json
import yaml

class DesignOracle:
    """
    The Design Oracle retrieves architectural and visual rules 
    from the Sovereign Design library (DESIGN.md).
    """
    
    from tools.infrastructure.config import settings

    # Ordered candidates for the tokenised design source, most specific first.
    #
    # PROJECT_ROOT is the repo root (/app in the portable container), and there
    # is no DESIGN.md there -- the tokenised system lives in dashboard/. The old
    # single hardcoded PROJECT_ROOT/"DESIGN.md" therefore never resolved in any
    # deployment, which silently emptied get_design_tokens() and disabled
    # DesignGuardrail. core/DESIGN.md is kept as a fallback but carries no YAML
    # front matter, so it yields prose rules with no tokens.
    DESIGN_CANDIDATES = ("dashboard/DESIGN.md", "DESIGN.md", "core/DESIGN.md")

    # Set by get_rules() once a source resolves; referenced by get_prompt_segment().
    DESIGN_FILE = None

    @classmethod
    def resolve_design_file(cls):
        """First existing candidate, preferring one that actually has tokens."""
        found = [
            p for p in (cls.settings.PROJECT_ROOT / rel for rel in cls.DESIGN_CANDIDATES)
            if p.exists()
        ]
        for path in found:
            try:
                if path.read_text().lstrip().startswith("---"):
                    return path
            except OSError:
                continue
        return found[0] if found else None

    @classmethod
    def get_rules(cls):
        design_file = cls.resolve_design_file()
        if design_file is None:
            # Loud and specific: a missing design source silently disables the
            # guardrail and strips tokens out of every design prompt, so say
            # exactly where we looked instead of returning an empty dict.
            searched = ", ".join(
                str(cls.settings.PROJECT_ROOT / rel) for rel in cls.DESIGN_CANDIDATES
            )
            return {"error": f"Design system source (DESIGN.md) not found. Searched: {searched}"}

        cls.DESIGN_FILE = design_file
        with open(design_file, 'r') as f:
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
