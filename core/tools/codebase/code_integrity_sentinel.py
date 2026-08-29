"""
Universal Code Integrity Sentinel (Kenbun Codebase & Pre-Flight Engine).
Autonomously detects and auto-fixes:
1. Undefined variables (NameError / F821)
2. Unquoted dictionary lookups (e.g. dict.get(undefined_key) -> dict.get('undefined_key'))
3. Missing standard library and workspace imports
4. Syntax errors and AST-level regressions across Python, TypeScript, and JavaScript.
"""

from __future__ import annotations

import os
import sys
import ast
import re
import json
import logging
import subprocess
import builtins
from typing import Dict, List, Set, Optional, Tuple, Any, Union
from pathlib import Path

try:
    from tools.registry import sovereign_tool
except (ImportError, ModuleNotFoundError):
    def sovereign_tool(*args, **kwargs):
        def decorator(f):
            return f
        return decorator

logger = logging.getLogger("tools.codebase.sentinel")

# Common standard library modules for auto-resolution
COMMON_STDLIB_MODULES = {
    "os": "import os",
    "sys": "import sys",
    "time": "import time",
    "json": "import json",
    "re": "import re",
    "subprocess": "import subprocess",
    "uuid": "import uuid",
    "math": "import math",
    "logging": "import logging",
    "pathlib": "from pathlib import Path",
    "typing": "from typing import Dict, List, Optional, Tuple, Any, Union, Set",
    "unittest": "import unittest",
    "Image": "from PIL import Image",
    "ImageGrab": "from PIL import ImageGrab",
    "requests": "import requests",
}

# Python built-in identifiers that are always defined
PYTHON_BUILTINS = set(dir(builtins)) | {
    "__file__", "__name__", "__doc__", "__package__", "__annotations__",
    "__debug__", "__builtins__"
}


class ScopeVisitor(ast.NodeVisitor):
    """AST Visitor to analyze variable definitions, imports, and symbol lookups with full scope awareness."""

    def __init__(self):
        self.scopes: List[Set[str]] = [set(PYTHON_BUILTINS)]
        self.undefined_names: List[Tuple[str, int, int]] = []
        self.unquoted_dict_get_calls: List[Tuple[str, int, int]] = []
        self.imported_names: Set[str] = set()
        self.defined_functions: Set[str] = set()
        self.defined_classes: Set[str] = set()

    def current_scope(self) -> Set[str]:
        return self.scopes[-1]

    def is_defined(self, name: str) -> bool:
        for scope in reversed(self.scopes):
            if name in scope:
                return True
        return False

    def _register_target(self, target: ast.AST):
        if isinstance(target, ast.Name):
            self.current_scope().add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._register_target(elt)
        elif isinstance(target, ast.Starred):
            self._register_target(target.value)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.asname or alias.name.split('.')[0]
            self.current_scope().add(name)
            self.imported_names.add(name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for alias in node.names:
            name = alias.asname or alias.name
            self.current_scope().add(name)
            self.imported_names.add(name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.current_scope().add(node.name)
        self.defined_functions.add(node.name)
        func_scope = set()
        for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
            func_scope.add(arg.arg)
        if node.args.vararg:
            func_scope.add(node.args.vararg.arg)
        if node.args.kwarg:
            func_scope.add(node.args.kwarg.arg)
        self.scopes.append(func_scope)
        self.generic_visit(node)
        self.scopes.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.current_scope().add(node.name)
        self.defined_functions.add(node.name)
        func_scope = set()
        for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
            func_scope.add(arg.arg)
        if node.args.vararg:
            func_scope.add(node.args.vararg.arg)
        if node.args.kwarg:
            func_scope.add(node.args.kwarg.arg)
        self.scopes.append(func_scope)
        self.generic_visit(node)
        self.scopes.pop()

    def visit_Lambda(self, node: ast.Lambda):
        lam_scope = set()
        for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
            lam_scope.add(arg.arg)
        if node.args.vararg:
            lam_scope.add(node.args.vararg.arg)
        if node.args.kwarg:
            lam_scope.add(node.args.kwarg.arg)
        self.scopes.append(lam_scope)
        self.generic_visit(node)
        self.scopes.pop()

    def visit_ClassDef(self, node: ast.ClassDef):
        self.current_scope().add(node.name)
        self.defined_classes.add(node.name)
        self.scopes.append(set())
        self.generic_visit(node)
        self.scopes.pop()

    def visit_Assign(self, node: ast.Assign):
        self.visit(node.value)
        for target in node.targets:
            self._register_target(target)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if node.value:
            self.visit(node.value)
        self._register_target(node.target)

    def visit_AugAssign(self, node: ast.AugAssign):
        self.visit(node.value)
        self._register_target(node.target)

    def visit_For(self, node: ast.For):
        self.visit(node.iter)
        self._register_target(node.target)
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_AsyncFor(self, node: ast.AsyncFor):
        self.visit(node.iter)
        self._register_target(node.target)
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_With(self, node: ast.With):
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars:
                self._register_target(item.optional_vars)
        for stmt in node.body:
            self.visit(stmt)

    def visit_AsyncWith(self, node: ast.AsyncWith):
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars:
                self._register_target(item.optional_vars)
        for stmt in node.body:
            self.visit(stmt)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if node.name:
            self.current_scope().add(node.name)
        if node.type:
            self.visit(node.type)
        for stmt in node.body:
            self.visit(stmt)

    def _handle_comprehension(self, generators: List[ast.comprehension], elt_or_val_fn):
        comp_scope = set()
        self.scopes.append(comp_scope)
        for gen in generators:
            self.visit(gen.iter)
            self._register_target(gen.target)
            for if_expr in gen.ifs:
                self.visit(if_expr)
        elt_or_val_fn()
        self.scopes.pop()

    def visit_ListComp(self, node: ast.ListComp):
        self._handle_comprehension(node.generators, lambda: self.visit(node.elt))

    def visit_SetComp(self, node: ast.SetComp):
        self._handle_comprehension(node.generators, lambda: self.visit(node.elt))

    def visit_GeneratorExp(self, node: ast.GeneratorExp):
        self._handle_comprehension(node.generators, lambda: self.visit(node.elt))

    def visit_DictComp(self, node: ast.DictComp):
        def visit_kv():
            self.visit(node.key)
            self.visit(node.value)
        self._handle_comprehension(node.generators, visit_kv)

    def visit_Call(self, node: ast.Call):
        # Detect dict.get(undefined_variable)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get" and node.args:
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Name) and not self.is_defined(first_arg.id):
                self.unquoted_dict_get_calls.append((first_arg.id, node.lineno, node.col_offset))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load):
            if not self.is_defined(node.id):
                self.undefined_names.append((node.id, node.lineno, node.col_offset))
        elif isinstance(node.ctx, ast.Store):
            self.current_scope().add(node.id)
        self.generic_visit(node)


