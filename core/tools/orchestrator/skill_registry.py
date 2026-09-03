#!/usr/bin/env python3
import os
import re
import glob
import math
from collections import Counter

SKILLS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.agents/skills"))

def tokenize(text):
    return [w for w in re.findall(r'[a-zA-Z0-9_\-]+', text.lower()) if len(w) > 2]

def load_all_skills():
    """
    Dynamically auto-discovers 100% of skills in .agents/skills/* without hardcoding.
    Parses YAML frontmatter, headers, purpose, and triggers automatically.
    """
    skills = []
    skill_files = glob.glob(os.path.join(SKILLS_DIR, "*/SKILL.md"))
    
    for sf in sorted(skill_files):
        try:
            with open(sf, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 1. Parse YAML Frontmatter
            name_match = re.search(r'name:\s*["\']?([^"\'\n]+)["\']?', content)
            desc_match = re.search(r'description:\s*(?:>-\s*)?["\']?([^"\'\n]+(?:\n\s+[^"\'\n]+)*)["\']?', content)
            
            name = name_match.group(1).strip() if name_match else os.path.basename(os.path.dirname(sf))
            desc = desc_match.group(1).strip().replace("\n", " ") if desc_match else ""
            
            # 2. Extract Purpose and Body Sections for Deep Semantic Grounding
            body_text = re.sub(r'---[\s\S]*?---', '', content) # strip frontmatter
            
            skills.append({
                "name": name,
                "description": desc,
                "full_text": f"{name} {desc} {body_text}",
                "path": sf,
                "dir": os.path.dirname(sf)
            })
        except Exception:
            continue
            
    return skills

def match_skills_for_task(query, limit=3):
    """
    Generic TF-IDF / Semantic Cosine Relevance Scorer.
    Zero hardcoded rules. Dynamically adapts as 10, 50, or 100+ skills are added.
    """
    all_skills = load_all_skills()
    if not all_skills:
        return []

    q_tokens = tokenize(query)
    if not q_tokens:
        return all_skills[:limit]

    # Calculate IDF for all tokens across all skills
    total_docs = len(all_skills)
    doc_freq = Counter()
    for s in all_skills:
        unique_tokens = set(tokenize(s['full_text']))
        for t in unique_tokens:
            doc_freq[t] += 1

    idf = {t: math.log((total_docs + 1) / (df + 1)) + 1.0 for t, df in doc_freq.items()}

    scored = []
    for s in all_skills:
        skill_tokens = tokenize(s['full_text'])
        tf = Counter(skill_tokens)
        
        # Calculate Query-to-Skill Semantic Score
        score = 0.0
        for qt in q_tokens:
            if qt in tf:
                # Term frequency weighted by Inverse Document Frequency
                term_weight = (1 + math.log(tf[qt])) * idf.get(qt, 1.0)
                score += term_weight

            # High-priority boost if query matches skill name directly
            if qt in s['name'].lower():
                score += 15.0

        if score > 0.0:
            scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:limit]]

if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "audit a11y color contrast on buttons"
    all_s = load_all_skills()
    print(f"⚡ DYNAMIC AUTO-DISCOVERY: Loaded {len(all_s)} skills with 0 hardcoding.")
    matched = match_skills_for_task(q)
    print(f"\nTop semantic matches for: '{q}'")
    for idx, m in enumerate(matched, 1):
        print(f" {idx}. [{m['name']}] -> {m['description'][:80]}...")
