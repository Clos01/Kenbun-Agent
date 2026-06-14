#!/usr/bin/env python3
"""
🌊  FUJITORA OS PORTABILITY AUDIT TOOL (藤虎 - Wisteria Tiger)
Autonomic System 6 Batching Scanner for OS-Generalization and Portability.

Designed to scan the entire codebase file-by-file (avoiding OOM) to detect:
1. ping commands with hardcoded flags (e.g., -c 1, -t 1).
2. Hardcoded Unix system directories (/tmp/, /var/, /etc/).
3. Platform-dependent package imports (pwd, grp, winreg).
4. OS-specific terminal clear/shell commands (clear, cls).
"""

import os
import re
import json
from pathlib import Path
from typing import List, Dict, Any

# Colors
C_P = "\033[38;5;218m"  # Wisteria Pink
C_G = "\033[38;5;120m"  # Light Green
C_Y = "\033[38;5;226m"  # Gold
C_R = "\033[0m"         # Reset
C_RED = "\033[38;5;196m" # Vivid Red
C_D = "\033[38;5;244m"  # Dim Grey

EXCLUDE_FOLDERS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", 
    ".pytest_cache", "brain_health", ".benchmarks"
}

TEXT_EXTENSIONS = {
    ".py", ".sh", ".yml", ".yaml", ".json", "Dockerfile"
}

# 1. Ping command regex (checks for -c, -t, -n, -w flags that diverge between OS)
PING_FLAGS_REGEX = re.compile(r'ping["\']?\s+.*-([ctnw])\s+(\d+)')

# 2. Hardcoded absolute system paths (avoiding standard /dev/null, /var/run/docker.sock, or docker config mappings)
SYSTEM_PATH_REGEX = re.compile(r'["\']/(tmp|var|etc)/[a-zA-Z0-9_\-\.\/]+["\']')

# 3. Platform restricted imports
PLATFORM_IMPORTS_REGEX = re.compile(r'^\s*(import|from)\s+(pwd|grp|winreg|msvcrt|termios|fcntl)\b', re.MULTILINE)

# 4. OS-specific command assumptions (like running 'clear' or 'cls' in shell subprocesses)
OS_COMMAND_REGEX = re.compile(r'subprocess\.(run|Popen|call)\(\s*["\'](clear|cls)["\']')

class FujitoraAuditor:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    def check_file(self, file_path: Path) -> List[Dict[str, Any]]:
        breaches = []
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                content = "".join(lines)

            # File-wide check for restricted imports
            for match in PLATFORM_IMPORTS_REGEX.finditer(content):
                line_num = content[:match.start()].count('\n') + 1
                breaches.append({
                    "type": "Restricted Platform Import",
                    "line": line_num,
                    "snippet": match.group(0).strip(),
                    "guidance": "Importing unix-only or windows-only libraries directly will crash other systems. Use conditional try/except blocks."
                })

            for line_idx, line in enumerate(lines, 1):
                clean_line = line.strip()
                if not clean_line or clean_line.startswith("#") or clean_line.startswith("//"):
                    continue

                # A. Ping Flags Check
                ping_match = PING_FLAGS_REGEX.search(line)
                if ping_match:
                    breaches.append({
                        "type": "Divergent Ping Option",
                        "line": line_idx,
                        "snippet": clean_line,
                        "guidance": "Ping utility flags diverge between Unix (-c, -W) and Windows (-n, -w). Implement system detection via `platform.system()`."
                    })

                # B. System Paths Check
                path_match = SYSTEM_PATH_REGEX.search(line)
                if path_match:
                    # Filter out Docker sockets or config constants
                    if "docker.sock" not in clean_line and "size=" not in clean_line:
                        breaches.append({
                            "type": "Hardcoded Unix Directory Path",
                            "line": line_idx,
                            "snippet": clean_line,
                            "guidance": f"Avoid writing to '/{path_match.group(1)}/' directly. Use `tempfile.gettempdir()` or dynamic settings directories."
                        })

                # C. Subprocess Clear/Cls Check
                cmd_match = OS_COMMAND_REGEX.search(line)
                if cmd_match:
                    breaches.append({
                        "type": "OS-Specific Subprocess Command",
                        "line": line_idx,
                        "snippet": clean_line,
                        "guidance": f"Running OS-specific command '{cmd_match.group(2)}' directly will fail. Use platform detection or standard overrides."
                    })

        except Exception:
            # Prevent OOM or crash from corrupt files
            pass
        return breaches

    def stream_scan(self):
        """Generates breaches in a file-by-file generator format (OOM safe)."""
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_FOLDERS]
            root_path = Path(root)

            for file in files:
                file_path = root_path / file
                if file_path.suffix.lower() in TEXT_EXTENSIONS or file_path.name in TEXT_EXTENSIONS:
                    file_breaches = self.check_file(file_path)
                    if file_breaches:
                        yield file_path.relative_to(self.workspace_root), file_breaches

def run_fujitora_scan():
    script_dir = Path(__file__).resolve().parent
    workspace_root = script_dir.parent
    auditor = FujitoraAuditor(workspace_root)

    print(f"\n{C_P}🌊  INITIATING FUJITORA MULTI-OS COMPATIBILITY AUDIT{C_R}")
    print(f"{C_D}Target Workspace: {workspace_root.resolve()}{C_R}\n")

    report_results = []
    breach_count = 0
    file_count = 0

    # Stream files to prevent OOM
    for rel_path, file_breaches in auditor.stream_scan():
        file_count += 1
        print(f"📁 {C_Y}{rel_path}{C_R}")
        for b in file_breaches:
            breach_count += 1
            print(f"  🚨 Line {b['line']}: {C_RED}[{b['type']}]{C_R}")
            print(f"     Snippet:  `{b['snippet']}`")
            print(f"     Guidance: {b['guidance']}")
            print()
            
            report_results.append({
                "file": str(rel_path),
                "line": b["line"],
                "type": b["type"],
                "snippet": b["snippet"],
                "guidance": b["guidance"]
            })

    # Save findings JSON
    brain_health_dir = workspace_root / "brain_health"
    brain_health_dir.mkdir(parents=True, exist_ok=True)
    report_path = brain_health_dir / "fujitora_audit_results.json"
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_results, f, indent=2)

    print(f"{C_G}✓ Audit complete. Results saved to:{C_R} {report_path}")
    print(f"  📂 Files with Portability Issues: {C_Y}{file_count}{C_R}")
    print(f"  🚨 Total Portability Breaches:    {C_RED}{breach_count}{C_R}\n")

if __name__ == "__main__":
    run_fujitora_scan()
