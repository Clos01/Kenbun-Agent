import os
from cryptography.fernet import Fernet
from pathlib import Path

# Path to the master key (hidden and protected)
from tools.infrastructure.config import settings
KEY_FILE = settings.PROJECT_ROOT / ".kenbun_master.key"

def _ensure_key():
    """Generates a key if it doesn't exist."""
    # Automated migration from old key file if present
    OLD_KEY_FILE = settings.PROJECT_ROOT / ".kenbun_master.key"
    if OLD_KEY_FILE.exists() and not KEY_FILE.exists():
        import shutil
        try:
            shutil.copy2(OLD_KEY_FILE, KEY_FILE)
        except Exception:
            pass

    if not KEY_FILE.exists():
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
        # Set restrictive permissions (read/write only for owner)
        os.chmod(KEY_FILE, 0o600)
    
    with open(KEY_FILE, "rb") as f:
        return f.read()

def encrypt_value(plain_text: str) -> str:
    """Encrypts a string for storage in .env."""
    key = _ensure_key()
    f = Fernet(key)
    return f.encrypt(plain_text.encode()).decode()

def decrypt_value(encrypted_text: str) -> str:
    """Decrypts a value retrieved from .env."""
    if not encrypted_text.startswith("enc:"):
        return encrypted_text # Already plain text
        
    key = _ensure_key()
    f = Fernet(key)
    try:
        return f.decrypt(encrypted_text[4:].encode()).decode()
    except Exception as e:
        return f"ERROR: Decryption failed. {e}"

if __name__ == "__main__":
    # CLI for the user to encrypt keys
    import sys
    if len(sys.argv) > 1:
        val = sys.argv[1]
        print(f"enc:{encrypt_value(val)}")
    else:
        print("Usage: python3 secret_manager.py <value_to_encrypt>")
