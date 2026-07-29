import ast
import importlib
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("harvester")

class ToolDecoratorVisitor(ast.NodeVisitor):
    """AST visitor to detect `@sovereign_tool` usage inside python source code files."""
    
    def __init__(self):
        self.has_sovereign_tool = False

    def visit_Decorator(self, node: ast.AST):
        if isinstance(node, ast.Call):
            func = node.func
        else:
            func = node
            
        if isinstance(func, ast.Name) and func.id == "sovereign_tool":
            self.has_sovereign_tool = True
        elif isinstance(func, ast.Attribute) and func.attr == "sovereign_tool":
            self.has_sovereign_tool = True
            
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        for dec in node.decorator_list:
            self.visit_Decorator(dec)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        for dec in node.decorator_list:
            self.visit_Decorator(dec)
        self.generic_visit(node)

def detect_sovereign_tools_in_file(file_path: Path) -> bool:
    """Read a python file and parse its AST to detect if it contains dynamic sovereign tools."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
        visitor = ToolDecoratorVisitor()
        visitor.visit(tree)
        return visitor.has_sovereign_tool
    except Exception as e:
        logger.debug(f"AST parse skipped for {file_path}: {e}")
        return False

def harvest_and_register_tools(tools_dir: Optional[Path] = None) -> List[str]:
    """
    Scans the core tools directory, dynamically detects sovereign tools via AST, and registers them.
    
    Returns:
        List of imported module strings.
    """
    if tools_dir is None:
        tools_dir = Path(__file__).resolve().parent

    logger.info(f"🔍 System 4 Harvester: Initiating dynamic sweep of {tools_dir}")
    
    imported_modules = []
    
    # 2. Walk directories safely
    for path in sorted(tools_dir.rglob("*.py")):
        if path.name in {"__init__.py", "registry.py", "harvester.py"}:
            continue
            
        if detect_sovereign_tools_in_file(path):
            try:
                # Compute relative module name
                relative_parts = list(path.relative_to(tools_dir).parts)
                relative_parts[-1] = path.stem # strip .py suffix
                mod_name = "tools." + ".".join(relative_parts)
                
                # Import module dynamically to trigger decoration & registration
                importlib.import_module(mod_name)
                imported_modules.append(mod_name)
                logger.info(f"✅ Harvester: Dynamically registered tools from module: {mod_name}")
            except BaseException as e:
                # BaseException, not Exception: a module that calls sys.exit() at
                # import time raises SystemExit, which is NOT an Exception and
                # would otherwise propagate out of the sweep and kill the host
                # process. native_ears.py does exactly that when the native macOS
                # Speech libs are absent; it has no @sovereign_tool so it is not
                # swept today, but the harvester must not be one refactor away
                # from taking down the MCP server on startup.
                logger.error(
                    f"❌ Harvester: Failed to dynamically import {path}: "
                    f"{type(e).__name__}: {e}"
                )

    return imported_modules

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    modules = harvest_and_register_tools()
    print(f"Sweep complete. Harvested modules: {modules}")
