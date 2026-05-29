import re
from typing import List, Dict, Any

class KeywordProcessor:
    """
    Handles keyword definitions and regex matching for System 4b.
    """
    def __init__(self, keywords: Dict[str, List[str]] = None):
        self.keywords = keywords or {
            "ui": ["css", "layout", "style", "tailwind", "flexbox", "grid", "component", "button", "center", "form", "validation", "zod", "input", "ui", "aesthetic", "brutalist", "glassmorphic", "animation", "gsap"],
            "security": ["sql", "injection", "auth", "jwt", "password", "data leak", "bypass", "permission", "cors", "vulnerability", "rate-limit", "brute-force", "ddos", "xss", "sanitization", "secure", "hardening", "encrypt", "breach", "leak", "harden"],
            "performance": ["slow", "lag", "optimize", "cache", "memory leak", "memory", "bottleneck", "fps", "glsl", "perf", "revalidation"],
            "bug": ["error", "fail", "crash", "bug", "broken", "broke", "regression", "not working", "fix", "issue", "resolve"],
            "architecture": ["architect", "design", "strategy", "research", "migrate", "transition", "pros and cons", "scalable", "infrastructure", "refactor"],
            "deep_code": ["implement", "build feature", "generate tests", "write module", "create module", "full implementation", "multi-file", "overhaul", "rewrite", "scaffold", "build out", "wire up"],
            "noise": ["story", "joke", "tell me", "dragon", "pizza", "movie", "game", "chat", "random"]
        }

    def match_categories(self, text: str) -> Dict[str, List[str]]:
        if not text:
            return {cat: [] for cat in self.keywords}
            
        text_lower = text.lower()
        matched = {cat: [] for cat in self.keywords}
        
        for category, kws in self.keywords.items():
            for k in kws:
                try:
                    # Security keywords use fuzzy matching (no word boundary)
                    if category == "security":
                        if k in text_lower:
                            matched[category].append(k)
                    else:
                        if re.search(rf"\b{re.escape(k)}\b", text_lower):
                            matched[category].append(k)
                except re.error:
                    continue
        return matched
