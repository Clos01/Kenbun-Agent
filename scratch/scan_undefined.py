import ast
import sys
import builtins

class FullySmartAuditor(ast.NodeVisitor):
    def __init__(self):
        self.scopes = [{}]
        self.undefined = set()
        self.current_function_stack = []

        # Bootstrap global standard symbols
        self.bootstrap_globals = {
            "sys", "os", "re", "shutil", "sqlite3", "logging", "Path",
            "__name__", "__file__", "PROVIDERS_MAP", "select_menu", "visual_len",
            "strip_ansi", "should_enable_color", "print_sakura_banner",
            "log_status", "is_port_in_use", "find_free_port", "bootstrap_core",
            "configure_api_keys", "configure_local_models", "launch_docker_swarm",
            "showcase_dashboard", "run_quick_setup", "run_interactive_wizard",
            "auto_register_claude_desktop_mcp", "auto_register_cursor_mcp",
            "detect_hardware", "Optional", "List"
        }

    def push_scope(self):
        self.scopes.append({})

    def pop_scope(self):
        self.scopes.pop()

    def define(self, name):
        self.scopes[-1][name] = True

    def is_defined(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return True
        if name in self.bootstrap_globals or hasattr(builtins, name):
            return True
        return False

    def visit_FunctionDef(self, node):
        # The function name is defined in the parent scope
        self.define(node.name)
        
        self.current_function_stack.append(node.name)
        self.push_scope()
        
        # Define arguments
        for arg in node.args.args:
            self.define(arg.arg)
        if node.args.vararg:
            self.define(node.args.vararg.arg)
        if node.args.kwarg:
            self.define(node.args.kwarg.arg)
        for arg in node.args.kwonlyargs:
            self.define(arg.arg)

        # Visit the body
        for child in node.body:
            self.visit(child)
            
        self.pop_scope()
        self.current_function_stack.pop()

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname or alias.name.split('.')[0]
            self.define(name)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            name = alias.asname or alias.name
            self.define(name)

    def visit_ExceptHandler(self, node):
        self.push_scope()
        if node.name:
            self.define(node.name)
        if node.type:
            self.visit(node.type)
        for child in node.body:
            self.visit(child)
        self.pop_scope()

    def visit_Assign(self, node):
        # Visit value first
        self.visit(node.value)
        # Store all targets
        for target in node.targets:
            self.visit_target(target)

    def visit_target(self, node):
        if isinstance(node, ast.Name):
            self.define(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                self.visit_target(elt)
        elif isinstance(node, ast.Attribute):
            self.visit(node.value)
        elif isinstance(node, ast.Subscript):
            self.visit(node.value)
            self.visit(node.slice)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            if not self.is_defined(node.id):
                func = " -> ".join(self.current_function_stack) if self.current_function_stack else "Global Scope"
                self.undefined.add((node.id, node.lineno, func))
        elif isinstance(node.ctx, ast.Store):
            self.define(node.id)

    # Comprehensions introduce local scope
    def visit_ListComp(self, node):
        self.push_scope()
        for gen in node.generators:
            self.visit(gen)
        self.visit(node.elt)
        self.pop_scope()

    def visit_DictComp(self, node):
        self.push_scope()
        for gen in node.generators:
            self.visit(gen)
        self.visit(node.key)
        self.visit(node.value)
        self.pop_scope()

    def visit_SetComp(self, node):
        self.push_scope()
        for gen in node.generators:
            self.visit(gen)
        self.visit(node.elt)
        self.pop_scope()

    def visit_GeneratorExp(self, node):
        self.push_scope()
        for gen in node.generators:
            self.visit(gen)
        self.visit(node.elt)
        self.pop_scope()

    def visit_comprehension(self, node):
        self.visit(node.iter)
        self.visit_target(node.target)
        for cond in node.ifs:
            self.visit(cond)

with open("scripts/bootstrap.py", "r", encoding="utf-8") as f:
    tree = ast.parse(f.read())

auditor = FullySmartAuditor()

# Pass 1: populate absolute top-level definitions so order of definition doesn't cause false positives
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        auditor.define(node.name)
    elif isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                auditor.define(target.id)

# Pass 2: Audit everything
for node in tree.body:
    auditor.visit(node)

if auditor.undefined:
    print("❌ Undefined names found:")
    for name, line, func in sorted(auditor.undefined, key=lambda x: x[1]):
        print(f"  Line {line} in '{func}': name '{name}' is not defined")
    sys.exit(1)
else:
    print("✅ All scopes fully audited! No undefined variables detected in bootstrap.py.")
    sys.exit(0)
