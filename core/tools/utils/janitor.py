import os
import subprocess
import re
from pathlib import Path

# --- CONFIGURATION ---
from tools.infrastructure.config import settings
PROJECT_ROOT = settings.PROJECT_ROOT
TOOLS_DIR = PROJECT_ROOT / "core" / "tools"

class SmartJanitor:
    def __init__(self, target_dir: Path):
        self.target_dir = target_dir
        self.ghosts = []

    def find_all_python_files(self):
        """Returns a list of all .py files in the target directory."""
        py_files = []
        for root, _, files in os.walk(self.target_dir):
            if "__pycache__" in root:
                continue
            for file in files:
                if file.endswith(".py"):
                    py_files.append(Path(root) / file)
        return py_files

    def extract_definitions(self, file_path: Path):
        """Extracts function and class names from a file."""
        with open(file_path, "r") as f:
            content = f.read()
        
        # Matches 'def function_name(' or 'class ClassName:'
        matches = re.findall(r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\(', content)
        matches += re.findall(r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)[:\(]', content)
        
        return set(matches)

    def is_used_anywhere_else(self, name: str, current_file: Path, all_files: list):
        """Checks if a name is referenced in any other file."""
        for file in all_files:
            if file == current_file:
                continue
            
            with open(file, "r") as f:
                content = f.read()
                if name in content:
                    return True
        return False

    def hunt_ghosts(self):
        print(f"🧹 Smart Janitor is entering the 'Ghost Hunt' phase...")
        all_files = self.find_all_python_files()
        print(f"  - Scanning {len(all_files)} files...")

        for file in all_files:
            definitions = self.extract_definitions(file)
            for name in definitions:
                # Skip common or internal names
                if name.startswith("__") or name in ["main", "run", "setup"]:
                    continue
                
                if not self.is_used_anywhere_else(name, file, all_files):
                    self.ghosts.append({"name": name, "file": file})

        print(f"✅ Hunt complete. Found {len(self.ghosts)} potential ghost functions/classes.")
        return self.ghosts

    def report(self):
        if not self.ghosts:
            print("✨ Your codebase is lean! No ghosts detected.")
            return

        print("\n👻 --- GHOST REPORT --- 👻")
        for ghost in self.ghosts:
            print(f"  - {ghost['name']} (Defined in: {ghost['file'].relative_to(PROJECT_ROOT)})")
        print("\n⚠️ WARNING: These functions are never called by other files.")

if __name__ == "__main__":
    janitor = SmartJanitor(TOOLS_DIR)
    janitor.hunt_ghosts()
    janitor.report()
