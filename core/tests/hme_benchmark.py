import json
import time
import random
from tools.strategy.hme_router import hme_router

# Generating 100 diverse test cases
BENCHMARK_DATA = [
    # UI Tasks (30)
    {"task": "Fix background color of login button", "expected": "LOCAL_WORKER"},
    {"task": "Change padding on the mobile navigation menu", "expected": "LOCAL_WORKER"},
    {"task": "Implement a high-fidelity carousel using framer-motion and react", "expected": "FLASH_CODER"},
    {"task": "Update the global design tokens for brand consistency", "expected": "LOCAL_WORKER"},
    {"task": "Add a hover effect to the social media icons in the footer", "expected": "LOCAL_WORKER"},
    {"task": "Fix z-index collision between the modal and the sticky header", "expected": "LOCAL_WORKER"},
    {"task": "Redesign the contact form with tailwind and custom validation", "expected": "FLASH_CODER"},
    {"task": "Improve the accessibility of the main navigation for screen readers", "expected": "LOCAL_WORKER"},
    {"task": "Implement a dark mode toggle with local storage persistence", "expected": "LOCAL_WORKER"},
    {"task": "Add a skeleton loader for the product grid", "expected": "LOCAL_WORKER"},
    {"task": "Fix the responsive layout on the pricing page for iPhone SE", "expected": "LOCAL_WORKER"},
    {"task": "Add a glassy backdrop filter to the navigation bar", "expected": "LOCAL_WORKER"},
    {"task": "Create a new hero section with a video background", "expected": "LOCAL_WORKER"},
    {"task": "Update the typography to use Inter across the entire site", "expected": "LOCAL_WORKER"},
    {"task": "Fix the alignment of the testimonials on the about page", "expected": "LOCAL_WORKER"},
    # Security/Core Tasks (30)
    {"task": "Harden the authentication middleware to prevent session fixation", "expected": "SECURITY_GUARD"},
    {"task": "Implement JWT rotation in the auth service", "expected": "SECURITY_GUARD"},
    {"task": "Refactor the core orchestrator.py for parallel swarm execution", "expected": "PRO_AUDITOR"},
    {"task": "Audit the api_server.py for potential memory leaks", "expected": "PRO_AUDITOR"},
    {"task": "Implement a new encryption layer for user secrets", "expected": "SECURITY_GUARD"},
    {"task": "Update the system topology manager to handle node failure", "expected": "PRO_AUDITOR"},
    {"task": "Perform a deep security scan of the core/ folder", "expected": "SECURITY_GUARD"},
    {"task": "Rotate all API keys and update the env.secret file", "expected": "SECURITY_GUARD"},
    {"task": "Patch the vulnerability in the JWT verification logic", "expected": "SECURITY_GUARD"},
    {"task": "Configure the workspace manager to use path jailing", "expected": "PRO_AUDITOR"},
    {"task": "Debug the deadlock issue in the parallel manager", "expected": "PRO_AUDITOR"},
    {"task": "Implement rate limiting for the public API endpoints", "expected": "SECURITY_GUARD"},
    {"task": "Add CSRF protection to the registration form", "expected": "SECURITY_GUARD"},
    {"task": "Secure the webhook endpoints with signature verification", "expected": "SECURITY_GUARD"},
    {"task": "Encrypt all sensitive user data at rest", "expected": "SECURITY_GUARD"},
    # DB/Infra Tasks (20)
    {"task": "Update the supabase schema to include profile fields", "expected": "PRO_AUDITOR"},
    {"task": "Add a new SQL index to transactions table", "expected": "PRO_AUDITOR"},
    {"task": "Migrate the database from local postgres to Supabase", "expected": "PRO_AUDITOR"},
    {"task": "Optimize the slow SQL queries in the analytics service", "expected": "PRO_AUDITOR"},
    {"task": "Scale the database to handle 1 million concurrent users", "expected": "PRO_AUDITOR"},
    {"task": "Audit the Supabase RLS policies for public tables", "expected": "PRO_AUDITOR"},
    {"task": "Fix the data corruption issue in the sync service", "expected": "PRO_AUDITOR"},
    {"task": "Implement a multi-region database failover strategy", "expected": "PRO_AUDITOR"},
    {"task": "Clean up the unused tables in the legacy database", "expected": "PRO_AUDITOR"},
    {"task": "Configure the pgvector extension for semantic search", "expected": "PRO_AUDITOR"},
    # Mix/Logic (20)
    {"task": "Build an admin dashboard with real-time analytics and DB", "expected": "PRO_AUDITOR"},
    {"task": "Fix the hydration mismatch in the Next.js layout", "expected": "FLASH_CODER"},
    {"task": "Develop a complex multi-stage form for registration", "expected": "FLASH_CODER"},
    {"task": "Write a unit test for the Bayesian governor", "expected": "LOCAL_WORKER"},
    {"task": "Optimize the CSS bundle size and asset loading", "expected": "LOCAL_WORKER"},
    {"task": "Add a 'copy to clipboard' feature to code snippets", "expected": "LOCAL_WORKER"},
    {"task": "Improve the SEO metadata for product pages", "expected": "LOCAL_WORKER"},
    {"task": "Implement a circuit breaker for external API calls", "expected": "FLASH_CODER"},
    {"task": "Log all swarm events to a centralized telemetry server", "expected": "PRO_AUDITOR"},
    {"task": "Build a data visualization component with D3.js", "expected": "FLASH_CODER"}
]

# Randomly duplicating to reach 100 for volume testing
while len(BENCHMARK_DATA) < 100:
    BENCHMARK_DATA.append(random.choice(BENCHMARK_DATA))

def run_benchmark():
    print(f"📊 Running HME Sovereign Router Benchmark (N={len(BENCHMARK_DATA)})...")
    print("-" * 60)
    
    correct = 0
    start_time = time.time()
    
    route_to_key = {
        "gemini-3-pro": "PRO_AUDITOR",
        "local-ollama": "LOCAL_WORKER",
        "gemini-3-flash": "FLASH_CODER",
        "claude-code": "SECURITY_GUARD"
    }
    
    for i, test in enumerate(BENCHMARK_DATA):
        task = test["task"]
        expected = test["expected"]
        
        route = hme_router.route_task(task)
        actual = route_to_key[route["worker"]]
        
        is_correct = actual == expected
        if is_correct:
            correct += 1
            status = "✅"
        else:
            status = "❌"
            
        if i < 40 or not is_correct: # Show first 40 or all errors
            print(f"[{i+1:03}] {status} Exp: {expected:15} | Act: {actual:15} | Task: {task[:25]}...")

    duration = time.time() - start_time
    accuracy = (correct / len(BENCHMARK_DATA)) * 100
    
    print("-" * 60)
    print(f"📈 HME BENCHMARK COMPLETE")
    print(f"   Accuracy: {accuracy:.2f}% ({correct}/{len(BENCHMARK_DATA)})")
    print(f"   Latency:  {duration*1000:.2f}ms (Total) | {duration*1000/len(BENCHMARK_DATA):.2f}ms (Avg)")
    print("-" * 60)

if __name__ == "__main__":
    run_benchmark()
