"""Encrypt a secret into .env using Kenbun's Fernet master key.

The secret is read from a HIDDEN prompt (no terminal echo, not stored in shell
history) and is never printed. It is encrypted with .kenbun_master.key and the
resulting `enc:` value is written into .env in place — replacing an existing
line for the same key, or appending if absent.

Usage:
    core/.venv/bin/python3 scripts/dev/encrypt_secret.py GEMINI_API_KEY

Run it once per key you want to encrypt (e.g. ANTHROPIC_API_KEY, OPENAI_API_KEY).
Decryption happens automatically at runtime via tools/utils/secret_manager.py.
"""

import getpass
import sys
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[2]
KEY_FILE = ROOT / ".kenbun_master.key"
ENV_FILE = ROOT / ".env"


def main():
    if not KEY_FILE.exists():
        sys.exit(f"❌ Master key not found at {KEY_FILE}")

    name = sys.argv[1] if len(sys.argv) > 1 else "GEMINI_API_KEY"

    secret = getpass.getpass(f"Paste value for {name} (input hidden): ").strip()
    if not secret:
        sys.exit("❌ No value entered; aborting.")
    if secret.startswith("enc:"):
        sys.exit("⚠️  That value is already encrypted (starts with 'enc:'). Aborting.")

    token = Fernet(KEY_FILE.read_bytes()).encrypt(secret.encode()).decode()
    enc = f"enc:{token}"

    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    out, replaced = [], False
    for line in lines:
        if line.startswith(f"{name}=") and not line.lstrip().startswith("#"):
            out.append(f"{name}={enc}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{name}={enc}")

    ENV_FILE.write_text("\n".join(out) + "\n")
    action = "replaced" if replaced else "added"
    print(f"✅ {name} encrypted and {action} in {ENV_FILE}. (value never displayed)")


if __name__ == "__main__":
    main()
