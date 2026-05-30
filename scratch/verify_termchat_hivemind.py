#!/usr/bin/env python3
import os
import sys
import json
import time
from pathlib import Path

# Add project root and scripts directory to path dynamically
project_root = Path("/Users/carlosrivas/Dev/kenbun-agent").resolve()
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "scripts"))

print("🌸 Kenbun Termchat Memory Layer Integration Test 🌸")
print(f"Project root set to: {project_root}")

# Try importing terminal_chat
try:
    import scripts.terminal_chat as tc
    print("✅ Successfully imported scripts.terminal_chat")
except ImportError as e:
    print(f"⚠️ Could not import via 'scripts.terminal_chat': {e}")
    try:
        import terminal_chat as tc
        print("✅ Successfully imported terminal_chat directly")
    except ImportError as e2:
        print(f"❌ Failed to import terminal_chat: {e2}")
        sys.exit(1)

# Ensure functions exist in the module
if not hasattr(tc, 'save_concept_to_hivemind') or not hasattr(tc, 'search_hivemind'):
    print("❌ save_concept_to_hivemind or search_hivemind not found in terminal_chat!")
    sys.exit(1)

save_func = tc.save_concept_to_hivemind
search_func = tc.search_hivemind

print("\n--- Test Set 1: User Requested Key/Value ---")
print("Calling save_concept_to_hivemind('Verification Test Key', 'Verification Test Value', 'test-run')...")
res_save1 = save_func("Verification Test Key", "Verification Test Value", "test-run")
print(f"Save Result:\n{res_save1}")

print("\nCalling search_hivemind('Verification Test Key')...")
res_search1 = search_func("Verification Test Key")
print(f"Search Result:\n{res_search1}")


print("\n--- Test Set 2: Audit Agent Requested Title/Content ---")
print("Calling save_concept_to_hivemind('Audit Test Title', 'Audit Test Content', 'audit-test')...")
res_save2 = save_func("Audit Test Title", "Audit Test Content", "audit-test")
print(f"Save Result:\n{res_save2}")

print("\nCalling search_hivemind('Audit Test Title')...")
res_search2 = search_func("Audit Test Title")
print(f"Search Result:\n{res_search2}")


print("\n--- Fallback Log Verification ---")
log_file = Path("/Users/carlosrivas/Dev/kenbun-agent/brain_health/failed_hivemind_memories.log")
if log_file.exists():
    print(f"✅ Fallback log file exists at: {log_file}")
    try:
        # Read the last few lines to see if our tests got logged
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        print(f"Total lines in log file: {len(lines)}")
        print("Recent log entries:")
        for line in lines[-5:]:
            print(f"  {line.strip()}")
    except Exception as e:
        print(f"❌ Error reading log file: {e}")
else:
    print(f"ℹ️ Fallback log file does not exist at: {log_file} (This may mean ChromaDB succeeded!)")

print("\n🌸 Verification Test Completed! 🌸")
