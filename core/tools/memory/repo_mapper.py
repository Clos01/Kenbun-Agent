"""
Repo Mapper — Generates skeleton maps of codebases.

Instead of sending 100 raw files to the AI, this creates a compact
structural summary showing only classes, functions, and signatures.
This is the same "Repo Map" technique used by Cursor and SWE-agent.

Uses Python's built-in `ast` module for .py files (zero dependencies).
Uses regex-based extraction for .js/.ts/.tsx files.
"""
import ast
import os
import re
from pathlib import Path


# --- CONFIGURATION ---
DEFAULT_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}

IGNORE_DIRS = {
    "node_modules", "__pycache__", ".git", ".next", ".venv",
    "venv", "env", "dist", "build", ".cache", "coverage",
    ".turbo", ".docker", ".eggs", "*.egg-info",
}

IGNORE_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    ".DS_Store", "*.pyc", "*.map",
}

MAX_FILE_SIZE = 500_000  # Skip files > 500KB (probably generated)


# --- 1. PYTHON SKELETON EXTRACTOR (using built-in `ast`) ---
def _extract_python_skeleton(file_path: Path) -> list:
    """Parse a Python file and extract class/function signatures."""
    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return [f"  ⚠️ (parse error)"]

    items = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            items.append(f"  class {node.name}:")
            for item in ast.iter_child_nodes(node):
                if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                    sig = _format_python_func(item)
                    items.append(f"    {sig}")

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = _format_python_func(node)
            items.append(f"  {sig}")

        elif isinstance(node, ast.ImportFrom):
            if node.module and not node.module.startswith("__"):
                names = ", ".join(alias.name for alias in node.names[:5])
                if len(node.names) > 5:
                    names += ", ..."
                items.append(f"  from {node.module} import {names}")

    return items


def _format_python_func(node) -> str:
    """Format a function/method signature."""
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    args = []
    for arg in node.args.args:
        name = arg.arg
        if name == "self" or name == "cls":
            continue
        annotation = ""
        if arg.annotation:
            try:
                annotation = f": {ast.unparse(arg.annotation)}"
            except Exception:
                pass
        args.append(f"{name}{annotation}")

    returns = ""
    if node.returns:
        try:
            returns = f" -> {ast.unparse(node.returns)}"
        except Exception:
            pass

    return f"{prefix} {node.name}({', '.join(args)}){returns}"


# --- 2. JS/TS SKELETON EXTRACTOR (regex-based) ---
JS_PATTERNS = [
    # export function name(args) or export async function name(args)
    re.compile(r"export\s+(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)"),
    # export const name = (args) =>  or  export const name = function
    re.compile(r"export\s+(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*(?:=>|:)"),
    # export default function name(args)
    re.compile(r"export\s+default\s+(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)"),
    # class Name
    re.compile(r"(?:export\s+)?class\s+(\w+)"),
    # interface Name
    re.compile(r"(?:export\s+)?interface\s+(\w+)"),
    # type Name =
    re.compile(r"(?:export\s+)?type\s+(\w+)\s*="),
    # const Name: React.FC or const Name = () =>  (React components — PascalCase)
    re.compile(r"(?:export\s+)?(?:const|function)\s+([A-Z]\w+)"),
]


def _extract_js_skeleton(file_path: Path) -> list:
    """Extract function/class/type signatures from JS/TS files."""
    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return [f"  ⚠️ (read error)"]

    items = []
    seen = set()

    for pattern in JS_PATTERNS:
        for match in pattern.finditer(source):
            groups = match.groups()
            name = groups[0]
            if name in seen:
                continue
            seen.add(name)

            full_match = match.group(0).strip()
            # Clean up for display
            if len(full_match) > 100:
                full_match = full_match[:100] + "..."
            items.append(f"  {full_match}")

    return items if items else ["  (no exports found)"]


# --- 3. MAIN SCANNER ---
def scan_repo(
    project_path: str,
    extensions: str = ".py,.ts,.tsx,.js,.jsx",
) -> str:
    """
    Generate a skeleton map of a project directory.

    Walks the project tree and extracts class names, function signatures,
    and type definitions — without the implementation code. This creates
    a compact "Repo Map" that fits large codebases into a single prompt.

    Args:
        project_path: Absolute path to the project root
        extensions: Comma-separated file extensions to scan

    Returns:
        A formatted skeleton map of the project structure.
    """
    root = Path(project_path)
    if not root.exists():
        return f"❌ Path not found: {project_path}"
    if not root.is_dir():
        return f"❌ Not a directory: {project_path}"

    ext_set = {e.strip() if e.strip().startswith(".") else f".{e.strip()}"
               for e in extensions.split(",")}

    output_lines = [f"# 🗺️ Repo Map: {root.name}\n"]
    total_files = 0
    total_items = 0
    current_dir = None

    # Walk the directory tree
    for dirpath, dirnames, filenames in os.walk(root):
        # Filter out ignored directories
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        dirnames.sort()

        rel_dir = Path(dirpath).relative_to(root)

        for filename in sorted(filenames):
            filepath = Path(dirpath) / filename
            suffix = filepath.suffix

            if suffix not in ext_set:
                continue
            if filepath.stat().st_size > MAX_FILE_SIZE:
                continue

            # Print directory header if changed
            dir_str = str(rel_dir) if str(rel_dir) != "." else "(root)"
            if dir_str != current_dir:
                current_dir = dir_str
                output_lines.append(f"\n📁 {dir_str}/")

            # Count lines
            try:
                line_count = len(filepath.read_text(errors="ignore").splitlines())
            except Exception:
                line_count = "?"

            output_lines.append(f"  📄 {filename} ({line_count} lines)")
            total_files += 1

            # Extract skeleton based on language
            if suffix == ".py":
                items = _extract_python_skeleton(filepath)
            elif suffix in (".ts", ".tsx", ".js", ".jsx"):
                items = _extract_js_skeleton(filepath)
            else:
                items = []

            output_lines.extend(items)
            total_items += len(items)

    # Summary footer
    output_lines.insert(1, f"Files: {total_files} | Symbols: {total_items}\n")

    return "\n".join(output_lines)
