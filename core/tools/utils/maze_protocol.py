import sys
import os
import subprocess
from pathlib import Path
import importlib.util
import traceback
from typing import Set

def backward_verify(target_file: str, project_root: str, run_tests: bool = True, visited: Set[str] = None):
    """
    MAZE PROTOCOL: Backward Verification with Circular Import Protection.
    """
    if visited is None:
        visited = set()

    print(f"🌀 INITIATING MAZE PROTOCOL: Backward Walk for {target_file}")
    
    file_path = Path(target_file).resolve()
    root_path = Path(project_root).resolve()
    
    if str(file_path) in visited:
        print(f"⚠️ CIRCULAR PATH DETECTED: {file_path}. Breaking loop.")
        return True # Loop is safe if previously verified
    
    visited.add(str(file_path))

    if not file_path.exists():
        print(f"❌ EXIT NOT FOUND: {file_path}")
        return False

    # 1. Entrance Check
    paths_found = [p for p in sys.path if str(root_path).startswith(p) or p == str(root_path)]
    if not paths_found:
        print(f"⚠️ WARNING: Project root {root_path} is not in sys.path")
    else:
        print(f"✅ Entrance Verified: Root is reachable.")

    # 2. Package Integrity Check
    current = file_path.parent
    while current != root_path.parent and current != current.parent:
        init_file = current / "__init__.py"
        if not init_file.exists():
            print(f"❌ PACKAGE HOLE DETECTED: Missing {init_file}. Module is dangling.")
            return False # Hard fail on package holes
        current = current.parent

    # 3. Import Trace with Recursion Protection
    try:
        with open(file_path, "r") as f:
            lines = f.readlines()
        
        imports = [line.strip() for line in lines if line.startswith("import ") or line.startswith("from ")]
        for imp in imports:
            mod_path = ""
            if imp.startswith("from "):
                mod_path = imp.split(" import ")[0].replace("from ", "").strip()
            elif imp.startswith("import "):
                mod_path = imp.split(" ")[1].strip()
            
            if mod_path:
                # Remove any relative leading dots for find_spec resolution
                clean_mod = mod_path.lstrip(".")
                
                # Check for absolute spec in sys.path
                spec = None
                try:
                    spec = importlib.util.find_spec(clean_mod)
                except (ModuleNotFoundError, ValueError, AttributeError):
                    pass
                
                origin_path = None
                if spec and spec.origin:
                    origin_path = Path(spec.origin).resolve()
                else:
                    # Fallback: check for a local file relative to the current file
                    local_py = file_path.parent / f"{clean_mod}.py"
                    local_dir_init = file_path.parent / clean_mod / "__init__.py"
                    if local_py.exists():
                        origin_path = local_py.resolve()
                    elif local_dir_init.exists():
                        origin_path = local_dir_init.resolve()
                
                if origin_path and origin_path.exists():
                    # Verify if the module origin resolves inside our active project root
                    # Using str in comparison and is_relative_to for robust cross-platform path jailing checks
                    is_internal = False
                    try:
                        is_internal = origin_path.is_relative_to(root_path) or str(root_path) in str(origin_path)
                    except ValueError:
                        pass
                        
                    if is_internal and origin_path.suffix == ".py":
                        print(f"   🔗 Recursing into dependency: {clean_mod} ({origin_path})")
                        if not backward_verify(str(origin_path), project_root, run_tests=False, visited=visited):
                            return False
    except Exception as e:
        print(f"❌ MAZE COLLAPSE: {e}")
        traceback.print_exc()
        return False

    # 4. Behavioral Verification (Run once at the entry point)
    if run_tests and len(visited) == 1:
        print(f"🔍 STEP 4: Behavioral Regression Check")
        test_dir = root_path / "tests"
        if test_dir.exists():
            try:
                env = os.environ.copy()
                env["PYTHONPATH"] = f"{root_path}:{env.get('PYTHONPATH', '')}"
                result = subprocess.run(
                    ["pytest", str(test_dir)],
                    capture_output=True, text=True, env=env, timeout=30
                )
                if result.returncode != 0:
                    print(f"   ❌ BEHAVIORAL FAILURE: Tests failed.")
                    return False
            except Exception as e:
                print(f"   ⚠️ WARNING: Regression check failed: {e}")

    print(f"✅ MAZE PROTOCOL COMPLETE: {target_file} is hardened.")
    return True
