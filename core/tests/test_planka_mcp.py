import os
import pytest
import urllib.request
from tools.registry import registry
from tools.infrastructure.planka import (
    planka_get_structure,
    planka_get_board,
    planka_create_card,
    planka_update_card,
    planka_move_card,
    planka_add_comment
)

def test_planka_tools_registration():
    """Verify that Planka tools are successfully registered in the sovereign registry."""
    tools = registry.get_all_tools()
    assert "planka_get_structure" in tools
    assert "planka_get_board" in tools
    assert "planka_create_card" in tools
    assert "planka_update_card" in tools
    assert "planka_move_card" in tools
    assert "planka_add_comment" in tools

def is_planka_reachable():
    """Helper to check if Planka instance is reachable for integration tests."""
    base_url = os.environ.get("PLANKA_BASE_URL", "http://127.0.0.1:1337").rstrip("/")
    try:
        with urllib.request.urlopen(f"{base_url}/", timeout=2) as response:
            return response.status == 200
    except Exception:
        return False

@pytest.mark.skipif(not is_planka_reachable(), reason="Planka server is not reachable at 127.0.0.1:1337")
def test_planka_live_integration():
    """Live integration test against Planka instance (requires active SSH tunnel)."""
    # 1. Test get structure
    struct = planka_get_structure()
    assert "❌ Error" not in struct
    assert "# 📁 Planka Project Structure" in struct
    
    # Extract a project and board ID if available
    # Our exploration script created a project named "Default Workspace" and a board named "Main Board"
    assert "Default Workspace" in struct
    assert "Main Board" in struct
    
    # Let's extract the board ID from the structure markdown
    # Structure format: "    *   **Board:** Main Board (ID: `1803497714239931407`)"
    board_id = None
    for line in struct.split("\n"):
        if "Main Board" in line and "ID:" in line:
            parts = line.split("`")
            if len(parts) >= 2:
                board_id = parts[1]
                break
                
    assert board_id is not None, f"Could not find Main Board ID in structure: {struct}"
    
    # 2. Test get board structure
    board_md = planka_get_board(board_id)
    assert "❌ Error" not in board_md
    assert "To Do" in board_md
    
    # Extract the To Do List ID
    # Format: "## 🟢 To Do (List ID: `1803497846654108693`)"
    list_id = None
    for line in board_md.split("\n"):
        if "To Do" in line and "List ID:" in line:
            parts = line.split("`")
            if len(parts) >= 2:
                list_id = parts[1]
                break
                
    assert list_id is not None, f"Could not find To Do List ID in board: {board_md}"
    
    # 3. Create card
    card_name = "Automated Test Card"
    create_res = planka_create_card(list_id, card_name, "Created by pytests")
    assert "✅" in create_res
    assert "Automated Test Card" in create_res
    
    # Extract card ID
    card_id = None
    for line in create_res.split("\n"):
        if "Card ID:" in line:
            parts = line.split("`")
            if len(parts) >= 2:
                card_id = parts[1]
                break
                
    assert card_id is not None
    
    # 4. Add comment
    comment_res = planka_add_comment(card_id, "This is an automated comment from integration tests.")
    assert "✅" in comment_res
    assert "Comment Added Successfully!" in comment_res
    
    # 5. Update card (archiving/moving it or changing name)
    update_res = planka_update_card(card_id, name="Automated Test Card (UPDATED)")
    assert "✅" in update_res
    assert "Automated Test Card (UPDATED)" in update_res
