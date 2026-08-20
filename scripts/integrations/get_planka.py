import json
import urllib.request

base_url = "http://100.104.211.61:1337"
email = "admin@example.com"
password = "demoadminpass123"

# get token
req = urllib.request.Request(f"{base_url}/api/access-tokens", data=json.dumps({"emailOrUsername": email, "password": password}).encode("utf-8"), method="POST")
req.add_header("Content-Type", "application/json")
with urllib.request.urlopen(req) as response:
    token = json.loads(response.read().decode())["item"]

# get board 1
req = urllib.request.Request(f"{base_url}/api/boards/1821314980880844507", method="GET")
req.add_header("Authorization", f"Bearer {token}")
with urllib.request.urlopen(req) as response:
    board_data = json.loads(response.read().decode())

lists = board_data.get("included", {}).get("lists", [])
cards = board_data.get("included", {}).get("cards", [])

for lst in lists:
    if lst.get("type") != "active": continue
    print(f"List: {lst.get('name')}")
    for card in cards:
        if card.get("listId") == lst.get("id") and not card.get("isClosed"):
            print(f"  - Card: {card.get('name')} ({card.get('id')})")
            print(f"    Due Date: {card.get('dueDate')}")
            print(f"    {card.get('description')}")


