import json
import random
import time
from tools.strategy.hme_router import hme_router

# RE-USING THE SAME GENERATOR LOGIC
ACTIONS = ["Fix", "Update", "Harden", "Secure", "Refactor", "Optimize", "Build", "Redesign", "Audit", "Debug", "Implement", "Patch", "Scale", "Deploy"]
UI_ELEMENTS = ["button", "header", "sidebar", "footer", "modal", "hero", "carousel", "nav", "card", "form", "toast", "tooltip", "dropdown", "grid", "skeleton"]
UI_STYLING = ["color", "padding", "margin", "z-index", "hover", "tailwind", "responsive", "backdrop", "typography", "animation", "shadow", "border", "flex", "grid"]
SEC_TARGETS = ["auth", "JWT", "API keys", "secrets", "session", "CSRF", "encryption", "password", "token", "firewall", "headers", "vault", "roles"]
DB_TARGETS = ["schema", "index", "table", "database", "RLS", "pgvector", "migration", "query", "cache", "partition", "sync", "backup", "replication"]
CORE_TARGETS = ["orchestrator", "parallel", "topology", "bayesian", "server", "pipeline", "autonomic", "governor", "sentinel", "monitor", "daemon"]

def audit_failures():
    print("🔍 Auditing Top 10 Failures in HME Logic...")
    
    route_to_key = {
        "gemini-3-pro": "PRO_AUDITOR",
        "local-ollama": "LOCAL_WORKER",
        "gemini-3-flash": "FLASH_CODER",
        "claude-code": "SECURITY_GUARD"
    }
    
    failures = 0
    limit = 10
    
    for _ in range(20000):
        category = random.choice(["ui", "security", "db", "infra", "mix"])
        if category == "ui":
            task = f"{random.choice(ACTIONS)} {random.choice(UI_STYLING)} for the {random.choice(UI_ELEMENTS)}"
            expected = "LOCAL_WORKER"
            if len(task) > 150: expected = "FLASH_CODER"
        elif category == "security":
            task = f"{random.choice(ACTIONS)} the {random.choice(SEC_TARGETS)} layers"
            expected = "SECURITY_GUARD"
        elif category == "db":
            task = f"{random.choice(ACTIONS)} {random.choice(DB_TARGETS)} structures"
            expected = "PRO_AUDITOR"
        elif category == "infra":
            task = f"{random.choice(ACTIONS)} the {random.choice(CORE_TARGETS)} logic"
            expected = "PRO_AUDITOR"
        else:
            task = f"{random.choice(ACTIONS)} {random.choice(UI_ELEMENTS)} and audit {random.choice(SEC_TARGETS)}"
            expected = "PRO_AUDITOR"

        route = hme_router.route_task(task)
        actual = route_to_key[route["worker"]]
        
        if actual != expected and failures < limit:
            print(f"❌ FAIL: Task: '{task}'")
            print(f"   Expected: {expected} | Actual: {actual}")
            # Debug weights
            w = hme_router._evaluate_pattern_matrix(task)
            print(f"   Pattern: {w}")
            failures += 1
        
        if failures >= limit:
            break

if __name__ == "__main__":
    audit_failures()
