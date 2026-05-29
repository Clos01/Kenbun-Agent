import re
import sys
import json
from tools.design.oracle import DesignOracle

class DesignGuardrail:
    """
    Automated validator to prevent 'Technical Debt' in design.
    Dynamically generates rules from the active DESIGN.md tokens.
    """
    
    @classmethod
    def get_dynamic_patterns(cls):
        rules = DesignOracle.get_rules()
        if "error" in rules:
            return []

        tokens = rules.get("tokens", {})
        patterns = []

        # 1. Radii Validation
        allowed_radii = set(list(tokens.get("rounded", {}).keys()) + ["none"])
        patterns.append((
            r'rounded-([a-z0-9-]+)',
            lambda m: f"Invalid radius token '{m.group(1)}'. Allowed for {rules['name']}: {', '.join(allowed_radii)}" if m.group(1) not in allowed_radii else None
        ))

        # 2. Color Validation (Soft warnings for non-token colors)
        # This is harder because of Tailwind defaults, but we can flag legacy Sovereign/Obsidian colors.
        legacy_colors = ["blue", "purple", "indigo", "sky", "cyan", "violet"]
        patterns.append((
            fr'(bg|text|border|fill|stroke)-(?:{"|".join(legacy_colors)})',
            "Legacy color detected. Please use tokens (primary, secondary, tertiary, neutral)."
        ))

        # 3. Hardcoded values (Inline styles)
        patterns.append((
            r'style=\{\{\s*borderRadius:\s*[\'"](?!0|4px|8px)[\'"]',
            "Hardcoded border-radius detected. Use tokenized classes."
        ))

        return patterns

    @classmethod
    def validate_content(cls, content, filename="unknown"):
        violations = []
        patterns = cls.get_dynamic_patterns()
        
        for pattern, message_logic in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                if callable(message_logic):
                    error_msg = message_logic(match)
                    if not error_msg:
                        continue
                else:
                    error_msg = message_logic
                    
                violations.append({
                    "file": filename,
                    "line": content.count('\n', 0, match.start()) + 1,
                    "match": match.group(0),
                    "error": error_msg
                })
    @classmethod
    def validate(cls, code_snippet: str) -> dict:
        violations = cls.validate_content(code_snippet)
        if violations:
            reason = "; ".join([f"Line {v['line']}: {v['error']} (found '{v['match']}')" for v in violations])
            return {"status": "REJECTED", "reason": reason}
        return {"status": "APPROVED", "reason": "Passed design compliance."}

if __name__ == "__main__":
    all_violations = []
    for arg in sys.argv[1:]:
        try:
            with open(arg, 'r') as f:
                v = DesignGuardrail.validate_content(f.read(), arg)
                all_violations.extend(v)
        except Exception as e:
            print(f"Error reading {arg}: {e}")
            
    if all_violations:
        print(json.dumps(all_violations, indent=2))
        sys.exit(1)
    else:
        print(f"PASSED: Content complies with {DesignOracle.get_rules()['name']} mandate.")
        sys.exit(0)
