import json
import random
import time
from tools.strategy.hme_router import hme_router

# KEYWORD LIBRARIES FOR 5K SYNTHETIC GENERATION
ACTIONS = ["Fix", "Update", "Harden", "Secure", "Refactor", "Optimize", "Build", "Redesign", "Audit", "Debug", "Implement"]
UI_ELEMENTS = ["button", "header", "sidebar", "footer", "modal", "hero section", "carousel", "navigation menu", "card layout", "input form"]
UI_STYLING = ["background color", "padding", "margin", "z-index", "hover effect", "tailwind classes", "mobile responsiveness", "glassy backdrop", "typography"]
SEC_TARGETS = ["authentication middleware", "JWT verification", "API keys", "secrets", "session logic", "CSRF protection", "encryption layer", "password hashing"]
DB_TARGETS = ["supabase schema", "SQL index", "transactions table", "postgres database", "RLS policies", "pgvector extension", "migration script"]
CORE_TARGETS = ["orchestrator.py", "parallel_manager.py", "topology_manager.py", "bayesian_governor", "api_server", "swarm pipeline"]

def generate_5k_dataset():
    dataset = []
    print("🧬 Synthesizing 5,000 tasks...")
    for _ in range(5000):
        category = random.choice(["ui", "security", "db", "infra", "mix"])
        
        if category == "ui":
            task = f"{random.choice(ACTIONS)} the {random.choice(UI_STYLING)} of the {random.choice(UI_ELEMENTS)}"
            expected = "LOCAL_WORKER"
            if len(task) > 150: expected = "FLASH_CODER"
        
        elif category == "security":
            task = f"{random.choice(ACTIONS)} the {random.choice(SEC_TARGETS)} to prevent leaks"
            expected = "SECURITY_GUARD"
        
        elif category == "db":
            task = f"{random.choice(ACTIONS)} the {random.choice(DB_TARGETS)} for production"
            expected = "PRO_AUDITOR"
            
        elif category == "infra":
            task = f"{random.choice(ACTIONS)} the {random.choice(CORE_TARGETS)}"
            expected = "PRO_AUDITOR"
            
        else: # Mix (Complexity)
            task = f"{random.choice(ACTIONS)} the {random.choice(UI_ELEMENTS)} and verify the {random.choice(SEC_TARGETS)}"
            expected = "PRO_AUDITOR"
            
        dataset.append({"task": task, "expected": expected})
    return dataset

def run_5k_benchmark():
    data = generate_5k_dataset()
    print(f"📊 Starting 5,000 Case 'Deep Void' Stress Test (Boosting Layer Active)...")
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
            
        if i % 1000 == 0 and i > 0:
            print(f"   [PROGRESS] {i}/5000 processed... Accuracy: {(correct/i)*100:.2f}%")

    duration = time.time() - start_time
    accuracy = (correct / len(data)) * 100
    
    print("-" * 60)
    print(f"📈 5K BENCHMARK COMPLETE (BOOSTING ENABLED)")
    print(f"   Accuracy:    {accuracy:.2f}%")
    print(f"   Total Time:  {duration*1000:.2f}ms")
    print(f"   Avg Latency: {duration*1000/len(data):.4f}ms")
    print("-" * 60)

if __name__ == "__main__":
    run_5k_benchmark()
