import os
import json
import urllib.request
import urllib.error
from typing import Optional, Tuple, Dict, Any
from tools.registry import sovereign_tool

def _get_planka_client() -> Tuple[str, str]:
    """Retrieves Planka configuration and authenticates to get a Bearer token."""
    try:
        from dotenv import load_dotenv
        from tools.utils.path_utils import get_project_root
        env_path = get_project_root() / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
    except Exception:
        pass

    base_url = os.environ.get("PLANKA_BASE_URL", "http://127.0.0.1:1337").rstrip("/")
    email = os.environ.get("PLANKA_AGENT_EMAIL", "admin@example.com")
    password = os.environ.get("PLANKA_AGENT_PASSWORD", "demoadminpass123")
    
    url = f"{base_url}/api/access-tokens"
    payload = {
        "emailOrUsername": email,
        "password": password
    }
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, method="POST")
    req.add_header("Content-Type", "application/json")
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            token = res_data.get("item")
            if not token:
                raise ValueError("No token key found in authentication response")
            return base_url, token
    except Exception as e:
        raise ConnectionError(f"Planka authentication failed at {url}. Make sure your SSH tunnel is active. Error: {e}")

def _planka_request(path: str, method: str = "GET", body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Performs an authorized HTTP request to the Planka REST API."""
    base_url, token = _get_planka_client()
    url = f"{base_url}{path}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    req_data = None
    if body:
        req_data = json.dumps(body).encode("utf-8")
        
    req = urllib.request.Request(url, data=req_data, method=method)
    for k, v in headers.items():
        req.add_header(k, v)
        
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = response.read().decode("utf-8")
            if not res_body:
                return {}
            return json.loads(res_body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        raise ValueError(f"Planka API HTTP Error {e.code}: {e.reason}. Response: {err_body}")
    except Exception as e:
        raise ConnectionError(f"Failed to communicate with Planka API at {url}: {e}")

@sovereign_tool()
def planka_get_structure() -> str:
    """
    Retrieves the entire workspace project and board structure from Planka.
    Returns:
        A formatted markdown summary of projects, boards, and lists.
    """
    try:
        projects_data = _planka_request("/api/projects", "GET")
        items = projects_data.get("items", [])
        included = projects_data.get("included", {})
        all_boards = included.get("boards", [])
        
        if not items:
            return "📁 **Planka Workspace:** No projects found. Create a project using the web UI."
            
        markdown = ["# 📁 Planka Project Structure\n"]
        for proj in items:
            proj_id = proj.get("id")
            proj_name = proj.get("name")
            markdown.append(f"*   **Project:** {proj_name} (ID: `{proj_id}`)")
            
            # Find boards for this project
            boards = [b for b in all_boards if b.get("projectId") == proj_id]
            if not boards:
                markdown.append("    *   *No boards in this project.*")
            else:
                for board in boards:
                    board_id = board.get("id")
                    board_name = board.get("name")
                    markdown.append(f"    *   **Board:** {board_name} (ID: `{board_id}`)")
                    
        return "\n".join(markdown)
    except Exception as e:
        return f"❌ Error retrieving Planka structure: {e}"

@sovereign_tool()
def planka_get_board(board_id: str) -> str:
    """
    Retrieves lists and cards within a specific Planka board.
    Args:
        board_id: The ID of the board to query.
    Returns:
        A markdown Kanban representation of lists and cards.
    """
    try:
        board_data = _planka_request(f"/api/boards/{board_id}", "GET")
        board_item = board_data.get("item", {})
        board_name = board_item.get("name", "Unknown Board")
        
        included = board_data.get("included", {})
        lists = included.get("lists", [])
        cards = included.get("cards", [])
        
        # Sort lists by position
        active_lists = [l for l in lists if l.get("type") in ("active", "list")]
        active_lists.sort(key=lambda x: x.get("position") or 0)
        
        markdown = [f"# 📋 Board: {board_name} (ID: `{board_id}`)\n"]
        
        if not active_lists:
            markdown.append("*No active lists found on this board.*")
            return "\n".join(markdown)
            
        for lst in active_lists:
            lst_id = lst.get("id")
            lst_name = lst.get("name")
            markdown.append(f"## 🟢 {lst_name} (List ID: `{lst_id}`)")
            
            # Find cards in this list
            list_cards = [c for c in cards if c.get("listId") == lst_id and not c.get("isClosed")]
            list_cards.sort(key=lambda x: x.get("position") or 0)
            
            if not list_cards:
                markdown.append("  *No open cards.*")
            else:
                for card in list_cards:
                    c_id = card.get("id")
                    c_name = card.get("name")
                    c_desc = card.get("description") or "No description"
                    due = card.get("dueDate") or "No due date"
                    markdown.append(f"  *   **{c_name}** (Card ID: `{c_id}`)")
                    markdown.append(f"      *Description:* {c_desc}")
                    markdown.append(f"      *Due Date:* {due}")
            markdown.append("") # Spacer
            
        return "\n".join(markdown)
    except Exception as e:
        return f"❌ Error retrieving Planka board {board_id}: {e}"

@sovereign_tool()
def planka_create_card(list_id: str, name: str, description: str = "") -> str:
    """
    Creates a new card in a specified Planka list.
    Args:
        list_id: The ID of the list where the card will be added.
        name: The title of the card.
        description: The description content of the card.
    Returns:
        Markdown confirmation of the created card.
    """
    try:
        payload = {
            "name": name,
            "description": description,
            "type": "project",
            "position": 65535
        }
        res = _planka_request(f"/api/lists/{list_id}/cards", "POST", payload)
        card = res.get("item", {})
        c_id = card.get("id")
        c_name = card.get("name")
        c_type = card.get("type")
        
        return (
            f"✅ **Card Created Successfully!**\n\n"
            f"*   **Card ID:** `{c_id}`\n"
            f"*   **Title:** {c_name}\n"
            f"*   **Type:** {c_type}\n"
            f"*   **List ID:** `{list_id}`"
        )
    except Exception as e:
        return f"❌ Failed to create card: {e}"

@sovereign_tool()
def planka_update_card(
    card_id: str, 
    name: Optional[str] = None, 
    description: Optional[str] = None, 
    list_id: Optional[str] = None
) -> str:
    """
    Updates card fields (name, description, or changes its list).
    Args:
        card_id: The ID of the card to update.
        name: (Optional) New title for the card.
        description: (Optional) New description for the card.
        list_id: (Optional) Moves the card to a new list ID.
    Returns:
        Markdown confirmation of the update status.
    """
    try:
        payload = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if list_id is not None:
            payload["listId"] = list_id
            payload["position"] = 65535 # Reset position relative to list
            
        if not payload:
            return "⚠️ No update fields provided. Nothing changed."
            
        res = _planka_request(f"/api/cards/{card_id}", "PATCH", payload)
        card = res.get("item", {})
        c_id = card.get("id")
        c_name = card.get("name")
        c_desc = card.get("description") or "No description"
        c_list = card.get("listId")
        
        return (
            f"✅ **Card Updated Successfully!**\n\n"
            f"*   **Card ID:** `{c_id}`\n"
            f"*   **Title:** {c_name}\n"
            f"*   **Description:** {c_desc}\n"
            f"*   **List ID:** `{c_list}`"
        )
    except Exception as e:
        return f"❌ Failed to update card {card_id}: {e}"

@sovereign_tool()
def planka_move_card(card_id: str, list_id: str, position: float = 65535.0) -> str:
    """
    Moves a card to a specific list at a specific position.
    Args:
        card_id: The ID of the card to move.
        list_id: The target list ID.
        position: The sort position index for the card.
    Returns:
        Markdown confirmation of the move.
    """
    try:
        payload = {
            "listId": list_id,
            "position": position
        }
        res = _planka_request(f"/api/cards/{card_id}", "PATCH", payload)
        card = res.get("item", {})
        c_id = card.get("id")
        c_list = card.get("listId")
        c_pos = card.get("position")
        
        return (
            f"✅ **Card Moved Successfully!**\n\n"
            f"*   **Card ID:** `{c_id}`\n"
            f"*   **New List ID:** `{c_list}`\n"
            f"*   **New Position:** {c_pos}"
        )
    except Exception as e:
        return f"❌ Failed to move card {card_id}: {e}"

@sovereign_tool()
def planka_add_comment(card_id: str, text: str) -> str:
    """
    Adds a comment to a specific card in Planka.
    Args:
        card_id: The ID of the card to comment on.
        text: The text body of the comment.
    Returns:
        Markdown confirmation of the comment creation.
    """
    try:
        payload = {
            "text": text
        }
        res = _planka_request(f"/api/cards/{card_id}/comments", "POST", payload)
        comment = res.get("item", {})
        comment_id = comment.get("id")
        user_id = comment.get("userId")
        
        return (
            f"✅ **Comment Added Successfully!**\n\n"
            f"*   **Comment ID:** `{comment_id}`\n"
            f"*   **User ID:** `{user_id}`\n"
            f"*   **Card ID:** `{card_id}`"
        )
    except Exception as e:
        return f"❌ Failed to add comment: {e}"
