import sys
import os

# Add core to path so we can import orchestrator

from tools.infrastructure.orchestrator import orchestrate

if __name__ == "__main__":
    print("Running orchestrate with 'bug_fix' workflow and 'remove ghost variables' task...")
    result = orchestrate("bug_fix", "Find and fix ghost variables", file_path="test_ghost.py")
    print("\n--- ORCHESTRATOR REPORT ---")
    print(result)
