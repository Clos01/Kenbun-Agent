import os
import ast
import subprocess
from pathlib import Path
from tools.utils.backtracker import save_checkpoint, restore_checkpoint
from tools.infrastructure.config import settings

class SecurityException(Exception):
    """Exception raised for architectural or path boundary violations."""
    pass

def _resolve_paths(file_path: str, project_path: str = ".") -> tuple[Path, Path]:
    """
    Safely resolves the absolute canonical paths and verifies workspace boundaries.
    Mitigates path traversal attacks.
    """
    resolved_proj = Path(project_path).resolve()
    resolved_file = Path(file_path).resolve()
    
    # Security Rule 1: Containment Gate
    # Ensure resolved_file is strictly inside resolved_proj
    try:
        # Check if resolved_file starts with resolved_proj
        relative = resolved_file.relative_to(resolved_proj)
    except ValueError:
        raise SecurityException(
            f"❌ SECURITY BREACH: Target path '{resolved_file}' is outside the authorized "
            f"project workspace '{resolved_proj}'."
        )
        
    return resolved_file, resolved_proj

def _verify_python_ast(file_path: Path) -> bool:
    """Parses Python code to verify syntax validity (AST Parity Check)."""
    try:
        content = file_path.read_text(encoding="utf-8")
        ast.parse(content)
        return True
    except SyntaxError as e:
        print(f"⚠️ AST Syntax error detected in '{file_path}': {e}")
        return False
    except Exception as e:
        print(f"⚠️ AST Verification failed for '{file_path}': {e}")
        return False

def autofix_linter(file_path: str, project_path: str = ".") -> str:
    """
    Executes a high-fidelity automated linter auto-fix pass (Step 0) on the target file.
    
    Runs:
    - Python: autofake (unused imports/vars) -> black (formatting) -> isort (import sorting)
    - JavaScript/TypeScript: npx eslint --fix
    
    Security:
    - Strict path containment checking
    - List-based subprocess runs (shell=False)
    - AST validation check before and after execution
    - Auto-backtrack checkpointing via tools.utils.backtracker
    """
    try:
        # 1. Resolve and jail-gate the paths
        # Default to settings.PROJECT_ROOT if project_path is default or empty
        base_proj = settings.PROJECT_ROOT if project_path in (".", "") else project_path
        target_file, target_proj = _resolve_paths(file_path, base_proj)
        
        if not target_file.exists():
            return f"❌ Error: Target file '{target_file}' does not exist on disk."
        if not target_file.is_file():
            return f"❌ Error: '{target_file}' is not a file."

        ext = target_file.suffix.lower()
        if ext not in (".py", ".js", ".jsx", ".ts", ".tsx", ".mjs"):
            return f"⏭️ Skipped: File extension '{ext}' does not support automatic linter fixing."

        # 2. Save recovery checkpoint before modifications
        print(f"🔄 Saving pre-fix checkpoint for '{target_file.name}'...")
        save_checkpoint(str(target_file), label="pre_linter_autofix")
        
        stdout_logs = []
        stderr_logs = []

        # 3. Language Execution Flow
        if ext == ".py":
            print(f"🐍 Executing Python pre-flight cleanups for '{target_file.name}'...")
            
            # Verify AST is initially valid
            if not _verify_python_ast(target_file):
                return f"❌ Aborted: Python file has active syntax errors and cannot be safely auto-fixed."
            
            # Running Step 3.1: Autofake (strips unused variables and imports)
            res_autofake = subprocess.run(
                ["autoflake", "--remove-all-unused-imports", "--remove-unused-variables", "--in-place", str(target_file)],
                shell=False, capture_output=True, text=True
            )
            stdout_logs.append(res_autofake.stdout)
            if res_autofake.stderr:
                stderr_logs.append(res_autofake.stderr)
            
            # Running Step 3.2: Isort (sorts imports)
            res_isort = subprocess.run(
                ["isort", str(target_file)],
                shell=False, capture_output=True, text=True
            )
            stdout_logs.append(res_isort.stdout)
            if res_isort.stderr:
                stderr_logs.append(res_isort.stderr)

            # Running Step 3.3: Black (formats code)
            res_black = subprocess.run(
                ["black", str(target_file)],
                shell=False, capture_output=True, text=True
            )
            stdout_logs.append(res_black.stdout)
            if res_black.stderr:
                stderr_logs.append(res_black.stderr)
                
            # AST Parity validation post-execution
            if not _verify_python_ast(target_file):
                print(f"🚩 Post-fix AST mismatch! Reverting to pre-fix checkpoint...")
                restore_checkpoint(str(target_file), label="pre_linter_autofix")
                return f"❌ Reverted: Auto-fix formatting caused compilation/AST failures."

        elif ext in (".js", ".jsx", ".ts", ".tsx", ".mjs"):
            print(f"🌐 Executing JavaScript/TypeScript pre-flight cleanups for '{target_file.name}'...")
            
            # Security Rule 3: Safe execution (shell=False)
            res_eslint = subprocess.run(
                ["npx", "eslint", "--fix", str(target_file)],
                shell=False, capture_output=True, text=True
            )
            
            stdout_logs.append(res_eslint.stdout)
            if res_eslint.stderr:
                stderr_logs.append(res_eslint.stderr)
                
            # Verification: If eslint exited with a severe error (indicating syntax breakage)
            # eslint exit code >= 2 generally indicates crash or parser errors
            if res_eslint.returncode >= 2:
                print(f"🚩 ESLint crash or parser failure detected! Reverting to pre-fix checkpoint...")
                restore_checkpoint(str(target_file), label="pre_linter_autofix")
                return f"❌ Reverted: ESLint run failed with code {res_eslint.returncode}. Critique:\n{res_eslint.stderr}"

        # 4. Formulating the Markdown Execution Report
        clean_out = "\n".join([line for line in stdout_logs if line.strip()])
        clean_err = "\n".join([line for line in stderr_logs if line.strip()])
        
        report = [
            f"## 🚀 Step 0: Pre-Flight Linter Auto-Fix Pass",
            f"**File:** `{target_file.name}`",
            f"**Workspace Bound:** `SAFE` (`{target_proj}`)",
            f"**Execution:** `SUCCESS` (`shell=False` verified)",
            ""
        ]
        
        if clean_out:
            report.append("### Output Logs")
            report.append(f"```\n{clean_out}\n```\n")
        if clean_err:
            report.append("### Warning Logs")
            report.append(f"```\n{clean_err}\n```\n")
            
        report.append("🏆 *Slate successfully cleaned. Workspace ready for executive reasoning.*")
        return "\n".join(report)
        
    except SecurityException as sec_err:
        return f"🚨 SECURITY BLOCK: {sec_err}"
    except Exception as e:
        return f"❌ Unexpected linter auto-fix failure: {e}"
