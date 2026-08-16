import os
import json
import urllib.request

# Configuration
PLANKA_URL = os.environ.get("PLANKA_BASE_URL", "http://100.104.211.61:1337").rstrip("/")
PLANKA_USER = os.environ.get("PLANKA_AGENT_EMAIL", "admin@example.com")
PLANKA_PASS = os.environ.get("PLANKA_AGENT_PASSWORD", "demoadminpass123")

BOARD_ID = "1803497714239931407"  # Main Board

def get_auth_token():
    url = f"{PLANKA_URL}/api/access-tokens"
    data = json.dumps({"emailOrUsername": PLANKA_USER, "password": PLANKA_PASS}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res = json.loads(response.read().decode("utf-8"))
            return res.get("item")
    except Exception as e:
        print(f"Auth failed: {e}")
        return None

def create_card(token, list_id, name, description):
    url = f"{PLANKA_URL}/api/lists/{list_id}/cards"
    data = json.dumps({
        "name": name,
        "description": description,
        "type": "project",
        "position": 65535
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res = json.loads(response.read().decode("utf-8"))
            print(f"✅ Card created: {name}")
            return res
    except Exception as e:
        print(f"❌ Failed to create card {name}: {e}")
        return None

def main():
    token = get_auth_token()
    if not token:
        print("Could not authenticate with Planka.")
        return

    todo_id = "1803497846654108693"  # To Do List on Main Board
    print(f"Injecting Webull Trading Cards into List ID: {todo_id}")
    
    cards_to_create = [
        (
            "📈 [WEBULL-01] Webull Open API & MCP Auth Pipeline",
            "**Epic**: Infrastructure & Authentication\n"
            "**Tech Stack**: Webull Open API, Python, FastMCP, OAuth2 / HMAC-SHA256\n"
            "**Description**: Establish secure connection to Webull Open API using AppKey, AppSecret, and Trading PIN exchange. Configure Webull MCP server endpoint wrappers for account telemetry, position queries, and order submission."
        ),
        (
            "⚡ [WEBULL-02] Market Maker & PFOF Execution Router",
            "**Epic**: Order Execution Engine\n"
            "**Tech Stack**: Python, Webull OpenAPI, Apex Clearing\n"
            "**Description**: Model Webull's off-exchange PFOF market maker routing (Citadel, Two Sigma, Virtu). Implement Limit + Bracket order logic with slippage protection and trailing stops to prevent adverse selection."
        ),
        (
            "🖥️ [WEBULL-03] AWS US-East-1 VPS & Co-location Node",
            "**Epic**: Compute Infrastructure\n"
            "**Tech Stack**: AWS EC2 (us-east-1 / N. Virginia), Docker, Tailscale\n"
            "**Description**: Provision a dedicated low-latency VPS ($35/mo) in AWS us-east-1 (close to Webull API servers) to execute 2-3 week swing trade signals with sub-40ms WebSocket round-trip times."
        ),
        (
            "🧠 [WEBULL-04] 2-3 Week Swing Trade Agent (Kenbun System 1/2)",
            "**Epic**: Strategy Engine\n"
            "**Tech Stack**: Kenbun FastMCP, Gemini Pro, System 2 Supervisor\n"
            "**Description**: Build swing trading signal agent evaluating 2-3 week hold horizons. Integrates technical breakout indicators (EMA 20/50, RSI, Volume Profile) with fundamental sentiment scanning and automated risk management (max 2% account equity risk per trade)."
        ),
        (
            "📊 [WEBULL-05] Planka Kanban Real-Time Execution Sync",
            "**Epic**: Workflow Orchestration\n"
            "**Tech Stack**: Planka API, Next.js Dashboard, Webhooks\n"
            "**Description**: Bi-directional sync between Webull MCP order states (PENDING, FILLED, CLOSED) and Planka Kanban cards. Moves trade cards automatically from 'Signal Triggered' -> 'In Trade (Holding)' -> 'Target Reached (Closed)'."
        )
    ]

    for name, desc in cards_to_create:
        create_card(token, todo_id, name, desc)

if __name__ == "__main__":
    main()
