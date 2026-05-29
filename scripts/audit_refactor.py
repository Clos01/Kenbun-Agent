"""
🏛️ Kenbun Branding Audit & Refinement Engine (System 6)
Programmatically sweeps the standalone kenbun-agent directory,
finds all legacy framework terms, and converts them to standard Kenbun branding.
"""

import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("audit_refactor")

# Excluded folders to protect system metadata
EXCLUDE_FOLDERS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".DS_Store",
}

# Scan-safe text extensions
TEXT_EXTENSIONS = {
    ".py", ".md", ".json", ".txt", ".yml", ".yaml", 
    ".sh", ".example", ".css", ".toml", ".tsx", ".ts",
    "Dockerfile", "Makefile", "Modefile"
}

# Branding replacement registry
REPLACEMENT_MAP = [
    # Legacy branding replacements
    ("antigravity", "kenbun"),
    ("Antigravity", "Kenbun"),
    ("ANTIGRAVITY", "KENBUN"),
    
    # Legacy instruction file naming replacements
    ("cloaude.md", "kenbun.md"),
    ("CLOAUDE.md", "KENBUN.md"),
    ("claude.md", "kenbun.md"),
    ("CLAUDE.md", "KENBUN.md"),
    ("README_HERMES.md", "KENBUN.md"),
    ("readme_hermes.md", "kenbun.md"),
]

def scan_and_refactor():
    logger.info("🛡️  Initiating Kenbun Sovereign Audit Sweep...")
    
    script_dir = Path(__file__).resolve().parent
    workspace_root = script_dir.parent
    logger.info(f"📂 Workspace Directory Target: {workspace_root.resolve()}")
    
    if not workspace_root.exists():
        logger.error("❌ Target workspace does not exist!")
        sys.exit(1)
        
    modified_files = 0
    total_replacements = 0

    for root, dirs, files in os.walk(workspace_root):
        root_path = Path(root)
        
        # In-place directory exclusion
        dirs[:] = [d for d in dirs if d not in EXCLUDE_FOLDERS]
        
        for file in files:
            file_path = root_path / file
            
            # Skip this audit script itself
            if file_path == Path(__file__).resolve():
                continue
                
            # Filter text extensions
            if file_path.suffix.lower() not in TEXT_EXTENSIONS and file_path.name not in TEXT_EXTENSIONS:
                continue
                
            try:
                # Read content
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                
                # Check and perform substitutions
                new_content = content
                file_replacements = 0
                
                for target, replacement in REPLACEMENT_MAP:
                    count = new_content.count(target)
                    if count > 0:
                        new_content = new_content.replace(target, replacement)
                        file_replacements += count
                        
                # Atomic rewrite if changes detected
                if file_replacements > 0:
                    logger.info(f"📝 Refactoring: {file_path.relative_to(workspace_root)} ({file_replacements} substitutions)")
                    
                    temp_path = file_path.with_suffix(file_path.suffix + ".refactor_tmp")
                    with open(temp_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    
                    os.replace(temp_path, file_path)
                    modified_files += 1
                    total_replacements += file_replacements
                    
            except Exception as e:
                logger.warning(f"⚠️ Could not audit/refactor file {file_path}: {e}")

    logger.info(f"✅ Audit Sweep Complete: Modified {modified_files} files with {total_replacements} total branding substitutions.")

if __name__ == "__main__":
    scan_and_refactor()
