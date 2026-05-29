import os
import sys
import json
import time
import asyncio
from tools.infrastructure.config import settings

# --- 1. SETUP PATHS ---
PROJECT_ROOT = settings.PROJECT_ROOT

from tools.infrastructure.orchestrator import run_pipeline
from tools.strategy.token_governor import token_governor

# --- MOCK TOOLS ---
mock_tools = {
    "scan_repo": lambda *args, **kwargs: "Mock scan results: main.py, utils.py",
    "recall_fix": lambda *args, **kwargs: "Found 1 similar past fix in ChromaDB.",
    "save_checkpoint": lambda *args, **kwargs: "Checkpoint 'pre_implement' saved successfully.",
    "restore_checkpoint": lambda *args, **kwargs: "Checkpoint restored.",
    "consult_supervisor": lambda *args, **kwargs: json.dumps({"status": "approved", "critique": "Chaos test approved."}),
    "research_with_gemini": lambda *args, **kwargs: "Research: Quantum gravity requires bridging GR and QM.",
    "review_code_with_gemini": lambda *args, **kwargs: "Code review: No major issues found.",
    "ask_architect": lambda *args, **kwargs: "Architectural standards: Use local fallbacks for resilience.",
    "reflect_and_distill": lambda *args, **kwargs: "Task reflection: System successfully handled simulated chaos.",
    "run_code_safely": lambda *args, **kwargs: "Code executed successfully.",
    "remember_fix": lambda *args, **kwargs: "Fix successfully remembered in ChromaDB.",
    "maze_verification": lambda *args, **kwargs: json.dumps({"status": "verified", "path": "backtrack_clean"}),
    "guardrail_audit": lambda *args, **kwargs: json.dumps({"status": "safe", "findings": []}),
}

async def run_chaos_test():
    print("="*60)
    print("🔥 KENBUN CHAOS ORCHESTRATOR 🔥")
    print("="*60)

    # 1. TEST BUDGET LIMITS
    print("\n[CHAOS 1] Testing TokenGovernor Hard Limit...")
    old_budget = token_governor.daily_budget
    token_governor.daily_budget = 0.000001 
    print(f"  - Budget set to: ${token_governor.daily_budget}")
    
    try:
        res = await run_pipeline(
            workflow="bug_fix",
            task="Fix the mock bug.",
            tools=mock_tools,
            project_path=str(PROJECT_ROOT)
        )
        if "Budget Exceeded" in res:
            print("  ✅ SUCCESS: TokenGovernor halted the swarm correctly.")
        else:
            print(f"  ❌ FAILURE: Swarm should have been halted. Result: {res[:200]}...")
    except Exception as e:
        print(f"  ❌ ERROR: Budget test crashed: {e}")

    token_governor.daily_budget = old_budget

    # 2. TEST REMOTE CONNECTION FAILURE (CHAOS)
    print("\n[CHAOS 2] Testing Remote PC Connection Failure...")
    
    old_ip = settings.SWARM_PC_IP
    old_port = settings.CHROMA_PORT
    
    # Poison the settings singleton
    settings.SWARM_PC_IP = "10.255.255.1" 
    settings.CHROMA_PORT = 9999
    
    print(f"  - Poisoned SWARM_PC_IP in Sovereign Settings: {settings.SWARM_PC_IP}")
    print("  - Executing task requiring System 3 (Memory)...")
    
    start_time = time.time()
    try:
        res = await run_pipeline(
            workflow="research_implement",
            task="Research how 'Kenbun' mission connects to local fallback.",
            tools=mock_tools,
            project_path=str(PROJECT_ROOT)
        )
        
        duration = time.time() - start_time
        print(f"  - Pipeline finished in {duration:.2f}s")
        
        if "Research" in res or "mission" in res or "Kenbun" in res:
            print("  ✅ SUCCESS: Pipeline completed using mock tools despite connection failure.")
        else:
            print(f"  ❌ FAILURE: Pipeline did not return expected results. Result: {res[:200]}...")
            
    except Exception as e:
        print(f"  ❌ FAILURE: Pipeline crashed during connection failure: {e}")

    # Restore settings
    settings.SWARM_PC_IP = old_ip
    settings.CHROMA_PORT = old_port
    
    # 3. TEST INTELLIGENCE ROUTING (BAYESIAN SELECTION)
    print("\n[CHAOS 3] Testing Bayesian Routing Logic...")
    from tools.strategy.strategy_manager import governor
    
    # We'll simulate a tool selection between 'recall_fix' (High Confidence) and 'chaos_generator' (Low)
    candidate_tools = ["recall_fix", "chaos_generator"]
    
    print(f"  - Candidates: {candidate_tools}")
    print(f"  - recall_fix confidence: {governor.get_tool_confidence('recall_fix'):.2%}")
    print(f"  - chaos_generator confidence: {governor.get_tool_confidence('chaos_generator'):.2%}")
    
    selections = {"recall_fix": 0, "chaos_generator": 0}
    for _ in range(100):
        tool, _ = governor.sample_strategy(candidate_tools)
        selections[tool] += 1
        
    print(f"  - Selection Distribution (100 trials): {selections}")
    
    if selections["recall_fix"] > selections["chaos_generator"]:
        print(f"  ✅ SUCCESS: System correctly favored high-confidence 'recall_fix' ({selections['recall_fix']}%) over failing 'chaos_generator'.")
    else:
        print(f"  ❌ FAILURE: System selected failing tool more often than reliable tool.")

    print("\n" + "="*60)
    print("🏁 CHAOS TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_chaos_test())
