import os
import pytest
import urllib.request
from tools.strategy.planka_workflow import (
    is_planka_sync_enabled,
    sync_pipeline_start,
    sync_pipeline_step,
    sync_pipeline_end
)
from tools.infrastructure.planka import _planka_request

def is_planka_reachable():
    """Helper to check if Planka instance is reachable for integration tests."""
    base_url = os.environ.get("PLANKA_BASE_URL", "http://127.0.0.1:1337").rstrip("/")
    try:
        with urllib.request.urlopen(f"{base_url}/", timeout=2) as response:
            return response.status == 200
    except Exception:
        return False

def test_is_planka_sync_enabled():
    # Test fallback/explicit values
    os.environ["PLANKA_SYNC_ENABLED"] = "false"
    assert not is_planka_sync_enabled()
    
    os.environ["PLANKA_SYNC_ENABLED"] = "true"
    assert is_planka_sync_enabled()
    
    del os.environ["PLANKA_SYNC_ENABLED"]
    # Should default to True if PLANKA_BASE_URL is set
    has_url = bool(os.environ.get("PLANKA_BASE_URL"))
    assert is_planka_sync_enabled() == has_url

@pytest.mark.skipif(not is_planka_reachable(), reason="Planka server is not reachable")
def test_planka_workflow_integration():
    """Verify full end-to-end sync workflow: start, step complete, and end transition."""
    # Ensure sync is enabled
    os.environ["PLANKA_SYNC_ENABLED"] = "true"
    
    task_name = "Planka Workflow Integration Test Task"
    workflow = "test_workflow"
    steps = [
        {"id": "step_one", "label": "Initial Research"},
        {"id": "step_two", "label": "Code Execution"},
        {"id": "step_three", "label": "Review and Verify"}
    ]
    
    # 1. Sync start
    ctx = sync_pipeline_start(workflow, task_name, steps)
    assert ctx is not None
    assert "card_id" in ctx
    assert "task_list_id" in ctx
    assert "step_tasks" in ctx
    assert "lists" in ctx
    
    card_id = ctx["card_id"]
    step_tasks = ctx["step_tasks"]
    assert "step_one" in step_tasks
    assert "step_two" in step_tasks
    assert "step_three" in step_tasks
    
    # 2. Sync step success
    sync_pipeline_step(ctx, "step_one", "Initial Research", success=True, result_preview="Completed research successfully.")
    
    # Fetch details to verify completion
    board_data = _planka_request(f"/api/boards/{ctx['board_id']}", "GET")
    tasks = board_data.get("included", {}).get("tasks", [])
    
    task_item = next((t for t in tasks if t["id"] == step_tasks["step_one"]), None)
    assert task_item is not None
    assert task_item["isCompleted"] is True
    
    # Verify second task is not yet completed
    task_item_two = next((t for t in tasks if t["id"] == step_tasks["step_two"]), None)
    assert task_item_two is not None
    assert task_item_two["isCompleted"] is False
    
    # 3. Sync step failure
    sync_pipeline_step(ctx, "step_two", "Code Execution", success=False, result_preview="Compilation error on line 45.")
    
    board_data = _planka_request(f"/api/boards/{ctx['board_id']}", "GET")
    tasks = board_data.get("included", {}).get("tasks", [])
    task_item_two = next((t for t in tasks if t["id"] == step_tasks["step_two"]), None)
    assert task_item_two["isCompleted"] is False # Success=False should mark completed as False
    
    # 4. Sync end (Failed/Blocked transition)
    sync_pipeline_end(ctx, success=False, summary="Workflow failed at step two due to compilation error.")
    
    # Fetch card to check listId is in blocked list
    card_res = _planka_request(f"/api/cards/{card_id}", "GET")
    card_item = card_res.get("item", {})
    assert card_item.get("listId") == ctx["lists"]["blocked"]
    
    # 5. Re-run and transition to Complete
    ctx2 = sync_pipeline_start(workflow, task_name, steps)
    assert ctx2 is not None
    assert ctx2["card_id"] == card_id # Should resolve same card
    
    # Complete all steps
    sync_pipeline_step(ctx2, "step_one", "Initial Research", success=True, result_preview="OK")
    sync_pipeline_step(ctx2, "step_two", "Code Execution", success=True, result_preview="OK")
    sync_pipeline_step(ctx2, "step_three", "Review and Verify", success=True, result_preview="OK")
    
    sync_pipeline_end(ctx2, success=True, summary="All tasks finished successfully.")
    
    card_res = _planka_request(f"/api/cards/{card_id}", "GET")
    card_item = card_res.get("item", {})
    assert card_item.get("listId") == ctx["lists"]["complete"]
    
    # Clean up test card so we don't pollute the board
    _planka_request(f"/api/cards/{card_id}", "PATCH", {"isClosed": True})
