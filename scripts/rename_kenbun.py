import os
import re

ROOT_DIR = "/Users/carlosrivas/Dev/Kenbun"

EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", 
    ".pytest_cache", ".ruff_cache", ".next", "kenbun_agent.egg-info", 
    ".claude", ".benchmarks", "_archive_orphan_weights"
}

def replace_text_in_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Skip binary files
        return

    # Specific override
    content = content.replace("nousresearch/hermes-agent", "Clos01/Kenbun-Agent")
    content = content.replace("nousresearch/kenbun-agent", "Clos01/Kenbun-Agent")

    # General replacements
    content = content.replace("hermes", "kenbun")
    content = content.replace("Hermes", "Kenbun")
    content = content.replace("HERMES", "KENBUN")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def rename_file_or_dir(name):
    new_name = name.replace("hermes", "kenbun")
    new_name = new_name.replace("Hermes", "Kenbun")
    new_name = new_name.replace("HERMES", "KENBUN")
    return new_name

def main():
    # First pass: replace content in files
    for root, dirs, files in os.walk(ROOT_DIR):
        # Exclude directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            # Skip python bytecode
            if file.endswith('.pyc') or file.endswith('.pyo'):
                continue
            filepath = os.path.join(root, file)
            # Skip this script
            if file == "rename_hermes.py":
                continue
            replace_text_in_file(filepath)

    # Second pass: rename files and directories bottom-up
    for root, dirs, files in os.walk(ROOT_DIR, topdown=False):
        # We don't filter dirs[:] here because we're bottom-up, but we should skip processing excluded paths
        if any(ex in root.split(os.sep) for ex in EXCLUDE_DIRS):
            continue

        for file in files:
            new_name = rename_file_or_dir(file)
            if new_name != file:
                old_path = os.path.join(root, file)
                new_path = os.path.join(root, new_name)
                print(f"Renaming file: {old_path} -> {new_path}")
                os.rename(old_path, new_path)

        for d in dirs:
            new_name = rename_file_or_dir(d)
            if new_name != d:
                old_path = os.path.join(root, d)
                new_path = os.path.join(root, new_name)
                print(f"Renaming directory: {old_path} -> {new_path}")
                os.rename(old_path, new_path)

if __name__ == "__main__":
    main()
