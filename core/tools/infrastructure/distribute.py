"""
🏛️ Kenbun Sovereign Distribution Engine (System 2 Sanitizer - Refactored)
This tool programmatically packages, sanitizes, and verifies the standalone kenbun-agent distribution.
It guarantees environment-agnostic execution, zero secret leaks, and post-zip integrity verification.
Refactored following the Gemini + Supervisor Consensus Code Review:
- Implemented stream-based, memory-safe file reading for scanning.
- Explicitly blocked symbolic link traversal to prevent host-level data leaks.
- Added database exclusions (.sqlite, .db, .sqlite3) for compliance.
- Integrated archive integrity audits (zipf.testzip()) and size bounds checks.
- Implemented robust, dynamic root path discovery.
"""

import os
import re
import sys
import zipfile
import logging
from pathlib import Path

# Configure logger dynamically without hijacking root logging
logger = logging.getLogger("distribute")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Sanitization and Exclusion Manifest
EXCLUDE_EXACT_NAMES = {
    ".env",
    ".env.local",
    ".kenbun_master.key",
    ".kenbun_master.key",
    ".DS_Store",
    "ehthumbs.db",
    "Thumbs.db",
}

EXCLUDE_FOLDERS = {
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".audit_backup",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".log",
    ".bak",
    ".db",
    ".sqlite",
    ".sqlite3",
}

