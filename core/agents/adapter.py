"""
AgentToolInterface (Adapter Pattern) for Kenbun Swarm Agents.
Enforces type safety with Pydantic, jailing, and strict separation of concerns.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Callable, List, Optional
import pydantic
from pydantic import BaseModel, Field

# Central config paths
from tools.infrastructure.config import settings

class FileReadInput(BaseModel):
    """Schema for viewing file contents safely."""
    file_path: str = Field(..., description="Absolute path of the target file to view.")
    start_line: Optional[int] = Field(None, description="1-indexed line number to start viewing.")
    end_line: Optional[int] = Field(None, description="1-indexed line number to stop viewing.")

class CodeSearchInput(BaseModel):
    """Schema for executing exact string pattern search across codebase."""
    query: str = Field(..., description="The string or regex pattern to search for.")
    search_path: str = Field(..., description="Absolute path of the file or directory to scan.")

class FileEditInput(BaseModel):
    """Schema for safe, contiguous text replacements (requires HITL approval)."""
    file_path: str = Field(..., description="Absolute path of the target file to modify.")
    target_content: str = Field(..., description="Exact substring to find and replace.")
    replacement_content: str = Field(..., description="New content to insert in place of the target substring.")
    start_line: int = Field(..., description="Approximate starting line range for search mapping.")
    end_line: int = Field(..., description="Approximate ending line range for search mapping.")

class SandboxRunInput(BaseModel):
    """Schema for sandboxed shell executions (requires HITL approval & jail isolation)."""
    command_line: str = Field(..., description="Terminal command to execute inside the sandbox.")
    cwd: Optional[str] = Field(None, description="Execution context directory path (jailed).")

class HeritageSecurityException(PermissionError):
    """Custom security exception for telemetry compliance (HERITAGE_SEC_002)."""
    def __init__(self, message: str, error_code: str = "HERITAGE_SEC_002"):
        super().__init__(message)
        self.error_code = error_code

class AgentToolInterface:
    """
    Decoupled adapter representing standard allowed capabilities of a Swarm Agent.
    Implements path jailing and parameter validation before passing actions to core systems.
    """
    def __init__(self, workspace: Path = settings.PROJECT_ROOT):
        self.workspace = Path(workspace).resolve()

    def _jail_path(self, target_path: str) -> Path:
        """
        Enforces physical jail boundaries on the filesystem using strict path resolution.
        Intercepts directory traversal and symbolic link out-of-bounds escapes.
        """
        if not target_path:
            raise HeritageSecurityException(
                "Security Sentinel: Empty target path is rejected.",
                error_code="HERITAGE_SEC_002"
            )
            
        base = self.workspace.resolve()
        # resolve(strict=False) resolves any symlinks to find the absolute physical destination path
        resolved = Path(target_path).resolve(strict=False)
        
        if not resolved.is_relative_to(base):
            # Emit structured security violation log for forensic compliance audit (HERITAGE_OBS_001)
            print(f"[HERITAGE_SEC_AUDIT_FAIL] [Error Code: HERITAGE_SEC_002] Path traversal violation attempted for path: {target_path} (resolved: {resolved})")
            raise HeritageSecurityException(
                f"Security Sentinel: Path traversal violation! Access to {target_path} is blocked.",
                error_code="HERITAGE_SEC_002"
            )
        return resolved

    def view_file_adapted(self, params: FileReadInput) -> str:
        """Secure file viewing adapter."""
        target = self._jail_path(params.file_path)
        if not target.exists() or not target.is_file():
            return f"Error: File {params.file_path} not found."
            
        with open(target, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
        start = max(1, params.start_line or 1) - 1
        end = min(len(lines), params.end_line or len(lines))
        
        return "".join(lines[start:end])

    def code_search_adapted(self, params: CodeSearchInput) -> List[Dict[str, Any]]:
        """Secure grep code search adapter."""
        # Enforce search scope boundary
        self._jail_path(params.search_path)
        
        # Native, safe Python search implementation avoiding raw shell execution
        results = []
        target = Path(params.search_path)
        
        files_to_scan = []
        if target.is_file():
            files_to_scan.append(target)
        else:
            # Scan directories recursively up to 100 files limit to prevent CPU lockups
            for root, _, files in os.walk(target):
                for f in files:
                    if f.endswith((".py", ".tsx", ".ts", ".css", ".md", ".json")):
                        files_to_scan.append(Path(root) / f)
                        if len(files_to_scan) >= 100:
                            break
                if len(files_to_scan) >= 100:
                    break
                    
        for f_path in files_to_scan:
            try:
                with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if params.query in line:
                            results.append({
                                "file": str(f_path),
                                "line_number": i,
                                "content": line.strip()
                            })
                            if len(results) >= 50: # Cap at 50 results
                                return results
            except Exception:
                continue
        return results

    def edit_file_adapted(self, params: FileEditInput) -> str:
        """Secure file editing adapter (called only AFTER HITL approval)."""
        target = self._jail_path(params.file_path)
        if not target.exists() or not target.is_file():
            return f"Error: Target file {params.file_path} does not exist."
            
        with open(target, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        if params.target_content not in content:
            return "Error: Could not locate exactly matching target content inside file."
            
        # Contiguous single drop-in replacement
        updated = content.replace(params.target_content, params.replacement_content, 1)
        
        with open(target, "w", encoding="utf-8") as f:
            f.write(updated)
            
        return f"Successfully modified: {target.name}"

    def run_sandbox_adapted(self, params: SandboxRunInput) -> Dict[str, Any]:
        """Secure sandboxed shell runner (called only AFTER HITL approval)."""
        target_cwd = self.workspace
        if params.cwd:
            target_cwd = self._jail_path(params.cwd)
            
        # Strict injection blocker
        blocked_tokens = ["rm ", "sudo ", "chmod ", "wget ", "curl ", "> /dev"]
        if any(token in params.command_line for token in blocked_tokens):
            return {
                "success": False,
                "error": "Security Sentinel: Command rejected. Contains blocked execution token."
            }
            
        import subprocess
        try:
            # Execute in a strictly scoped sandboxed subprocess with limits
            result = subprocess.run(
                params.command_line,
                cwd=target_cwd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=15.0 # Strict execution deadline limit
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Sandbox Timeout: Command exceeded the maximum execution duration of 15s."
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
