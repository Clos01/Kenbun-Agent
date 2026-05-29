import json
import random
import time
from tools.strategy.hme_router import hme_router

# KEYWORD LIBRARIES FOR SYNTHETIC GENERATION
ACTIONS = ["Fix", "Update", "Harden", "Secure", "Refactor", "Optimize", "Build", "Redesign", "Audit", "Debug", "Implement"]
UI_ELEMENTS = ["button", "header", "sidebar", "footer", "modal", "hero section", "carousel", "navigation menu", "card layout", "input form"]
UI_STYLING = ["background color", "padding", "margin", "z-index", "hover effect", "tailwind classes", "mobile responsiveness", "glassy backdrop", "typography"]
SEC_TARGETS = ["authentication middleware", "JWT verification", "API keys", "secrets", "session logic", "CSRF protection", "encryption layer", "password hashing"]
DB_TARGETS = ["supabase schema", "SQL index", "transactions table", "postgres database", "RLS policies", "pgvector extension", "migration script"]
CORE_TARGETS = ["orchestrator.py", "parallel_manager.py", "topology_manager.py", "bayesian_governor", "api_server", "swarm pipeline"]

def generate_1k_dataset():
    dataset = []
    
    for _ in range(1000):
        category = random.choice(["ui", "security", "db", "infra", "mix"])
        
        if category == "ui":
            task = f"{random.choice(ACTIONS)} the {random.choice(UI_STYLING)} of the {random.choice(UI_ELEMENTS)}"
            expected = "LOCAL_WORKER"
            if len(task) > 150 or "complex" in task: expected = "FLASH_CODER"
        
        elif category == "security":
            task = f"{random.choice(ACTIONS)} the {random.choice(SEC_TARGETS)} to prevent leaks"
            expected = "SECURITY_GUARD"
        
        elif category == "db":
            task = f"{random.choice(ACTIONS)} the {random.choice(DB_TARGETS)} for the production environment"
            expected = "PRO_AUDITOR"
            
        elif category == "infra":
            task = f"{random.choice(ACTIONS)} the {random.choice(CORE_TARGETS)} to improve reliability"
            expected = "PRO_AUDITOR"
            
        else: # Mix
            task = f"{random.choice(ACTIONS)} the {random.choice(UI_ELEMENTS)} and verify the {random.choice(SEC_TARGETS)}"
            expected = "PRO_AUDITOR" # Complex mix needs Pro
            
        dataset.append({"task": task, "expected": expected})
        
    return dataset

def run_1k_benchmark():
    data = generate_1k_dataset()
    print(f"📊 Starting 1,000 Case 'Deep Stress' Benchmark...")
    print("-" * 60)
    
    correct = 0
    start_time = time.time()
    
    route_to_key = {
        "gemini-3-pro": "PRO_AUDITOR",
        "local-ollama": "LOCAL_WORKER",
        "gemini-3-flash": "FLASH_CODER",
        "claude-code": "SECURITY_GUARD"
    }
    
    pivots = 0
    
    for i, test in enumerate(data):
        task = test["task"]
        expected = test["expected"]
        
        # We wrap the call to capture stdout (pivots)
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            route = hme_router.route_task(task)
        
        if "Pivoting" in f.getvalue():
            pivots += 1
            
        actual = route_to_key[route["worker"]]
        
        if actual == expected:
            correct += 1
            
        if i % 100 == 0 and i > 0:
            print(f"   [PROGRESS] {i}/1000 processed... Current Accuracy: {(correct/i)*100:.1f}%")

    duration = time.time() - start_time
    accuracy = (correct / len(data)) * 100
    
    print("-" * 60)
    print(f"📈 1K BENCHMARK COMPLETE")
    print(f"   Total Tasks: {len(data)}")
    print(f"   Accuracy:    {accuracy:.2f}%")
    print(f"   Bayesian Pivots: {pivots}")
    print(f"   Total Latency:   {duration*1000:.2f}ms")
    print(f"   Avg Latency:     {duration*1000/len(data):.4f}ms")
    print("-" * 60)

if __name__ == "__main__":
    run_1k_benchmark()
