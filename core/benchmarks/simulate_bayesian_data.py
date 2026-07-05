import os
import sys
import random
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "core"))

from tools.utils.bayesian import tune_swarm

# The 33 tools we want to train
CORE_TOOLS = [
    "scan_repo", "recall_fix", "autofix_linter", "index_codebase",
    "delete_from_hivemind", "get_brain_health", "audit_package_safety",
    "save_to_hivemind", "search_hivemind_concepts", "search_codebase",
    "think_about_tools", "patch_hivemind_concept", "ingest_knowledge_from_pdf",
    "prune_hivemind", "get_intelligence_stats", "reflect_on_task",
    "save_checkpoint", "consult_supervisor", "audit_guardrail",
    "research_official_docs", "ask_architect", "ask_ui_expert",
    "get_design_tokens", "review_code_with_gemini", "research_with_gemini",
    "run_code_safely", "restore_checkpoint", "list_checkpoints",
    "orchestrate", "remember_fix", "token_governor", "telemetry_pulse",
    "bayesian_governor"
]

# Provide realistic simulated win-rates to give the system logical stats
# Easy/Reliable tasks get 90-98% success rates
# Complex/Brittle tasks get 75-85% success rates
WIN_RATES = {
    "get_brain_health": 0.99,
    "list_checkpoints": 0.99,
    "scan_repo": 0.95,
    "search_codebase": 0.90,
    "consult_supervisor": 0.92,
    "run_code_safely": 0.78, # often fails on weird code
    "autofix_linter": 0.82,
    "review_code_with_gemini": 0.88,
    "research_with_gemini": 0.85,
    "orchestrate": 0.94,
    "bayesian_governor": 0.98,
    "telemetry_pulse": 0.99,
}

def get_win_rate(tool):
    return WIN_RATES.get(tool, 0.89) # Default 89% win rate for unmapped

def simulate_data(iterations=500):
    print(f"🚀 Starting Bayesian Data Simulation ({iterations} loops per tool)...")
    print("-" * 50)
    
    total_injected = 0
    for tool in CORE_TOOLS:
        win_rate = get_win_rate(tool)
        successes = 0
        failures = 0
        
        for _ in range(iterations):
            is_success = random.random() <= win_rate
            
            # The bayesian governor function takes (tool_id, success, category)
            # We'll use "global" category so they show up easily
            tune_swarm(tool, is_success, "global")
            
            if is_success:
                successes += 1
            else:
                failures += 1
                
        total_injected += iterations
        print(f"✅ Injected 500 runs for '{tool}' (Successes: {successes}, Failures: {failures})")

    print("-" * 50)
    print(f"🎉 Simulation Complete! Injected {total_injected} total statistical data points.")
    print("Check the Telemetry Dashboard or weights.json!")

if __name__ == "__main__":
    simulate_data(500)
