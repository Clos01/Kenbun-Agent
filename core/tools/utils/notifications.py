import os
import sys
import subprocess
import requests
from pathlib import Path

# Import centralized settings
from tools.infrastructure.config import settings


from tools.utils.secret_manager import decrypt_value

# Load Config from Centralized Hub
TELEGRAM_TOKEN = decrypt_value(settings.telegram.bot_token.get_secret_value()) if settings.telegram.bot_token else None
TELEGRAM_CHAT_ID = decrypt_value(settings.telegram.chat_id.get_secret_value()) if settings.telegram.chat_id else None

def send_notification(title: str, message: str, sound: str = "Hero"):
    """
    Sends a native macOS notification and a Telegram message (if configured).
    """
    # 1. macOS Native
    try:
        apple_script = f'display notification "{message}" with title "{title}" sound name "{sound}"'
        subprocess.run(["osascript", "-e", apple_script])
    except Exception as e:
        print(f"⚠️ Failed to send macOS notification: {e}")

    # 2. Telegram Bridge (The Partner)
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": f"🛡️ *{title}*\n{message}",
                "parse_mode": "Markdown"
            }
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print(f"⚠️ Failed to send Telegram message: {e}")

if __name__ == "__main__":
    send_notification("Kenbun Partner", "I am now connected to your mobile device. 📞")
