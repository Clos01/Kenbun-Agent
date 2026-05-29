import re
from typing import Dict, Any, List, Tuple
from tools.strategy.strategy_manager import governor

class HMERouter:
    """
    Hierarchical Mixture of Experts (HME) Sovereign Router.
    """
    
    def __init__(self):
        self.routes = {
            "PRO_AUDITOR": {"worker": "gemini-3-pro", "sandbox": "high_security", "priority": 1},
            "LOCAL_WORKER": {"worker": "local-ollama", "sandbox": "standard", "priority": 3},
            "FLASH_CODER": {"worker": "gemini-3-flash", "sandbox": "standard", "priority": 2},
            "SECURITY_GUARD": {"worker": "claude-code", "sandbox": "jails", "priority": 1}
        }
        
        # Sovereign Pattern Matrix Libraries (Pre-compiled with strict boundaries)
        ui_words = ["button", "header", "sidebar", "footer", "modal", "hero", "carousel", "nav", "card", "form", "toast", "tooltip", "dropdown", "grid", "skeleton", "color", "padding", "margin", "z-index", "hover", "tailwind", "responsive", "backdrop", "typography", "animation", "shadow", "border", "flex", "css", "react", "component", "ui", "ux", "design", "tw", "tsx", "jsx", "html", "style", "mobile", "sx", "font", "theme", "dark", "light", "glass"]
        
        sec_words = ["auth", "jwt", "api keys", "secrets", "session", "csrf", "encryption", "password", "token", "firewall", "headers", "vault", "roles", "login", "encrypt", "secret", "pass", "protect", "hardening", "audit", "verify", "sign", "acl", "sec", "guard", "jail", "permission", "policy", "security", "layers"]
        
        db_words = ["schema", "index", "table", "database", "rls", "pgvector", "migration", "query", "cache", "partition", "sync", "backup", "replication", "sql", "db", "supabase", "prisma", "mig", "postgres", "crud", "replica", "store", "data", "structure", "embedding", "vector", "structures"]
        
        infra_words = ["orchestrator", "parallel", "topology", "bayesian", "server", "pipeline", "autonomic", "governor", "sentinel", "monitor", "daemon", "core", "api", "infrastructure", "swarm", "workflow", "system", "sys", "node", "env", "ci", "cd", "devops", "corrector", "recovery", "logic", "scale", "optimize"]

        # Compile strict boundary regexes
        self.ui_p = re.compile(r"\b(" + "|".join(re.escape(w) for w in ui_words) + r")\b")
        self.sec_p = re.compile(r"\b(" + "|".join(re.escape(w) for w in sec_words) + r")\b")
        self.db_p = re.compile(r"\b(" + "|".join(re.escape(w) for w in db_words) + r")\b")
        self.infra_p = re.compile(r"\b(" + "|".join(re.escape(w) for w in infra_words) + r")\b")

    def _evaluate_pattern_matrix(self, task: str) -> Dict[str, Any]:
        """Sovereign Pattern Matrix: Evaluates structural archetypes."""
        t = task.lower()
        
        # Exact Boundary Tokenization
        has_ui = bool(self.ui_p.search(t))
        has_sec = bool(self.sec_p.search(t))
        has_db = bool(self.db_p.search(t))
        has_infra = bool(self.infra_p.search(t))
        
        # 1. The 'Collision' Archetype (Mix)
        if has_ui and (has_sec or has_db or has_infra):
            return self.routes["PRO_AUDITOR"]
            
        # 2. The 'Infrastructure/Data' Archetype
        if has_infra or has_db:
            return self.routes["PRO_AUDITOR"]
            
        # 3. The 'Pure Security' Archetype
        if has_sec:
            return self.routes["SECURITY_GUARD"]
            
        # 4. The 'Pure UI' Archetype
        if has_ui:
            if len(task) > 150:
                return self.routes["FLASH_CODER"]
            return self.routes["LOCAL_WORKER"]
            
        # Fallback Archetype
        if len(task) > 100:
            return self.routes["FLASH_CODER"]
        return self.routes["LOCAL_WORKER"]

    def _estimate_volume(self, task: str) -> float:
        t = task.lower()
        score = 0.0
        keywords = ["refactor", "massive", "entire", "migration", "orchestrate", "across", "files", "rewrite"]
        for k in keywords:
            if k in t:
                score += 0.25
        if len(task) > 150:
            score += 0.3
        elif len(task) > 100:
            score += 0.15
        return min(1.0, score)

    def route_task(self, task: str) -> Dict[str, Any]:
        proposal = self._evaluate_pattern_matrix(task)
        
        # Bayesian Confidence Check
        conf = governor.get_tool_confidence(proposal["worker"])
        if conf < 0.3:
            if proposal["worker"] == "local-ollama":
                proposal = self.routes["FLASH_CODER"]
            else:
                proposal = self.routes["PRO_AUDITOR"]

        # Integrity Flag
        vol = self._estimate_volume(task)
        proposal["integrity_flag"] = "CHUNKING_REQUIRED" if vol > 0.7 else "ATOMIC"
        
        return proposal

# Singleton
hme_router = HMERouter()
