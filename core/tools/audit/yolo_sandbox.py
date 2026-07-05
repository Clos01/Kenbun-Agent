import os
import json
import shlex
import re
from pathlib import Path

# Commands that are ALWAYS blocked even in YOLO mode (nuclear options)
YOLO_BLOCKLIST = [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf /*",
    "mkfs",
    "dd if=/dev/zero",
    "dd if=/dev/random",
    ":(){ :|:& };:",    # fork bomb
    "chmod -R 777 /",
    "chown -R",
    "> /dev/sda",
    "shred /dev",
    "wipefs",
    "fdisk /dev/sd",
    "format c:",
]

def get_active_project_root():
    try:
        from core.tools.infrastructure.config import settings
        return settings.PROJECT_ROOT.resolve()
    except Exception:
        try:
            from core.tools.utils.path_utils import get_project_root
            return get_project_root().resolve()
        except Exception:
            return Path.cwd().resolve()

def is_yolo_safe(cmd: str) -> bool:
    """
    Returns False if the command matches any blocked structural pattern.
    Uses shlex parsing to inspect command parts securely and prevent blocklist bypasses.
    Fail-closed: returns False if parsing or safety checks fail.
    """
    cmd_lower = cmd.lower().strip()
    
    # 1. Strict Character Whitelist (Default Deny on metacharacters, braces, backslashes, etc.)
    if not re.match(r"^[a-zA-Z0-9_\-\.\/ \'\"\+\=\:]+$", cmd):
        return False

    # 2. Prevent Command Chaining, background execution, subshell metacharacters,
    # redirection, globbing, brace expansion, parentheses, and backslash obfuscation (Fail-closed structural block).
    forbidden_metachars = {";", "&", "|", "`", "$", "\n", "\r", ">", "<", "*", "?", "\\", "{", "}", "(", ")"}
    if any(char in cmd for char in forbidden_metachars):
        return False

    # 3. Parse command using shlex to analyze structure
    try:
        parts = shlex.split(cmd)
    except ValueError:
        # If shell parsing fails (e.g. due to unclosed quotes), fail-closed
        return False

    if not parts:
        return True

    # 4. Strictly block sudo execution in YOLO mode to prevent privilege escalation
    if "sudo" in cmd_lower or "sudo" in parts:
        return False

    executable = parts[0].lower()
    args = [arg.lower() for arg in parts[1:]]
    executable_base = Path(executable).name

    # 4. Nuclear Blocklist (Default Allow, but block catastrophic commands)
    NUCLEAR_EXECUTABLES = {"mkfs", "dd", "fdisk", "format", "reboot", "shutdown", "halt"}
    if executable_base in NUCLEAR_EXECUTABLES:
        return False
    if executable_base == "rm" and "-rf" in args and "/" in args:
        return False

    # 5. Check local project override registry (Learned from interactive YOLO prompts)
    try:
        allowlist_path = get_active_project_root() / "brain_health" / ".yolo_allowlist.json"
        if allowlist_path.exists():
            with open(allowlist_path, "r") as f:
                yolo_allowlist = set(json.load(f))
                if executable_base in yolo_allowlist:
                    return True
    except Exception:
        pass

    # 6. Strict Allowlist (Mandated by System 2 Security Court)
    ALLOWED_EXECUTABLES = {"git", "ls", "npm", "zip", "cd", "pwd", "whoami", "cat", "echo", "python", "pip", "mkdir", "cp", "mv"}
    if executable_base not in ALLOWED_EXECUTABLES:
        return False

    # 6. Strict Argument Injection Prevention (Default Deny on dangerous flags)
    if executable_base == "git":
        for arg in args:
            if "--upload-pack" in arg or "--exec-path" in arg or "--config" in arg or "!" in arg:
                return False

    if executable_base == "npm":
        for arg in args:
            # Block arbitrary npm script execution and installation
            if arg in ("run", "exec", "install", "i", "link", "run-script", "publish"):
                return False

    # Load active project root deterministically (Fail-closed)
    try:
        project_root = get_active_project_root()
    except Exception:
        return False

    if project_root.parent == project_root or str(project_root).lower().rstrip("/\\") in (
        "", "/", "c:", "d:", "c:\\", "d:\\", "/users", "/home", "/private", "/var", "/etc", "/tmp"
    ):
        return False

    def is_path_in_workspace(path_str: str) -> bool:
        try:
            target_path = Path(path_str).expanduser().resolve()
            # Enforce symlink check on components to prevent TOCTOU symlink swaps
            current = target_path
            while current != current.parent:
                if current.is_symlink():
                    return False
                current = current.parent
                
            if hasattr(target_path, "is_relative_to"):
                return target_path.is_relative_to(project_root)
            else:
                target_path.relative_to(project_root)
                return True
        except Exception:
            # Resolution failed or is outside -> Fail-closed
            return False

    # Check 1: Recursive/Forced deletion target checks (Fail-closed)
    if executable_base == "rm":
        has_recursive = any("-" in arg and "r" in arg for arg in args)
        has_no_preserve = any("--no-preserve-root" in arg for arg in args)
        
        if has_no_preserve:
            return False
            
        if has_recursive or any("rf" in arg or "fr" in arg for arg in args):
            # Target check
            targets = [arg for arg in args if not arg.startswith("-")]
            if not targets:
                return False
                
            for target in targets:
                if not is_path_in_workspace(target):
                    return False
                
                # Check for sensitive top-level folders explicitly
                sensitive_paths = {"/", "/*", "~", os.path.expanduser("~").lower(), "/etc", "/var", "/usr", "/bin", "/sbin", "/boot", "/lib", "/system"}
                clean_target = target.strip("\"'").rstrip("/")
                if clean_target in sensitive_paths:
                    return False
                    
                try:
                    resolved_target = Path(clean_target).expanduser().resolve()
                    if str(resolved_target) in sensitive_paths or str(resolved_target) in ("/", os.path.expanduser("~"), str(Path.home())):
                        return False
                except Exception:
                    return False

    # Check 2: Block recursive chmod/chown on sensitive root directories or outside workspace
    if executable_base in ("chmod", "chown"):
        has_recursive = any("-" in arg and "r" in arg for arg in args)
        if has_recursive:
            targets = [arg for arg in args if not arg.startswith("-")]
            if not targets:
                return False
            for target in targets:
                if not is_path_in_workspace(target):
                    return False

    # Fallback legacy check
    cmd_condensed = "".join(cmd_lower.split())
    for danger in YOLO_BLOCKLIST:
        danger_condensed = "".join(danger.split()).lower()
        if danger_condensed in cmd_condensed:
            return False

    return True


def is_command_destructive(cmd: str) -> tuple[bool, str]:
    """
    Checks if a command has potentially destructive or high-impact side effects.
    Returns (is_high_impact, reason_description).
    """
    cmd_lower = cmd.lower().strip()
    
    # 1. Superuser privileges
    if cmd_lower.startswith("sudo "):
        return True, "Runs with superuser (root) privileges"
        
    # 2. File / folder deletion
    if "rm " in cmd_lower and ("-r" in cmd_lower or "-f" in cmd_lower or "rf" in cmd_lower):
        return True, "Deletes files or directories recursively/permanently"
        
    # 3. System prune / clean
    if "prune" in cmd_lower:
        return True, "Wipes or cleans Docker volumes/cache permanently"
        
    # 4. Uninstall/purge commands
    if "uninstall" in cmd_lower or "purge" in cmd_lower or "apt-get remove" in cmd_lower:
        return True, "Uninstalls packages or software libraries"
        
    # 5. Dangerous disk commands
    if any(k in cmd_lower for k in ["dd ", "mkfs", "fdisk", "wipefs", "shred"]):
        return True, "Overwrites or modifies physical disk partitions"
        
    # 6. Fork bomb or kernel panic triggers
    if ":(){ :|:& };:" in cmd_lower or "reboot" in cmd_lower or "shutdown" in cmd_lower:
        return True, "Reboots or shuts down the system"
        
    return False, ""
