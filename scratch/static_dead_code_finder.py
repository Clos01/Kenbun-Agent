import os
import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class DeadCodeFinder:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.definitions = {}  # name -> (file_path, type)
        self.references = set()  # set of names referenced
        self.local_unused = []  # list of (file_path, func_name, var_name, line_no)

    def scan_files(self):
        py_files = []
        for root, dirs, files in os.walk(self.root_dir):
            # Exclude directories
            dirs[:] = [d for d in dirs if d not in [
                "node_modules", ".venv", "venv", ".pytest_cache", ".git", ".agents", "brain_health", "scratch"
            ]]
            for file in files:
                if file.endswith(".py"):
                    py_files.append(Path(root) / file)
        return py_files

    def parse_file(self, file_path: Path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            tree = ast.parse(content)
        except Exception as e:
            print(f"⚠️ Failed to parse {file_path.relative_to(self.root_dir)}: {e}")
            return

        relative_path = file_path.relative_to(self.root_dir)

        # Walk AST to find definitions and references
        for node in ast.walk(tree):
            # 1. Definitions
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                name = node.name
                # Skip double-underscores, tests, and setup methods
                if not (name.startswith("__") or name.startswith("test_") or name in ["main", "run", "setup", "setUp", "tearDown"]):
                    self.definitions[name] = (relative_path, "function")
                
                # Check for unused local variables inside functions
                self.check_unused_locals(node, relative_path)

            elif isinstance(node, ast.ClassDef):
                name = node.name
                if not (name.startswith("__") or name.startswith("Test")):
                    self.definitions[name] = (relative_path, "class")

            # 2. References (Name nodes and Attribute nodes)
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    self.references.add(node.id)
            
            elif isinstance(node, ast.Attribute):
                self.references.add(node.attr)

    def check_unused_locals(self, func_node, relative_path):
        """Finds variables defined in a function but never loaded/referenced inside it."""
        defined_vars = {} # name -> line_no
        loaded_vars = set()

        for node in ast.walk(func_node):
            if isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Store):
                    defined_vars[node.id] = node.lineno
                elif isinstance(node.ctx, ast.Load):
                    loaded_vars.add(node.id)
            elif isinstance(node, ast.arg):
                defined_vars[node.arg] = node.lineno

        # Any defined var that is never loaded is unused (exclude standard parameters like self)
        for var_name, line_no in defined_vars.items():
            if var_name not in loaded_vars and var_name not in ["self", "args", "kwargs", "_"]:
                if not var_name.startswith("_"):
                    self.local_unused.append((relative_path, func_node.name, var_name, line_no))

    def run(self):
        py_files = self.scan_files()
        print(f"🔍 Scanning {len(py_files)} Python files in {self.root_dir}...")
        for file in py_files:
            self.parse_file(file)

        # Find dead code (definitions with 0 references outside their own file)
        dead_definitions = {}
        for name, (path, item_type) in self.definitions.items():
            if name not in self.references:
                dead_definitions[name] = (path, item_type)

        return dead_definitions, self.local_unused

if __name__ == "__main__":
    finder = DeadCodeFinder(PROJECT_ROOT)
    dead_defs, unused_locals = finder.run()

    print("\n👻 --- DEAD CODE REPORT (FUNCTIONS & CLASSES) --- 👻")
    if not dead_defs:
        print("✨ No unused functions or classes found.")
    else:
        for name, (path, item_type) in sorted(dead_defs.items(), key=lambda x: str(x[1][0])):
            print(f"  - [{item_type.upper()}] {name} (Defined in: {path})")

    print("\n📦 --- UNUSED VARIABLES / ARGUMENTS REPORT --- 📦")
    if not unused_locals:
        print("✨ No unused local variables found.")
    else:
        # Group by file
        grouped = {}
        for path, func, var, line in unused_locals:
            grouped.setdefault(path, []).append((func, var, line))

        for path in sorted(grouped.keys()):
            print(f"  📄 {path}:")
            for func, var, line in grouped[path]:
                print(f"    - Variable '{var}' in function '{func}' on line {line} is never referenced.")
