import os
from cryptography.fernet import Fernet

# Path to the master key (hidden and protected)
from core.tools.utils.path_utils import get_project_root
KEY_FILE = get_project_root() / ".kenbun_master.key"

def _ensure_key():
    """Generates a key if it doesn't exist."""

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
        
    ciphertext = encrypted_text[4:]
    if ciphertext.startswith("v1:"):
        ciphertext = ciphertext[3:]
        
    key = _ensure_key()
    f = Fernet(key)
    try:
        return f.decrypt(ciphertext.encode()).decode()
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
