import sys
import os

# Add core to path so we can import orchestrator
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))

from tools.infrastructure.orchestrator import orchestrate

if __name__ == "__main__":
    print("Running orchestrate with 'bug_fix' workflow and 'remove ghost variables' task...")
    result = orchestrate("bug_fix", "Find and fix ghost variables", file_path="test_ghost.py")
    print("\n--- ORCHESTRATOR REPORT ---")
    print(result)
