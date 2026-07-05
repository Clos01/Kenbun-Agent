#!/usr/bin/env python3
"""
🤖 autofix_type_errors.py
Agentic type-fixing script that runs Pyrefly to detect static analysis/import errors,
and dispatches Kenbun's 'bug_fix' orchestration pipeline to fix them automatically.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List

# 1. PATH BOOTSTRAP (Ensures core tools are importable)
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root / "core"))

try:
    from tools.infrastructure.server import orchestrate
except ImportError:
    print("❌ Failed to import Kenbun's orchestration engine.")
    sys.exit(1)

MAX_ITERATIONS = 3

def run_pyrefly_check() -> List[Dict]:
    """Runs Pyrefly and returns a list of detected error objects."""
    print("🔍 Running Pyrefly check...")
    cmd = ["uv", "run", "--with", "pyrefly", "pyrefly", "check", "--output-format=json"]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(project_root))
    
    if res.returncode == 0:
        return []
        
    try:
        data = json.loads(res.stdout)
        if isinstance(data, dict):
            return data.get("errors", [])
        elif isinstance(data, list):
            return data
        return []
    except json.JSONDecodeError:
        # Fallback in case of stdout format changes or non-zero crash exits
        print(f"⚠️ Pyrefly returned non-JSON output:\n{res.stdout or res.stderr}")
        return []

def group_errors_by_file(errors: List[Dict]) -> Dict[str, List[Dict]]:
    """Groups error list by file paths."""
    grouped = {}
    for err in errors:
        path = err.get("path")
        if path:
            abs_path = str(project_root / path)
            grouped.setdefault(abs_path, []).append(err)
    return grouped

def fix_file_errors(file_path: str, file_errors: List[Dict]) -> bool:
    """Dispatches Kenbun's bug_fix orchestration pipeline for a specific file."""
    relative_path = os.path.relpath(file_path, project_root)
    print(f"\n🚀 Dispatching Orchestrator to fix {relative_path}...")
    
    # Format error description
    error_details = []
    for err in file_errors:
        line = err.get("line", "?")
        code = err.get("code", "unknown")
        msg = err.get("message", "No message details provided.")
        error_details.append(f"  - Line {line} [{code}]: {msg}")
        
    task_desc = (
        f"Analyze and fix the following static type-checking and import errors in the file '{relative_path}'.\n"
        f"Make sure to keep all functional logic identical and only repair the types.\n\n"
        f"Errors found:\n" + "\n".join(error_details)
    )
    
    try:
        # Trigger bug_fix workflow asynchronously and wait for completion
        res = orchestrate(
            workflow="bug_fix",
            task=task_desc,
            file_path=file_path,
            project_path=str(project_root),
            wait=True
        )
        print(f"✅ Orchestrator returned results for {relative_path}:\n{res}")
        return True
    except Exception as e:
        print(f"❌ Orchestrator failed to run for {relative_path}: {e}")
        return False

def main():
    print("==================================================")
    print("🤖 STARTING KENBUN AGENTIC TYPE FIXER")
    print("==================================================")
    
    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n🔄 --- Iteration {iteration} / {MAX_ITERATIONS} ---")
        
        errors = run_pyrefly_check()
        if not errors:
            print("🎉 No type checking errors found! Codebase is perfectly clean.")
            break
            
        grouped_errors = group_errors_by_file(errors)
        print(f"🚨 Found {len(errors)} errors across {len(grouped_errors)} files.")
        
        # Select first file to fix in this iteration
        target_file = list(grouped_errors.keys())[0]
        target_errors = grouped_errors[target_file]
        
        success = fix_file_errors(target_file, target_errors)
        if not success:
            print("⚠️ Stopped iteration due to orchestrator error.")
            break
            
        # Optional: Sleep briefly between runs
        import time
        time.sleep(1)
    else:
        print(f"\n⚠️ Reached maximum iteration limit of {MAX_ITERATIONS}. Some errors may remain.")

if __name__ == "__main__":
    main()
