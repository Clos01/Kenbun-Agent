import sys
import time

print("Starting import diagnostic...")

modules_to_test = [
    "tools.infrastructure.config",
    "tools.strategy.strategy_manager",
    "tools.strategy.decision_logic",
    "tools.infrastructure.topology_manager",
    "tools.infrastructure.orchestrator",
    "tools.strategy.intelligence_engine",
    "tools.audit.guardrail_agent",
    "tools.execution.claude_code_agent",
    "tools.execution.p330_worker",
    "tools.utils.workspace_manager",
    "tools.strategy.token_governor",
    "tools.autonomic.autonomic_corrector",
    "tools.memory.chroma_db_connect"
]

for mod in modules_to_test:
    print(f"Importing {mod}...", flush=True)
    t0 = time.time()
    try:
        __import__(mod)
        t1 = time.time()
        print(f"✅ Imported {mod} in {t1-t0:.4f}s", flush=True)
    except Exception as e:
        print(f"❌ Failed to import {mod}: {e}", flush=True)

print("Import diagnostic finished!")