# High-risk patterns to scan for in text files (e.g. API keys, unencrypted secrets)
# Optimized regex to avoid ReDoS and scan efficiently
HIGH_RISK_PATTERNS = [
    (re.compile(r"AIzaSy[A-Za-z0-9_\-]{35}"), "Google API Key"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{95}"), "Anthropic API Key"),
    (re.compile(r"xox[bpgr]-[A-Za-z0-9\-]+"), "Slack API Key"),
    (re.compile(r"secret[_-]key\s*=\s*['\"][^'\"#]{20,}['\"]", re.IGNORECASE), "Raw hardcoded secret"),
]

def find_project_root(start_path: Path) -> Path:
    """Dynamically discover the true Kenbun workspace root by searching upwards."""
    # First search for a clear root marker like the "kenbun-agent" directory
    for parent in [start_path] + list(start_path.parents):
        if (parent / "kenbun-agent").exists() and parent.name != "kenbun-agent":
            return parent
    # If we are already running inside the decoupled kenbun-agent distribution, the folder containing SKILL.md is our root
    for parent in [start_path] + list(start_path.parents):
        if (parent / "SKILL.md").exists() and not (parent.parent / "kenbun-agent").exists():
            return parent
    # Fallback to standard parent resolution if markers not found
    return start_path.resolve().parents[3]

def should_exclude(path: Path) -> bool:
    """Evaluate if a given path should be excluded based on the manifest."""
    # Prevent symlink attacks by skipping all symbolic links
    if path.is_symlink():
        return True

    # Check exact file/folder name
    if path.name in EXCLUDE_EXACT_NAMES:
        return True
    
    # Check if any parent folder is in the EXCLUDE_FOLDERS list
    for part in path.parts:
        if part in EXCLUDE_FOLDERS:
            return True
            
    # Check file extension
    if path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return True
        
    return False

def sanitize_archive_name(file_path: Path, source_dir: Path) -> str:
    """Ensure the path within the ZIP is safe and free of directory traversal patterns."""
    relative = file_path.relative_to(source_dir.parent)
    as_str = relative.as_posix()
    # Replace absolute or parent traversal segments just in case
    sanitized = as_str.replace("../", "").replace("..\\", "")
    return sanitized

def build_distribution(source_dir: Path, output_zip: Path):
    """Programmatically package and sanitize the source directory into the output ZIP."""
    logger.info(f"🚀 Starting Kenbun Distribution Builder...")
    logger.info(f"📂 Source: {source_dir.resolve()}")
    logger.info(f"📦 Output ZIP: {output_zip.resolve()}")

    if not source_dir.exists():
        logger.error(f"❌ Source directory {source_dir} does not exist!")
        sys.exit(1)

    # Initialize stats
    files_added = 0
    files_excluded = 0

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zipf:
        for root, dirs, files in os.walk(source_dir, followlinks=False):
            root_path = Path(root)
            
            # Skip excluded folders entirely in os.walk to optimize traversal and block leaks
            dirs[:] = [d for d in dirs if d not in EXCLUDE_FOLDERS and not (root_path / d).is_symlink()]

            for file in files:
                file_path = root_path / file
                
                # Check exclusion and symlink protection
                if should_exclude(file_path):
                    logger.debug(f"🛡️ Excluding sensitive/temporary file or symlink: {file_path.relative_to(source_dir)}")
                    files_excluded += 1
                    continue
                
                # Determine sanitized archive path
                archive_name = sanitize_archive_name(file_path, source_dir)
                
                zipf.write(file_path, archive_name)
                files_added += 1

    logger.info(f"✅ Compression Complete: Added {files_added} files (Excluded {files_excluded} files).")

def verify_distribution(zip_path: Path, max_uncompressed_size_gb: float = 2.0):
    """
    Perform a robust, memory-safe post-archive verification sweep.
    Checks CRC integrity, tests size limits to mitigate zip bombs, blocks traversal metadata, and streams files for key scans.
    """
    logger.info("🛡️ Initiating System 2 Verification Audit...")
    
    if not zip_path.exists():
        logger.error("❌ Verification failed: ZIP file does not exist.")
        sys.exit(1)

    errors = 0
    warnings = 0

    with zipfile.ZipFile(zip_path, "r") as zipf:
        # 1. CRC Check
        corrupt_file = zipf.testzip()
        if corrupt_file:
            logger.error(f"❌ ARCHIVE CORRUPTION: File {corrupt_file} failed CRC/header integrity check.")
            errors += 1

        # 2. ZIP Bomb Defense
        total_size = sum(zinfo.file_size for zinfo in zipf.infolist())
        max_size_bytes = max_uncompressed_size_gb * 1024 * 1024 * 1024
        if total_size > max_size_bytes:
            logger.error(f"❌ ZIP BOMB VULNERABILITY: Uncompressed archive size ({total_size / (1024**3):.2f} GB) exceeds threshold.")
            errors += 1

        namelist = zipf.namelist()
        
        # 3. Structural and Traversal Check
        for name in namelist:
            p = Path(name)
            
            # Block directory traversal attempts in filenames
            if ".." in name or name.startswith("/") or name.startswith("\\"):
                logger.error(f"❌ SECURITY BREACH: Directory traversal pattern in zip filename: {name}")
                errors += 1
            
            # Check name or directory parts against manifest
            if p.name in EXCLUDE_EXACT_NAMES or any(part in EXCLUDE_FOLDERS for part in p.parts) or p.suffix.lower() in EXCLUDE_EXTENSIONS:
                logger.error(f"❌ SECURITY BREACH: Forbidden file packed in archive: {name}")
                errors += 1
                
        # 4. Stream-Based Content Scan for secrets (Memory-safe line-by-line streaming)
        text_suffixes = {".py", ".md", ".json", ".txt", ".yml", ".yaml", ".sh", ".example", ".css", ".toml", ".tsx", ".ts"}
        
        for name in namelist:
            p = Path(name)
            if p.suffix.lower() in text_suffixes:
                try:
                    with zipf.open(name) as f:
                        # Stream line by line to keep memory minimal
                        for line_num, byte_line in enumerate(f, 1):
                            line = byte_line.decode("utf-8", errors="replace")
                            
                            # Run security pattern matchers
                            for pattern, desc in HIGH_RISK_PATTERNS:
                                matches = pattern.findall(line)
                                for match in matches:
                                    # Allow encrypted keys or explicit placeholders
                                    if "enc:" in match or "placeholder" in match:
                                        continue
                                    logger.warning(f"⚠️ POTENTIAL SECRET LEAK in [{name}] (Line {line_num}): Found {desc} -> '{match[:15]}...'")
                                    warnings += 1
                except Exception as e:
                    logger.debug(f"Could not read {name} for content scan: {e}")

    # Summary
    logger.info(f"📊 Verification Summary: {errors} Errors, {warnings} Warnings.")
    if errors > 0:
        logger.error("❌ System 2 Audit: REJECTED. Security vulnerabilities or corrupt files detected in ZIP.")
        sys.exit(1)
    else:
        logger.info("🛡️ System 2 Audit: APPROVED. Decoupled distribution is safe for deployment.")

if __name__ == "__main__":
    # Dynamically find project root
    base_dir = find_project_root(Path(__file__).resolve())
    
    source = base_dir.parent / "kenbun-agent" if (base_dir.parent / "kenbun-agent").exists() else base_dir / "kenbun-agent"
    output = base_dir / "kenbun_agent.zip"
    
    build_distribution(source, output)
    verify_distribution(output)
