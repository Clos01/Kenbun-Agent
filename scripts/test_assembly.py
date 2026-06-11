import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.tools.infrastructure.orchestrator import orchestrate

def spawn_agent(agent_id: int):
    print(f"[{agent_id}] Spawning Agent...")
    try:
        # Intentionally bad code that will fail when run_code_safely or similar is called
        buggy_code = f"def broken_function_{agent_id}():\n    print('Hello' \n   return True"
        
        # orchestrate is not async by default, but wait, let's check its signature.
        report = orchestrate(
            workflow="bug_fix",
            task=f"Test {agent_id}: Fix the syntax error in this code.",
            file_path="dummy.py",
            project_path=str(Path.cwd()),
            code_snippet=buggy_code,
            tech_key="python"
        )
        
        report_text = "\n".join(report)
        if "Auto-Correction Triggered" in report_text or "consult_supervisor" in report_text:
            print(f"[{agent_id}] ✅ Auto-Correction SUCCESSFUL!")
        else:
            print(f"[{agent_id}] ❌ Completed, but no auto-correction detected.")
            
    except Exception as e:
        print(f"[{agent_id}] ⚠️ Error: {e}")

import concurrent.futures

def main():
    print("🚀 Launching 10-Agent Orchestrator Assembly Test...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(spawn_agent, i) for i in range(1, 11)]
        concurrent.futures.wait(futures)
    print("🏁 Assembly Test Complete!")

if __name__ == "__main__":
    main()
