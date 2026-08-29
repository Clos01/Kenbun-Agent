---
name: "code-integrity-sentinel"
description: "Autonomously detects and auto-fixes missing imports, undefined variables, unquoted dictionary key lookups, unused variables, syntax errors, and AST-level regressions across Python, TypeScript, and JavaScript whenever creating or modifying code."
version: "1.0.0"
license: "MIT"
---

# Code Integrity Sentinel (Universal Agent Skill)

Static analysis, AST validation, and automated hygiene for sovereign agentic coding.

Version: 1.0.0  
License: MIT

## Purpose

Use this skill whenever creating new software, writing scripts, editing files, or preparing code to be executed locally or dispatched across remote SSH satellites (e.g. P330).

This skill prevents the most common LLM coding bugs:
1. **Undefined Variables & NameError (F821)**: Referencing variables that were never initialized.
2. **Unquoted Dictionary Key Lookups**: Writing `dict.get(field_name)` when `field_name` was intended as a literal string `'field_name'`.
3. **Missing Standard Library / Framework Imports**: Forgetting `os`, `sys`, `time`, `json`, `subprocess`, `re`, `typing`, `uuid`, etc.
4. **Syntax & AST Regressions**: Malformed string interpolations, unbalanced parentheses, or improper async/await closures.

---

## Tool & CLI Integration

### 1. Standalone CLI Utility (`bin/code-sentinel`)
```bash
# Check modified git files
bin/code-sentinel check --diff

# Check a specific file
bin/code-sentinel check path/to/file.py

# Auto-fix missing imports and unquoted dict lookups
bin/code-sentinel fix path/to/file.py

# Continuous background monitoring
bin/code-sentinel watch
```

### 2. Kenbun Sovereign MCP Tool
```python
from tools.codebase.code_integrity_sentinel import audit_code_integrity

# Audit workspace changes
result = audit_code_integrity(target="workspace")

# Audit and autofix single file
result = audit_code_integrity(target="path/to/script.py", autofix=True)
```

### 3. Integrated Repo Scanner (`scan_repo`)
When running `scan_repo(project_path)`, the Code Integrity Sentinel automatically runs a background pass across all discovered files, appending a dedicated `🛡️ [Code Integrity Sentinel]` section to the generated Repo Map.

---

## Sentinel Rules & Auto-Fix Conventions

1. **Explicit Quoting on Dict Lookups**:
   - ❌ **Anti-Pattern**: `res.get(screen_delta_after, 0.0)`
   - ✅ **Correct**: `res.get("screen_delta_after", 0.0)`

2. **Zero Missing Imports**:
   - Always verify standard libraries (`os`, `sys`, `time`, `json`, `re`, `typing`) are imported at the top of every generated script.

3. **Browser Telemetry & Glean Error Suppression**:
   - When launching Firefox / headless browsers in automation or CI/CD pipelines, prevent crashreporter/Glean network errors:
   - `MOZ_CRASHREPORTER_DISABLE=1 MOZ_TELEMETRY_REPORTING=0 MOZ_DATA_REPORTING=0 GDK_BACKEND=x11 firefox ... >/dev/null 2>&1 &`

4. **Pre-Flight AST Compilation**:
   - Before executing code on remote satellites (`DISPLAY=:0`), pass the code through `ast.parse` to guarantee zero syntax or import errors.
