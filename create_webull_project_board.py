import os
import json
import urllib.request

PLANKA_URL = os.environ.get("PLANKA_BASE_URL", "http://100.104.211.61:1337").rstrip("/")
PLANKA_USER = os.environ.get("PLANKA_AGENT_EMAIL", "admin@example.com")
PLANKA_PASS = os.environ.get("PLANKA_AGENT_PASSWORD", "demoadminpass123")

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

def planka_post(path, token, payload):
    url = f"{PLANKA_URL}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"POST {path} failed: {e}")
        return None

def main():
    token = get_auth_token()
    if not token:
        print("Failed to authenticate with Planka.")
        return

    # 1. Create Project
    print("🚀 Creating Planka Project: Webull Agentic Trading...")
    proj_res = planka_post("/api/projects", token, {"name": "Webull Agentic Trading"})
    if not proj_res or not proj_res.get("item"):
        print("Failed to create project.")
        return
    
    project_id = proj_res["item"]["id"]
    print(f"✅ Project Created! ID: {project_id}")

    # 2. Create Board
    print("📌 Creating Planka Board: Webull Trading Engine...")
    board_res = planka_post(f"/api/projects/{project_id}/boards", token, {"name": "Webull Trading Board", "type": "kanban"})
    if not board_res or not board_res.get("item"):
        print("Failed to create board.")
        return
    
    board_id = board_res["item"]["id"]
    print(f"✅ Board Created! ID: {board_id}")

    # 3. Create Lists
    lists_to_create = [
        "Signal Triggered (To Do)",
        "In Trade (Holding)",
        "Target Reached (Closed)"
    ]
    
    list_ids = {}
    for idx, name in enumerate(lists_to_create):
        list_res = planka_post(f"/api/boards/{board_id}/lists", token, {
            "name": name,
            "position": (idx + 1) * 65535
        })
        if list_res and list_res.get("item"):
            lid = list_res["item"]["id"]
            list_ids[name] = lid
            print(f"  - List created: {name} (ID: {lid})")

    todo_id = list_ids.get("Signal Triggered (To Do)")
    if todo_id:
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

        for idx, (cname, cdesc) in enumerate(cards_to_create):
            card_res = planka_post(f"/api/lists/{todo_id}/cards", token, {
                "name": cname,
                "description": cdesc,
                "type": "project",
                "position": (idx + 1) * 65535
            })
            if card_res and card_res.get("item"):
                print(f"  ✅ Card created: {cname}")

    print("\n🎉 Webull Agentic Trading Project & Board creation complete!")

if __name__ == "__main__":
    main()
