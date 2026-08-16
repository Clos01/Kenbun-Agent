import sys
import os
from pathlib import Path

# Load env variables manually
env_path = Path(".env")
if env_path.exists():
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                val = val.strip().strip("'\"")
                os.environ[key.strip()] = val

sys.path.insert(0, str(Path("core").resolve()))
from tools.infrastructure.planka import _planka_request

def main():
    card_id = "1829913137130767545"
    list_id = "1803523573189444733"
    
    # 1. Add Comment
    comment_text = "🤖 **Task Completed via Kenbun Swarm**\nStatus: ✅ Success\nDetails: Fixed health check endpoint to explicitly return status HTTP 200 OK."
    try:
        _planka_request(f"/api/cards/{card_id}/comments", "POST", {"text": comment_text})
        print("Comment added successfully.")
    except Exception as e:
        print(f"Failed to add comment: {e}")

    # 2. Move Card
    try:
        _planka_request(f"/api/cards/{card_id}", "PATCH", {"listId": list_id, "position": 65535})
        print("Card successfully moved to Complete list.")
    except Exception as e:
        print(f"Failed to move card: {e}")

if __name__ == "__main__":
    main()
