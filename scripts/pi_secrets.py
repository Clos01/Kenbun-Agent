#!/usr/bin/env python3
import os
import sys
import json
import base64
import hashlib
from pathlib import Path
from cryptography.fernet import Fernet

# Ensure PYTHONPATH includes core
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.tools.infrastructure.config import settings

ENC_FILE_PATH = Path(settings.BRAIN_HEALTH_DIR) / "pi_credentials.enc"

def get_encryption_key() -> bytes:
    """Derive a stable 32-byte Fernet key from the Planka secret key."""
    # Try to load directly from .env file to avoid pydantic schema mismatches
    secret = os.environ.get("PLANKA_SECRET_KEY")
    if not secret:
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    if line.strip().startswith("PLANKA_SECRET_KEY="):
                        secret = line.split("=", 1)[1].strip()
                        break
    if not secret:
        secret = "kenbun_default_secure_fallback_salt_32bytes_long"
    
    # Hash the secret to ensure it's exactly 32 bytes, then base64 urlsafe encode
    hasher = hashlib.sha256(secret.encode("utf-8"))
    key_32 = hasher.digest()
    return base64.urlsafe_b64encode(key_32)

def encrypt_data(data: dict) -> bytes:
    """Encrypt a dictionary into a secure token."""
    key = get_encryption_key()
    fernet = Fernet(key)
    serialized = json.dumps(data).encode("utf-8")
    return fernet.encrypt(serialized)

def decrypt_data() -> dict:
    """Decrypt the stored credentials file."""
    if not ENC_FILE_PATH.exists():
        raise FileNotFoundError(f"No encrypted credentials found at {ENC_FILE_PATH}")
    
    key = get_encryption_key()
    fernet = Fernet(key)
    
    with open(ENC_FILE_PATH, "rb") as f:
        encrypted_payload = f.read()
        
    decrypted = fernet.decrypt(encrypted_payload)
    return json.loads(decrypted.decode("utf-8"))

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/pi_secrets.py --generate             ➔ Generate and encrypt credentials")
        print("  python scripts/pi_secrets.py --show                 ➔ Decrypt and display credentials")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "--generate":
        # Check if already exists to prevent overwriting
        if ENC_FILE_PATH.exists():
            print("⚠️ Encrypted credentials already exist. Use --show to view them.")
            sys.exit(0)

        # Generate credentials
        # We will use "sentry" as hostname and "carlos" as username
        hostname = "sentry"
        username = "carlos"
        
        # Generate a high-entropy secure password (alphanumeric + symbols)
        import secrets
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        password = "".join(secrets.choice(alphabet) for _ in range(16))
        # Ensure it has at least one symbol and number
        if not any(c.isdigit() for c in password):
            password += "9"
        if not any(c in "!@#$%^&*" for c in password):
            password += "!"

        creds = {
            "hostname": hostname,
            "username": username,
            "password": password
        }

        # Encrypt and save
        os.makedirs(ENC_FILE_PATH.parent, exist_ok=True)
        encrypted = encrypt_data(creds)
        with open(ENC_FILE_PATH, "wb") as f:
            f.write(encrypted)
            
        print("✅ Successfully generated and encrypted Raspberry Pi credentials!")
        print(f"Stored securely in: {ENC_FILE_PATH}")
        print("\nPlaintext Credentials (use these in the Raspberry Pi Imager now!):")
        print(f"  Hostname: {hostname}")
        print(f"  Username: {username}")
        print(f"  Password: {password}")
        print("\nTo show these credentials in the future, run:")
        print("  python scripts/pi_secrets.py --show")

    elif cmd == "--show":
        try:
            creds = decrypt_data()
            print("🔒 Decrypted Raspberry Pi Credentials:")
            print(f"  IP Address: {creds.get('ip_address', '192.168.1.183')}")
            print(f"  Hostname: {creds.get('hostname')}")
            print(f"  Username: {creds.get('username')}")
            
            # Support both old key 'password' and new key 'ssh_password'
            ssh_pw = creds.get('ssh_password') or creds.get('password')
            print(f"  SSH Password: {ssh_pw}")
            
            if 'pihole_admin_password' in creds:
                print(f"  Pi-hole Admin Password: {creds['pihole_admin_password']}")
                print(f"  Dashboard URL: http://{creds.get('ip_address', '192.168.1.183')}/admin")
        except Exception as e:
            print(f"❌ Failed to decrypt credentials: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
