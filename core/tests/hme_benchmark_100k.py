import json
import random
import time
from tools.strategy.hme_router import hme_router

# MASSIVE LIBRARIES FOR 100K GENERATION
ACTIONS = ["Fix", "Update", "Harden", "Secure", "Refactor", "Optimize", "Build", "Redesign", "Audit", "Debug", "Implement", "Patch", "Scale", "Deploy"]
UI_ELEMENTS = ["button", "header", "sidebar", "footer", "modal", "hero", "carousel", "nav", "card", "form", "toast", "tooltip", "dropdown", "grid", "skeleton"]
UI_STYLING = ["color", "padding", "margin", "z-index", "hover", "tailwind", "responsive", "backdrop", "typography", "animation", "shadow", "border", "flex", "grid"]
SEC_TARGETS = ["auth", "JWT", "API keys", "secrets", "session", "CSRF", "encryption", "password", "token", "firewall", "headers", "vault", "roles"]
DB_TARGETS = ["schema", "index", "table", "database", "RLS", "pgvector", "migration", "query", "cache", "partition", "sync", "backup", "replication"]
CORE_TARGETS = ["orchestrator", "parallel", "topology", "bayesian", "server", "pipeline", "autonomic", "governor", "sentinel", "monitor", "daemon"]

def generate_100k_dataset():
    dataset = []
    print("🧬 Synthesizing 100,000 tasks across the Sovereign Deep...")
    for _ in range(100000):
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
            
        else: # Mix
            task = f"{random.choice(ACTIONS)} {random.choice(UI_ELEMENTS)} and audit {random.choice(SEC_TARGETS)}"
            expected = "PRO_AUDITOR"
            
        dataset.append({"task": task, "expected": expected})
    return dataset

def run_100k_benchmark():
    data = generate_100k_dataset()
    print(f"📊 Starting 100,000 Case 'Deep Pressure' Stress Test...")
    print("-" * 60)
    
    correct = 0
    start_time = time.time()
    
    route_to_key = {
        "gemini-3-pro": "PRO_AUDITOR",
        "local-ollama": "LOCAL_WORKER",
        "gemini-3-flash": "FLASH_CODER",
        "claude-code": "SECURITY_GUARD"
    }
    
    for i, test in enumerate(data):
        task = test["task"]
        expected = test["expected"]
        
        route = hme_router.route_task(task)
        actual = route_to_key[route["worker"]]
        
        if actual == expected:
            correct += 1
            
        if i % 20000 == 0 and i > 0:
            print(f"   [PROGRESS] {i}/100000 processed... Accuracy: {(correct/i)*100:.2f}%")

    duration = time.time() - start_time
    accuracy = (correct / len(data)) * 100
    
    print("-" * 60)
    print(f"📈 100K BENCHMARK COMPLETE (SOVEREIGN SCALE)")
    print(f"   Accuracy:    {accuracy:.2f}%")
    print(f"   Total Time:  {duration*1000:.2f}ms")
    print(f"   Avg Latency: {duration*1000/len(data):.4f}ms")
    print("-" * 60)

if __name__ == "__main__":
    run_100k_benchmark()
