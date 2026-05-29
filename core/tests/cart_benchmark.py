import json
import time
from tools.strategy.cart_router import cart_router

# 35 Test Cases for the CART Benchmark
BENCHMARK_DATA = [
    {"task": "Fix the background color of the login button to be blue", "expected": "LOCAL_WORKER"},
    {"task": "Update the supabase schema to include a new profile field for users", "expected": "PRO_AUDITOR"},
    {"task": "Harden the authentication middleware to prevent session fixation", "expected": "SECURITY_GUARD"},
    {"task": "Refactor the core orchestrator.py to support parallel swarm execution", "expected": "SECURITY_GUARD"},
    {"task": "Create a new React component for the gallery preview with framer-motion", "expected": "LOCAL_WORKER"},
    {"task": "Add a new SQL index to the transactions table to speed up lookups", "expected": "PRO_AUDITOR"},
    {"task": "Implement JWT rotation in the auth service", "expected": "SECURITY_GUARD"},
    {"task": "Fix a typo in the footer of the landing page", "expected": "LOCAL_WORKER"},
    {"task": "Develop a complex multi-stage form for user registration with validation", "expected": "FLASH_CODER"},
    {"task": "Audit the api_server.py for potential memory leaks", "expected": "SECURITY_GUARD"},
    {"task": "Migrate the database from local postgres to Supabase", "expected": "PRO_AUDITOR"},
    {"task": "Add tailwind classes to the contact form for better mobile responsiveness", "expected": "LOCAL_WORKER"},
    {"task": "Implement a new encryption layer for user secrets", "expected": "SECURITY_GUARD"},
    {"task": "Update the system topology manager to handle node failure", "expected": "SECURITY_GUARD"},
    {"task": "Write a unit test for the Bayesian governor", "expected": "LOCAL_WORKER"},
    {"task": "Perform a deep security scan of the entire core/ folder", "expected": "SECURITY_GUARD"},
    {"task": "Optimize the CSS bundle size by removing unused styles", "expected": "LOCAL_WORKER"},
    {"task": "Build an admin dashboard with real-time analytics and DB integration", "expected": "PRO_AUDITOR"},
    {"task": "Fix the hydration mismatch in the Next.js layout", "expected": "FLASH_CODER"},
    {"task": "Rotate all API keys and update the .env.secret file", "expected": "SECURITY_GUARD"},
    {"task": "Add a hover effect to the navigation links", "expected": "LOCAL_WORKER"},
    {"task": "Implement a rate limiting middleware for the API", "expected": "SECURITY_GUARD"},
    {"task": "Scale the database to handle 1 million concurrent users", "expected": "PRO_AUDITOR"},
    {"task": "Fix the z-index overlap on the mobile sidebar", "expected": "LOCAL_WORKER"},
    {"task": "Analyze the log files for recurring 500 errors in the DB layer", "expected": "PRO_AUDITOR"},
    {"task": "Create a high-fidelity design system in TSX for the new portfolio", "expected": "FLASH_CODER"},
    {"task": "Patch the vulnerability in the JWT verification logic", "expected": "SECURITY_GUARD"},
    {"task": "Configure the workspace manager to use a new path jailing strategy", "expected": "SECURITY_GUARD"},
    {"task": "Add a 'copy to clipboard' feature to the code snippets", "expected": "LOCAL_WORKER"},
    {"task": "Debug the deadlock issue in the parallel manager", "expected": "SECURITY_GUARD"},
    {"task": "Improve the SEO metadata for the product pages", "expected": "LOCAL_WORKER"},
    {"task": "Build a complex data visualization component with D3.js and React", "expected": "FLASH_CODER"},
    {"task": "Audit the Supabase RLS policies for the public tables", "expected": "PRO_AUDITOR"},
    {"task": "Implement a circuit breaker for external API calls", "expected": "FLASH_CODER"},
    {"task": "Update the branding colors in the global design tokens", "expected": "LOCAL_WORKER"}
]

def run_benchmark():
    print(f"📊 Running CART Sovereign Router Benchmark (N={len(BENCHMARK_DATA)})...")
    print("-" * 60)
    
    correct = 0
    start_time = time.time()
    
    results = []
    
    # Mapping route response back to the key for comparison
    route_to_key = {
        "gemini-3-pro": "PRO_AUDITOR",
        "local-ollama": "LOCAL_WORKER",
        "gemini-3-flash": "FLASH_CODER",
        "claude-code": "SECURITY_GUARD"
    }
    
    for i, test in enumerate(BENCHMARK_DATA):
        task = test["task"]
        expected = test["expected"]
        
        route = cart_router.route_task(task)
        actual = route_to_key[route["worker"]]
        
        is_correct = actual == expected
        if is_correct:
            correct += 1
            status = "✅"
        else:
            status = "❌"
            
        results.append({
            "id": i + 1,
            "task": task[:40] + "...",
            "expected": expected,
            "actual": actual,
            "status": status
        })
        
        print(f"[{i+1:02}] {status} Expected: {expected:15} | Actual: {actual:15} | Task: {task[:30]}...")

    duration = time.time() - start_time
    accuracy = (correct / len(BENCHMARK_DATA)) * 100
    
    print("-" * 60)
    print(f"📈 BENCHMARK COMPLETE")
    print(f"   Accuracy: {accuracy:.2f}% ({correct}/{len(BENCHMARK_DATA)})")
    print(f"   Latency:  {duration*1000:.2f}ms (Total) | {duration*1000/len(BENCHMARK_DATA):.2f}ms (Avg)")
    print("-" * 60)

if __name__ == "__main__":
    run_benchmark()
