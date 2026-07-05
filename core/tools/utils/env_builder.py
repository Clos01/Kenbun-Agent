import sys
from pathlib import Path

# Need C_Y and C_R from console_ui
try:
    from core.tools.utils.console_ui import C_Y, C_R
except ImportError:
    C_Y = "\033[93m"
    C_R = "\033[0m"

def decrypt_value(val):
    """Decrypts values that are encrypted with 'enc:' prefix using the repository master key."""
    if not val.startswith("enc:"):
        return val
    try:
        from cryptography.fernet import Fernet
        # Resolve key file path dynamically
        possible_keys = [
            Path.cwd() / ".kenbun_master.key",
            Path.cwd() / "core" / ".kenbun_master.key",
            Path(__file__).parent.parent.parent / ".kenbun_master.key",
            Path(__file__).parent.parent.parent / "core" / ".kenbun_master.key"
        ]
        key = None
        for kp in possible_keys:
            if kp.exists():
                with open(kp, "rb") as f:
                    key = f.read().strip()
                break
        
        if key:
            f = Fernet(key)
            # Decrypt value (strip 'enc:' prefix)
            return f.decrypt(val[4:].encode()).decode()
    except Exception:
        # Fallback to returning raw string if decryption fails or cryptography is missing
        pass
    return val

def update_env_value(key, new_value):
    """Safely updates a specific key-value pair in .env file, symmetrically encrypting it if needed."""
    possible_paths = [
        Path.cwd() / ".env",
        Path.cwd() / "core" / ".env",
        Path(__file__).parent.parent.parent / ".env",
        Path(__file__).parent.parent.parent / "core" / ".env"
    ]
    target_path = None
    for path in possible_paths:
        if path.exists():
            target_path = path
            break
            
    if not target_path:
        target_path = Path.cwd() / ".env"
        
    lines = []
    updated = False
    
    # Read existing lines
    if target_path.exists():
        try:
            with open(target_path, "r") as f:
                lines = f.readlines()
        except PermissionError:
            print(f"\n{C_Y}❌ Permission Denied when trying to open {target_path}. Run with appropriate permissions.{C_R}")
            return False
            
    # Symmetrically encrypt the new value using the master key
    encrypted_val = new_value
    try:
        # Resolve the tools module to load secret_manager
        from core.tools.utils.secret_manager import encrypt_value
        encrypted_val = "enc:" + encrypt_value(new_value)
    except Exception:
        pass
        
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}="):
            new_lines.append(f"{key}={encrypted_val}\n")
            updated = True
        else:
            new_lines.append(line)
            
    if not updated:
        new_lines.append(f"{key}={encrypted_val}\n")
        
    try:
        with open(target_path, "w") as f:
            f.writelines(new_lines)
        return True
    except Exception as e:
        print(f"\n{C_Y}❌ Failed to write back env configuration: {e}{C_R}")
        return False

def load_env_vars():
    """Manually parse .env file to load active configurations securely."""
    env = {}
    possible_paths = [
        Path.cwd() / ".env",
        Path.cwd() / "core" / ".env",
        Path(__file__).parent.parent.parent / ".env",
        Path(__file__).parent.parent.parent / "core" / ".env"
    ]
    for path in possible_paths:
        if path.exists():
            try:
                with open(path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            parts = line.split("=", 1)
                            if len(parts) == 2:
                                key = parts[0].strip()
                                val = parts[1].strip().strip('"').strip("'")
                                # Decrypt immediately on load!
                                env[key] = decrypt_value(val)
                break
            except PermissionError:
                # Catch permission errors gracefully during pre-flight diagnostics
                pass
    return env
