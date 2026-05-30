#!/usr/bin/env python3
"""
🏛️ Kenbun Sovereignty & Quality Audit Engine (System 6)
Programmatically performs a comprehensive repository-wide architectural,
security, compatibility, and code hygiene scan.
"""

import os
import sys
import re
from pathlib import Path

# Color styling for CLI output
C_P = "\033[38;5;218m"  # Pink
C_G = "\033[38;5;120m"  # Light Green
C_Y = "\033[38;5;226m"  # Gold
C_R = "\033[0m"         # Reset
C_RED = "\033[38;5;196m" # Vivid Red
C_C = "\033[38;5;87m"   # Cyan
C_D = "\033[38;5;244m"  # Dim Grey
C_W = "\033[38;5;231m"  # White

EXCLUDE_FOLDERS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".DS_Store",
    "brain_health",
}

TEXT_EXTENSIONS = {
    ".py", ".md", ".json", ".txt", ".yml", ".yaml", 
    ".sh", ".example", ".css", ".toml", ".tsx", ".ts",
    "Dockerfile", "Makefile"
}

def scan_repository(workspace_root: Path):
    print(f"\n{C_P}🛡️  INITIATING KENBUN FULL ARCHITECTURAL & HYGIENE SCAN{C_R}")
    print(f"{C_D}Target Workspace: {workspace_root.resolve()}{C_R}\n")

    # Metrics registries
    hardcoded_paths = []
    bare_excepts = []
    file_map = {} # basename -> list of absolute paths
    god_modules = []
    import_shims = []
    total_files = 0
    total_loc = 0

    # Compile regexes
    path_regex = re.compile(r'["\']/(Users|home|tmp|var)/[a-zA-Z0-9_\-\.\/]+["\']')
    except_regex = re.compile(r'^\s*except\s*:\s*$', re.MULTILINE)
    shim_regex = re.compile(r'sys\.path\.(insert|append)')

    for root, dirs, files in os.walk(workspace_root):
        # Exclude directories in-place
        dirs[:] = [d for d in dirs if d not in EXCLUDE_FOLDERS]
        root_path = Path(root)

        for file in files:
            file_path = root_path / file
            
            # Skip temp files, log files, or artifacts
            if file_path.suffix.lower() not in TEXT_EXTENSIONS and file_path.name not in TEXT_EXTENSIONS:
                continue

            total_files += 1

            # Duplicate tracking
            basename = file_path.name
            if file_path.suffix == ".py":
                file_map.setdefault(basename, []).append(file_path)

            # Analyze Python contents
            if file_path.suffix == ".py":
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        loc = len(lines)
                        total_loc += loc
                        content = "".join(lines)

                    rel_path = file_path.relative_to(workspace_root)

                    # 1. God Module Check
                    if loc > 600:
                        god_modules.append((rel_path, loc))

                    # 2. Hardcoded User Paths
                    for line_idx, line in enumerate(lines, 1):
                        if path_regex.search(line):
                            # Skip common self-healing/probe checks if any
                            if "docker.sock" in line or "/dev/null" in line:
                                continue
                            hardcoded_paths.append((rel_path, line_idx, line.strip()))

                    # 3. Bare Except Checks
                    for match in except_regex.finditer(content):
                        # Find line number
                        char_idx = match.start()
                        line_num = content[:char_idx].count('\n') + 1
                        bare_excepts.append((rel_path, line_num))

                    # 4. Import Shims Check
                    for line_idx, line in enumerate(lines, 1):
                        if shim_regex.search(line):
                            import_shims.append((rel_path, line_idx, line.strip()))

                except Exception as e:
                    print(f"{C_Y}⚠️ Could not scan file {file_path}: {e}{C_R}")

    # Build Report
    report_lines = []
    report_lines.append("# 🏛️ Kenbun Sovereignty & Code Quality Audit Scan Report")
    report_lines.append("")
    report_lines.append(f"**Scan Location:** `{workspace_root.resolve()}`  ")
    report_lines.append(f"**Total Scanned Files:** {total_files}  ")
    report_lines.append(f"**Total Python LOC:** {total_loc}  ")
    report_lines.append("")
    report_lines.append("## 1. Executive Summary")
    report_lines.append("This autonomic scan reviews architectural drift, security risks (hardcoded dev environments), code health (raw except blocks), and scalability blockages across the codebase.")
    report_lines.append("")

    # Section 2: God Modules (> 600 LOC)
    report_lines.append("## 2. God Modules (High Architectural Refactor Priority)")
    report_lines.append("These modules concentrate too much responsibility and are high targets for splitting into dedicated single-responsibility packages.")
    report_lines.append("")
    if god_modules:
        report_lines.append("| File Path | Lines of Code | Refactor Suggestion |")
        report_lines.append("|---|---|---|")
        for g_path, g_loc in sorted(god_modules, key=lambda x: x[1], reverse=True):
            report_lines.append(f"| [{g_path}](file://{workspace_root / g_path}) | **{g_loc}** | Split into submodules or separate routers |")
    else:
        report_lines.append("✓ No god modules (> 600 LOC) found. Excellent modular encapsulation!")
    report_lines.append("")

    # Section 3: Hardcoded User Paths (Portability Risk)
    report_lines.append("## 3. Hardcoded Developer Paths (Security & Portability Risk)")
    report_lines.append("These absolute paths prevent execution on different developer machines, Docker containers, or staging servers. They should be replaced with relative paths or environment variables.")
    report_lines.append("")
    if hardcoded_paths:
        report_lines.append("| File Path | Line | Code Snippet |")
        report_lines.append("|---|---|---|")
        for h_path, h_line, h_snippet in hardcoded_paths:
            report_lines.append(f"| [{h_path}](file://{workspace_root / h_path}#L{h_line}) | {h_line} | `{h_snippet}` |")
    else:
        report_lines.append("✓ No hardcoded developer paths found. Highly portable config!")
    report_lines.append("")

    # Section 4: Duplicate Filenames (Shadowing Risk)
    report_lines.append("## 4. Duplicate Filenames (Import Shadowing Risk)")
    report_lines.append("Having identical Python filenames across different directories causes import shadowing issues, broken singletons, and developer confusion.")
    report_lines.append("")
    duplicates = {k: v for k, v in file_map.items() if len(v) > 1}
    if duplicates:
        report_lines.append("| Basename | Duplicated Paths |")
        report_lines.append("|---|---|")
        for base, paths in duplicates.items():
            path_links = ", ".join([f"[{p.relative_to(workspace_root)}](file://{p})" for p in paths])
            report_lines.append(f"| `{base}` | {path_links} |")
    else:
        report_lines.append("✓ No duplicate python filenames found. Clean namespace layout!")
    report_lines.append("")

    # Section 5: Bare Except Clauses (Stability Risk)
    report_lines.append("## 5. Bare `except:` Clauses (Hangs & Termination Failures)")
    report_lines.append("Bare `except:` blocks intercept system exit exceptions (like `KeyboardInterrupt` or `SystemExit`), preventing clean termination and causing terminal shell lockups. Replace with `except Exception:`.")
    report_lines.append("")
    if bare_excepts:
        report_lines.append("| File Path | Line | Recommended Fix |")
        report_lines.append("|---|---|---|")
        for b_path, b_line in bare_excepts:
            report_lines.append(f"| [{b_path}](file://{workspace_root / b_path}#L{b_line}) | {b_line} | Use `except Exception:` or explicitly declare target classes |")
    else:
        report_lines.append("✓ No bare `except:` clauses found. Perfect exception safety!")
    report_lines.append("")

    # Section 6: Import Path Shims (Technical Debt)
    report_lines.append("## 6. Import Path Shims (`sys.path` tampering)")
    report_lines.append("Dynamically injecting paths into `sys.path` is a smell that indicates inconsistent import schemes. Use absolute package imports (`from tools.core.x`) and standard package layouts.")
    report_lines.append("")
    if import_shims:
        report_lines.append("| File Path | Line | Snippet |")
        report_lines.append("|---|---|---|")
        for s_path, s_line, s_snippet in import_shims:
            report_lines.append(f"| [{s_path}](file://{workspace_root / s_path}#L{s_line}) | {s_line} | `{s_snippet}` |")
    else:
        report_lines.append("✓ No `sys.path` manipulations detected. High import standards!")
    report_lines.append("")

    # Write output report
    report_content = "\n".join(report_lines)
    
    # Save as artifact
    artifact_dir = Path("/Users/carlosrivas/.gemini/antigravity/brain/058c08d2-a921-45b9-b708-16e78077597b")
    artifact_path = artifact_dir / "architecture_audit_report.md"
    
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        with open(artifact_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(f"{C_G}✓ Architecture Audit Report saved to:{C_R} {artifact_path}\n")
    except Exception as e:
        print(f"{C_RED}❌ Failed to save audit report to artifacts: {e}{C_R}\n")

    # Print CLI Summary
    print(f"{C_G}✦ SCAN COMPLETE SUMMARY ✦{C_R}")
    print(f"  📂 Scanned Files:   {C_W}{total_files}{C_R}")
    print(f"  🐍 Python LOC:      {C_W}{total_loc}{C_R}")
    print(f"  👹 God Modules:     {C_RED if god_modules else C_G}{len(god_modules)}{C_R}")
    print(f"  🚨 Hardcoded Paths: {C_RED if hardcoded_paths else C_G}{len(hardcoded_paths)}{C_R}")
    print(f"  ⚠️  Bare Excepts:    {C_RED if bare_excepts else C_G}{len(bare_excepts)}{C_R}")
    print(f"  🔗 Import Shims:    {C_Y if import_shims else C_G}{len(import_shims)}{C_R}")
    print(f"  🎭 Duplicates:      {C_Y if duplicates else C_G}{len(duplicates)}{C_R}")
    print()

if __name__ == "__main__":
    script_dir = Path(__file__).resolve().parent
    workspace_root = script_dir.parent
    scan_repository(workspace_root)
