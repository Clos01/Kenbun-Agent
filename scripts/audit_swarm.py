import os
import json
import concurrent.futures
from pathlib import Path

# Add core to path so tools imports work

from tools.infrastructure.orchestrator import orchestrate

def find_code_files(base_dir: Path) -> list:
    extensions = {".py", ".ts", ".tsx", ".js", ".jsx"}
    files = []
    # Avoid massive dirs like node_modules or .venv
    for root, dirs, filenames in os.walk(base_dir):
        if "node_modules" in dirs:
            dirs.remove("node_modules")
        if ".venv" in dirs:
            dirs.remove(".venv")
        if ".git" in dirs:
            dirs.remove(".git")
        if "__pycache__" in dirs:
            dirs.remove("__pycache__")
        if "build" in dirs:
            dirs.remove("build")
        if "dist" in dirs:
            dirs.remove("dist")
            
        for name in filenames:
            ext = os.path.splitext(name)[1]
            if ext in extensions:
                files.append(Path(root) / name)
    return files

def audit_file(file_path: Path, project_root: str) -> dict:
    print(f"[+] Spawning agent for {file_path.name}...")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
            
        task_prompt = "Audit this file specifically for MISSING VARIABLES, UNDEFINED NAMES, and GHOST/DEAD/UNREACHABLE code. If it is completely clean, reply exactly with 'CLEAN'. Otherwise, list the issues."
        
        tech_key = "python" if file_path.suffix == ".py" else "nextjs"
        
        report = orchestrate(
            workflow="code_review",
            task=task_prompt,
            project_path=project_root,
            file_path=str(file_path),
            code_snippet=code[:10000],  # truncate to avoid crazy massive files if any
            tech_key=tech_key
        )
        
        report_text = "\n".join(report)
        if "CLEAN" in report_text and "undefined" not in report_text.lower() and "missing" not in report_text.lower():
            return {"file": str(file_path), "status": "CLEAN", "issues": []}
        else:
            return {"file": str(file_path), "status": "ISSUES_FOUND", "issues": [report_text]}
    except Exception as e:
        return {"file": str(file_path), "status": "ERROR", "issues": [str(e)]}

def main():
    root = Path(__file__).resolve().parent.parent
    
    # Gather files from core, scripts, dashboard
    target_dirs = [root / "core", root / "scripts", root / "dashboard"]
    code_files = []
    for d in target_dirs:
        code_files.extend(find_code_files(d))
        
    print(f"🚀 Launching swarm of {len(code_files)} agents (bounded to 15 concurrent threads)...")
    
    results = []
    issues_found = 0
    # Using 15 threads to prevent rate-limiting and OOM errors
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(audit_file, f, str(root)): f for f in code_files}
        
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            results.append(res)
            if res["status"] == "ISSUES_FOUND":
                print(f"🚨 ISSUES in {Path(res['file']).name}")
                issues_found += 1
            elif res["status"] == "ERROR":
                print(f"⚠️ ERROR in {Path(res['file']).name}: {res['issues'][0]}")
            else:
                print(f"✅ {Path(res['file']).name} is clean.")
                
    # Write summary
    out_path = root / "audit_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"🏁 Swarm completed. {issues_found} files with potential issues. Results written to {out_path}")

if __name__ == "__main__":
    main()
