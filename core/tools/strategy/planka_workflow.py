import os
import logging
from typing import Optional, Dict, Any, List, Tuple
from tools.infrastructure.planka import _planka_request

logger = logging.getLogger("planka_workflow")

def is_planka_sync_enabled() -> bool:
    """Checks if Planka sync is enabled via environment variables."""
    # Check explicit toggle first
    val = os.environ.get("PLANKA_SYNC_ENABLED")
    if val is not None:
        return val.strip().lower() in ("true", "1", "yes")
    # Default to True if Planka base URL is set
    return bool(os.environ.get("PLANKA_BASE_URL"))

def get_planka_board_and_lists(board_id: Optional[str] = None) -> Tuple[str, Dict[str, str]]:
    """
    Finds or defaults the board_id and maps the standard workflow lists:
    - todo
    - inprogress
    - blocked
    - complete
    
    If list(s) are missing, they are dynamically created.
    """
    if not board_id:
        board_id = os.environ.get("PLANKA_DEFAULT_BOARD_ID")
    
    if not board_id:
        # Find first board in projects
        projects_data = _planka_request("/api/projects", "GET")
        items = projects_data.get("items", [])
        included = projects_data.get("included", {})
        all_boards = included.get("boards", [])
        
        if not all_boards:
            raise ValueError("No Planka boards found to run workflow sync.")
        board_id = all_boards[0].get("id")
        
    # Fetch Board Details to scan lists
    board_data = _planka_request(f"/api/boards/{board_id}", "GET")
    included = board_data.get("included", {})
    lists = included.get("lists", [])
    
    # Map lists
    lists_map = {}
    for lst in lists:
        name_lower = (lst.get("name") or "").lower()
        if name_lower in ("to do", "todo", "triage"):
            lists_map["todo"] = lst.get("id")
        elif name_lower in ("in progress", "doing", "running", "active"):
            lists_map["inprogress"] = lst.get("id")
        elif name_lower in ("blocked", "hold"):
            lists_map["blocked"] = lst.get("id")
        elif name_lower in ("complete", "completed", "done"):
            lists_map["complete"] = lst.get("id")
            
    # Dynamically create missing lists
    if "todo" not in lists_map:
        res = _planka_request(f"/api/boards/{board_id}/lists", "POST", {"name": "To Do", "position": 65535.0, "type": "active"})
        lists_map["todo"] = res["item"]["id"]
        
    if "inprogress" not in lists_map:
        res = _planka_request(f"/api/boards/{board_id}/lists", "POST", {"name": "In Progress", "position": 131070.0, "type": "active"})
        lists_map["inprogress"] = res["item"]["id"]
        
    if "blocked" not in lists_map:
        res = _planka_request(f"/api/boards/{board_id}/lists", "POST", {"name": "Blocked", "position": 196605.0, "type": "active"})
        lists_map["blocked"] = res["item"]["id"]
        
    if "complete" not in lists_map:
        res = _planka_request(f"/api/boards/{board_id}/lists", "POST", {"name": "Complete", "position": 262140.0, "type": "active"})
        lists_map["complete"] = res["item"]["id"]
        
    return board_id, lists_map


