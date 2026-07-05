import re
from pathlib import Path
import pytest

SKILLS_DIR = Path(__file__).resolve().parent.parent / "tools" / "skills"

def get_all_skills():
    """Locate the newly added skill directories containing SKILL.md."""
    new_skills = ["quick-recap", "read-the-damn-docs", "plow-ahead"]
    skills = []
    if not SKILLS_DIR.exists():
        return skills
    for p in SKILLS_DIR.iterdir():
        if p.is_dir() and p.name in new_skills and (p / "SKILL.md").exists():
            skills.append(p)
    return skills

def parse_yaml_frontmatter(content: str) -> dict:
    """Robust, dependency-free YAML-like frontmatter parser for basic metadata."""
    # Find text between first two ---
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
            
        # Check for indent (list item under a key or sub-key value)
        if line.startswith("-") or line.startswith("  "):
            # Simple list item parsing
            item = line.lstrip("- ").strip()
            if current_key and isinstance(data[current_key], list):
                data[current_key].append(item)
            continue
            
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            
            # Sub-key handling (e.g. kenbun:)
            if val == "":
                data[key] = {}
                current_key = key
            elif current_key and isinstance(data.get(current_key), dict):
                # Simple nested key-value under current_key (e.g., mode: document)
                # If value looks like a list bracket, parse as list
                if val.startswith("[") and val.endswith("]"):
                    items = [i.strip().strip("'\"") for i in val[1:-1].split(",") if i.strip()]
                    data[current_key][key] = items
                else:
                    # Boolean / Integer / String conversions
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

@pytest.mark.parametrize("skill_path", get_all_skills(), ids=lambda p: p.name)
def test_skill_protocol_compliance(skill_path):
    """Ensure SKILL.md has compliant frontmatter for Kenbun."""
    skill_file = skill_path / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")
    
    # Check that frontmatter block exists
    assert content.startswith("---"), f"{skill_path.name}/SKILL.md must start with --- frontmatter separator"
    
    metadata = parse_yaml_frontmatter(content)
    
    # Verify the 'kenbun' root namespace exists
    assert "kenbun" in metadata, f"{skill_path.name}/SKILL.md is missing the 'kenbun' frontmatter section"
    kenbun_meta = metadata["kenbun"]
    assert isinstance(kenbun_meta, dict), f"'kenbun' in {skill_path.name}/SKILL.md must be a dictionary block"
    
    # Validate mode
    assert "mode" in kenbun_meta, f"{skill_path.name}/SKILL.md must define 'mode' under kenbun"
    assert kenbun_meta["mode"] in ["prototype", "deck", "document"], \
        f"Invalid mode '{kenbun_meta['mode']}' in {skill_path.name}/SKILL.md. Must be prototype, deck, or document."
        
    # Validate fidelity
    assert "fidelity" in kenbun_meta, f"{skill_path.name}/SKILL.md must define 'fidelity' under kenbun"
    assert kenbun_meta["fidelity"] in ["high", "wireframe"], \
        f"Invalid fidelity '{kenbun_meta['fidelity']}' in {skill_path.name}/SKILL.md. Must be high or wireframe."
        
    # Validate tech_stack
    assert "tech_stack" in kenbun_meta, f"{skill_path.name}/SKILL.md must define 'tech_stack' under kenbun"
    assert isinstance(kenbun_meta["tech_stack"], list), f"'tech_stack' in {skill_path.name}/SKILL.md must be a list"
    
    # Validate discovery_required
    assert "discovery_required" in kenbun_meta, f"{skill_path.name}/SKILL.md must define 'discovery_required' under kenbun"
    assert isinstance(kenbun_meta["discovery_required"], bool), f"'discovery_required' in {skill_path.name}/SKILL.md must be a boolean"