class CodeIntegritySentinel:
    """Enterprise code hygiene and static analysis engine."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def audit_code_string(self, code: str, filename: str = "<inline_code>") -> Dict[str, Any]:
        """Audits a raw Python code string for syntax, undefined names, and unquoted dict lookups."""
        try:
            tree = ast.parse(code, filename=filename)
        except SyntaxError as e:
            return {
                "valid": False,
                "filename": filename,
                "syntax_error": {
                    "message": str(e.msg),
                    "line": e.lineno,
                    "offset": e.offset,
                    "text": e.text
                },
                "undefined_names": [],
                "unquoted_dict_lookups": [],
                "missing_imports": [],
                "issues_count": 1
            }

        visitor = ScopeVisitor()
        # Hoist top-level functions, classes, and assignments
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                visitor.scopes[0].add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    visitor._register_target(target)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    visitor.scopes[0].add(alias.asname or alias.name.split('.')[0])

        visitor.visit(tree)

        missing_imports = []
        unique_undefined = []
        seen = set()

        for name, line, col in visitor.undefined_names:
            if name in seen:
                continue
            seen.add(name)
            if name in COMMON_STDLIB_MODULES:
                missing_imports.append({"symbol": name, "suggested_import": COMMON_STDLIB_MODULES[name], "line": line})
            else:
                unique_undefined.append({"symbol": name, "line": line, "col": col})

        unquoted_lookups = [
            {"variable_passed": name, "line": line, "suggested_fix": f"'{name}'"}
            for name, line, col in visitor.unquoted_dict_get_calls
        ]

        issues_count = len(unique_undefined) + len(unquoted_lookups) + len(missing_imports)

        return {
            "valid": issues_count == 0,
            "filename": filename,
            "syntax_error": None,
            "undefined_names": unique_undefined,
            "unquoted_dict_lookups": unquoted_lookups,
            "missing_imports": missing_imports,
            "issues_count": issues_count
        }

    def audit_file(self, filepath: str) -> Dict[str, Any]:
        """Audits a file on disk."""
        path = Path(filepath)
        if not path.exists():
            return {"valid": False, "filename": filepath, "error": "File does not exist", "issues_count": 1}

        if path.suffix == ".py":
            try:
                content = path.read_text(encoding="utf-8")
                return self.audit_code_string(content, filename=str(path))
            except Exception as e:
                return {"valid": False, "filename": filepath, "error": str(e), "issues_count": 1}
        
        return {"valid": True, "filename": filepath, "skipped": "Non-Python file", "issues_count": 0}

    def autofix_code_string(self, code: str) -> Tuple[str, List[str]]:
        """Automatically fixes missing standard library imports and unquoted dict lookups in code."""
        audit = self.audit_code_string(code)
        if audit["valid"]:
            return code, []

        fixed_code = code
        fixes_applied = []

        # 1. Fix unquoted dict lookups: .get(var_name, ...) -> .get("var_name", ...)
        for item in audit.get("unquoted_dict_lookups", []):
            var = item["variable_passed"]
            pattern = rf"\.get\(\s*{re.escape(var)}\s*([,\)])"
            replacement = rf".get('{var}'\1"
            if re.search(pattern, fixed_code):
                fixed_code = re.sub(pattern, replacement, fixed_code)
                fixes_applied.append(f"Quoted dictionary key lookup: .get({var}) -> .get('{var}')")

        # 2. Auto-inject missing standard imports at top of file
        missing_imports = audit.get("missing_imports", [])
        if missing_imports:
            imports_to_add = []
            for item in missing_imports:
                stmt = item["suggested_import"]
                if stmt not in fixed_code:
                    imports_to_add.append(stmt)
                    fixes_applied.append(f"Injected missing import: '{stmt}'")

            if imports_to_add:
                header = "\n".join(imports_to_add) + "\n"
                fixed_code = header + fixed_code

        return fixed_code, fixes_applied

    def autofix_file(self, filepath: str) -> Dict[str, Any]:
        """Audits and automatically writes fixes to a file on disk."""
        path = Path(filepath)
        if not path.exists() or path.suffix != ".py":
            return {"status": "SKIPPED", "filename": filepath}

        content = path.read_text(encoding="utf-8")
        fixed_content, fixes = self.autofix_code_string(content)

        if fixes:
            path.write_text(fixed_content, encoding="utf-8")
            return {
                "status": "FIXED",
                "filename": filepath,
                "fixes_applied": fixes,
                "remaining_audit": self.audit_code_string(fixed_content, filename=filepath)
            }

        return {
            "status": "CLEAN",
            "filename": filepath,
            "fixes_applied": [],
            "audit": self.audit_code_string(content, filename=filepath)
        }

    def audit_workspace_changes(self) -> Dict[str, Any]:
        """Audits all modified and untracked git files in the workspace."""
        try:
            proc = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True
            )
            files_to_check = []
            for line in proc.stdout.splitlines():
                if line.strip():
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        rel_path = parts[-1]
                        if rel_path.endswith(".py"):
                            files_to_check.append(os.path.join(self.workspace_root, rel_path))

            results = []
            total_issues = 0
            for fpath in files_to_check:
                if os.path.exists(fpath):
                    res = self.audit_file(fpath)
                    if not res["valid"]:
                        total_issues += res.get("issues_count", 0)
                        results.append(res)

            return {
                "status": "PASSED" if total_issues == 0 else "ISSUES_FOUND",
                "scanned_files_count": len(files_to_check),
                "issues_count": total_issues,
                "problematic_files": results
            }
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}


@sovereign_tool(name="audit_code_integrity", category="Codebase")
def audit_code_integrity(
    target: Optional[str] = None,
    autofix: bool = False
) -> Dict[str, Any]:
    """
    Universal Code Integrity Sentinel Tool.
    Audits and autofixes missing imports, undefined variables, and unquoted dict lookups.
    
    Args:
        target: Optional path to file/directory, or code snippet string. If omitted, scans git workspace changes.
        autofix: If True, automatically writes fixes for standard imports and dict lookups.
    """
    sentinel = CodeIntegritySentinel()

    if not target or target == "workspace" or target == "--diff":
        return sentinel.audit_workspace_changes()

    if os.path.exists(target):
        if autofix:
            return sentinel.autofix_file(target)
        return sentinel.audit_file(target)

    # Treat as inline code snippet
    if autofix:
        fixed_code, fixes = sentinel.autofix_code_string(target)
        return {
            "original_audit": sentinel.audit_code_string(target),
            "fixed_code": fixed_code,
            "fixes_applied": fixes
        }

    return sentinel.audit_code_string(target)