def sync_pipeline_start(
    workflow: str,
    task: str,
    steps: List[Dict[str, Any]],
    board_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Initializes a Planka card for tracking the task's lifecycle stages.
    """
    if not is_planka_sync_enabled():
        return None
        
    try:
        # Resolve board and lists
        board_id, lists_map = get_planka_board_and_lists(board_id)
        
        # 1. Search for existing card by name in 'todo' or 'inprogress' lists
        board_data = _planka_request(f"/api/boards/{board_id}", "GET")
        all_cards = board_data.get("included", {}).get("cards", [])
        
        card = None
        card_title = task.strip()
        if len(card_title) > 80:
            card_title = card_title[:77] + "..."
            
        for c in all_cards:
            card_name = c.get("name") or ""
            if card_name.strip().lower() == card_title.lower() and not c.get("isClosed"):
                card = c
                break
                
        if card:
            card_id = card["id"]
            # Move card to In Progress if it's in todo
            if card.get("listId") == lists_map["todo"]:
                _planka_request(f"/api/cards/{card_id}", "PATCH", {"listId": lists_map["inprogress"], "position": 65535})
        else:
            # Create a new card in 'inprogress' directly
            payload = {
                "name": card_title,
                "description": f"Goal/Task Objective:\n{task}\n\nWorkflow: `{workflow}`\nStatus: Started",
                "type": "project",
                "position": 65535
            }
            res = _planka_request(f"/api/lists/{lists_map['inprogress']}/cards", "POST", payload)
            card_id = res["item"]["id"]
            
        # 2. Create or find the Checklist ("Lifecycle Stages")
        board_data = _planka_request(f"/api/boards/{board_id}", "GET")
        all_task_lists = board_data.get("included", {}).get("taskLists", [])
        
        task_list = None
        for tl in all_task_lists:
            if tl.get("cardId") == card_id and tl.get("name") == "Lifecycle Stages":
                task_list = tl
                break
                
        if task_list:
            task_list_id = task_list["id"]
        else:
            res_tl = _planka_request(f"/api/cards/{card_id}/task-lists", "POST", {"name": "Lifecycle Stages", "position": 65535})
            task_list_id = res_tl["item"]["id"]
            
        # 3. Populate checklist items/tasks for each pipeline step
        all_tasks = board_data.get("included", {}).get("tasks", [])
        existing_tasks = {t.get("name"): t for t in all_tasks if t.get("taskListId") == task_list_id}
        
        step_tasks = {}
        pos = 65535.0
        for step in steps:
            step_id = step["id"]
            label = step["label"]
            task_name = f"{label} ({step_id})"
            
            if task_name in existing_tasks:
                task_item = existing_tasks[task_name]
                if task_item.get("isCompleted"):
                    _planka_request(f"/api/tasks/{task_item['id']}", "PATCH", {"isCompleted": False})
                step_tasks[step_id] = task_item["id"]
            else:
                res_task = _planka_request(f"/api/task-lists/{task_list_id}/tasks", "POST", {
                    "name": task_name,
                    "position": pos
                })
                step_tasks[step_id] = res_task["item"]["id"]
            pos += 65535.0
            
        # 4. Post start comment
        _planka_request(f"/api/cards/{card_id}/comments", "POST", {
            "text": f"🤖 **Kenbun Swarm execution started.**\nWorkflow: `{workflow}`\nObjective: {task}"
        })
        
        return {
            "card_id": card_id,
            "task_list_id": task_list_id,
            "step_tasks": step_tasks,
            "lists": lists_map,
            "board_id": board_id
        }
    except Exception as e:
        logger.warning(f"Failed to initialize Planka workflow: {e}")
        return None


def sync_pipeline_step(
    ctx: Optional[Dict[str, Any]],
    step_id: str,
    step_label: str,
    success: bool,
    result_preview: str
):
    """
    Updates the step status on the Planka card.
    Marks the checklist item as completed and leaves a status comment.
    """
    if not ctx:
        return
    try:
        card_id = ctx["card_id"]
        step_tasks = ctx.get("step_tasks", {})
        task_id = step_tasks.get(step_id)
        
        # 1. Mark checklist item completed
        if task_id:
            _planka_request(f"/api/tasks/{task_id}", "PATCH", {"isCompleted": success})
            
        # 2. Leave comment with results preview
        status_icon = "✅" if success else "❌"
        status_text = "successful" if success else "failed"
        
        clean_preview = result_preview.strip()
        if len(clean_preview) > 500:
            clean_preview = clean_preview[:497] + "..."
            
        comment_text = (
            f"🔧 **Step: {step_label} ({step_id})** {status_icon}\n"
            f"Execution was {status_text}.\n\n"
            f"**Preview output:**\n```\n{clean_preview}\n```"
        )
        _planka_request(f"/api/cards/{card_id}/comments", "POST", {"text": comment_text})
    except Exception as e:
        logger.warning(f"Failed to sync step {step_id} to Planka: {e}")


def sync_pipeline_end(
    ctx: Optional[Dict[str, Any]],
    success: bool,
    summary: str
):
    """
    Finalizes the Planka card lifecycle. Moves it to complete or blocked and posts the summary.
    """
    if not ctx:
        return
    try:
        card_id = ctx["card_id"]
        lists_map = ctx["lists"]
        
        # 1. Post final summary comment
        status_header = "🎯 **Swarm Pipeline Execution Complete!** ✅" if success else "⚠️ **Swarm Pipeline Blocked or Failed!** ❌"
        
        clean_summary = summary.strip()
        if len(clean_summary) > 1500:
            clean_summary = clean_summary[:1497] + "..."
            
        comment_text = f"{status_header}\n\n{clean_summary}"
        _planka_request(f"/api/cards/{card_id}/comments", "POST", {"text": comment_text})
        
        # 2. Transition card to final column
        target_list_id = lists_map["complete"] if success else lists_map["blocked"]
        _planka_request(f"/api/cards/{card_id}", "PATCH", {
            "listId": target_list_id,
            "position": 65535,
            "description": f"Goal/Task Objective Finished.\nStatus: {'Success' if success else 'Blocked/Failed'}"
        })
    except Exception as e:
        logger.warning(f"Failed to finalize Planka workflow: {e}")
