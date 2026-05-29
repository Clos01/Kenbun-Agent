import ast
import inspect
from pathlib import Path
from typing import List, Dict, Any, Tuple

class SovereignBreach(Exception):
    """Custom exception for architectural violations."""
    pass

class ASTAuditor(ast.NodeVisitor):
    """
    System 5.1: The AST Auditor.
    Scans code for 'Illegal Subtrees' that indicate technical debt or ungrounded logic.
    """
    def __init__(self, file_content: str = None):
        self.breaches = []
        self.file_content = file_content.split('\n') if file_content else []

    def visit_Call(self, node: ast.Call):
        # 1. Detect sys.path mutations
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Attribute) and node.func.value.attr == 'path':
                if node.func.attr in ['append', 'insert']:
                    self._add_breach(node, "ILLEGAL_SYS_PATH_MUTATION: Use absolute tools.* imports instead.")
            
            # 2. Detect os.getenv (should use settings)
            if isinstance(node.func.value, ast.Name) and node.func.value.id == 'os' and node.func.attr == 'getenv':
                self._add_breach(node, "ILLEGAL_ENV_LOOKUP: Use tools.infrastructure.config.settings instead.")

        # 3. Detect eval/exec
        if isinstance(node.func, ast.Name) and node.func.id in ['eval', 'exec']:
            self._add_breach(node, f"FORBIDDEN_DYNAMIC_LOGIC: {node.func.id} is banned in Sovereign blocks.")

        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        # 4. Detect Path(__file__) or __file__ usage
        if node.attr == '__file__':
            self._add_breach(node, "BRITTLE_PATH_RESOLUTION: Avoid __file__. Use settings.PROJECT_ROOT.")
        
        self.generic_visit(node)

    def _add_breach(self, node: ast.AST, message: str):
        line = getattr(node, 'lineno', 0)
        col = getattr(node, 'col_offset', 0)
        snippet = self.file_content[line-1].strip() if 0 < line <= len(self.file_content) else "N/A"
        self.breaches.append({
            "line": line,
            "col": col,
            "message": message,
            "snippet": snippet
        })

def audit_code(code: str) -> Tuple[bool, List[Dict[str, Any]]]:
    """Runs a full structural audit on a string of code."""
    try:
        tree = ast.parse(code)
        auditor = ASTAuditor(code)
        auditor.visit(tree)
        return len(auditor.breaches) == 0, auditor.breaches
    except SyntaxError as e:
        return False, [{"line": e.lineno, "message": f"SYNTAX_ERROR: {e.msg}"}]

def audit_function(func):
    """Audits a live function object."""
    source = inspect.getsource(func)
    return audit_code(source)

if __name__ == "__main__":
    # Test Case
    poisoned_code = """
import sys
import os
from pathlib import Path

def setup():
    token = os.getenv("GITHUB_TOKEN")
    return token
    """
    is_clean, breaches = audit_code(poisoned_code)
    print(f"Clean: {is_clean}")
    for b in breaches:
        print(f"  - [{b['line']}] {b['message']} | Snippet: {b['snippet']}")
