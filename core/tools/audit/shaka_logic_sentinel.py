#!/usr/bin/env python3
"""
⛩️  SHAKA LOGIC SENTINEL (Vegapunk Punk-01 Satellite)
Autonomic System 6 Portability, Sandbox, and Container Privilege Auditor.

Enforces:
1. Haki Path Watch (覇気パス監視): Flags absolute host paths.
2. Kairoseki TTY Guard (海楼石TTY防御): Blocks interactive -it/-t flags in automation.
3. Logia Privilege Probe (ロギア特権調査): Warns about writing to /root/ in non-root contexts.
4. Den Den Mushi Host Match (電伝虫ホスト照合): Flags unconfigured Docker container name calls.
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Any

# Haki Path Watch: Matches absolute user/dev paths, ignoring Unix/Docker standards
PATH_REGEX = re.compile(r'["\']?/(Users|home|root)/[a-zA-Z0-9_\-\.\/]+["\']?')

# Kairoseki TTY Guard: Matches interactive docker exec/run calls
TTY_REGEX = re.compile(r'docker\s+(exec|run)\s+-[a-zA-Z]*t[a-zA-Z]*\s+')

# Logia Privilege Probe: Matches write/create attempts to /root inside non-root app context
ROOT_WRITE_REGEX = re.compile(r'[\"\']+/root/[a-zA-Z0-9_\-\.\/]+[\"\']+')

# Den Den Mushi Host Match: Matches docker execution calls to hardcoded container names
DOCKER_EXEC_REGEX = re.compile(r'docker\s+exec\s+-[a-zA-Z]*\s+([a-zA-Z0-9_\-]+)\s+')

class ShakaLogicSentinel:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        # Configured container names to whitelist (from docker-compose)
        self.known_containers = {"portable_fastmcp", "portable_ollama", "portable_dashboard", "portable_dozzle", "chromadb", "system3_brain"}

    def audit_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Statically scans a file for architectural logic breaches."""
        breaches = []
        try:
            # Skip binary/meta folders
            if any(part in file_path.parts for part in {".git", "node_modules", ".venv", "venv", "__pycache__", "brain_health"}):
                return []

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            for line_idx, line in enumerate(lines, 1):
                clean_line = line.strip()
                if not clean_line or clean_line.startswith("#"):
                    continue

                # 1. Check Haki Path Watch
                path_match = PATH_REGEX.search(line)
                if path_match:
                    # Allow dynamic setting fallbacks or environment vars
                    if "$" not in clean_line and "{" not in clean_line:
                        breaches.append({
                            "type": "Haki Path Watch (Absolute Path Violation)",
                            "line": line_idx,
                            "snippet": clean_line,
                            "guidance": "Replace absolute environment path with a relative path or an environment variable fallback."
                        })

                # 2. Check Kairoseki TTY Guard
                tty_match = TTY_REGEX.search(line)
                if tty_match:
                    breaches.append({
                        "type": "Kairoseki TTY Guard (TTY Flag in Script)",
                        "line": line_idx,
                        "snippet": clean_line,
                        "guidance": "Remove pseudo-TTY allocation flag '-t' (e.g. use '-i' instead of '-it') for non-interactive execution compatibility."
                    })

                # 3. Check Logia Privilege Probe
                root_write_match = ROOT_WRITE_REGEX.search(line)
                if root_write_match:
                    # Exclude typical docker volumes setup comments or specific base commands
                    if "docker-compose" not in str(file_path) and "docker exec" not in clean_line:
                        breaches.append({
                            "type": "Logia Privilege Probe (Unprivileged root Folder Assumption)",
                            "line": line_idx,
                            "snippet": clean_line,
                            "guidance": "Writing to '/root/' inside a container running as a non-root appuser will fail. Use '/app/' or dynamic home paths."
                        })

                # 4. Check Den Den Mushi Host Match
                docker_exec_match = DOCKER_EXEC_REGEX.search(line)
                if docker_exec_match:
                    target_container = docker_exec_match.group(1)
                    if target_container not in self.known_containers:
                        breaches.append({
                            "type": "Den Den Mushi Host Match (Unconfigured Container Name)",
                            "line": line_idx,
                            "snippet": clean_line,
                            "guidance": f"Container name '{target_container}' does not match configuration. Use settings parameter or dynamic docker discovery."
                        })

        except Exception as e:
            pass # Silent fail to prevent interrupting audit scans
        
        return breaches

    def scan_directory(self) -> Dict[str, List[Dict[str, Any]]]:
        """Recursively audits the workspace directory."""
        results = {}
        extensions = {".py", ".sh", ".yml", ".yaml", ".json", "Dockerfile"}
        
        for root, _, files in os.walk(self.workspace_root):
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix in extensions or file_path.name in extensions:
                    file_breaches = self.audit_file(file_path)
                    if file_breaches:
                        rel_path = file_path.relative_to(self.workspace_root)
                        results[str(rel_path)] = file_breaches
        return results

def run_sentinel_audit():
    workspace_root = Path(__file__).resolve().parent.parent.parent.parent
    sentinel = ShakaLogicSentinel(workspace_root)
    results = sentinel.scan_directory()
    
    # Text colors
    c_p = "\033[38;5;218m"  # Pink
    c_g = "\033[38;5;120m"  # Light Green
    c_y = "\033[38;5;226m"  # Gold
    c_r = "\033[0m"         # Reset
    c_red = "\033[38;5;196m" # Vivid Red
    
    print(f"\n{c_p}⛩️  SHAKA LOGIC SENTINEL: INITIATING PORTABILITY & PARITY SCAN{c_r}")
    print(f"Target Directory: {workspace_root}\n")
    
    if not results:
        print(f"{c_g}✓ Perfect Harmony! No logic or portability breaches found in the active workspace.{c_r}\n")
        return
        
    breach_count = 0
    for rel_path, file_breaches in results.items():
        print(f"📁 {c_y}{rel_path}{c_r}")
        for b in file_breaches:
            breach_count += 1
            print(f"  🚨 Line {b['line']}: {c_red}[{b['type']}]{c_r}")
            print(f"     Snippet:  `{b['snippet']}`")
            print(f"     Guidance: {b['guidance']}")
            print()
            
    print(f"🏁 Sentinel complete. Found {c_red}{breach_count}{c_r} potential portability breaches across the codebase.\n")

if __name__ == "__main__":
    run_sentinel_audit()
