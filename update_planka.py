import sys
import os
import json
import argparse
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

from tools.strategy.planka_workflow import sync_pipeline_step, sync_pipeline_end
from tools.infrastructure.planka import _planka_request

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--track", required=True, choices=["e2e", "impl"])
    parser.add_argument("--step", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--success", action="store_true")
    parser.add_argument("--preview", default="")
    parser.add_argument("--complete", action="store_true")
    args = parser.parse_args()

    # Load context
    ctx_path = Path(".agents/orchestrator/planka_context.json")
    if not ctx_path.exists():
        print(f"Error: Context file not found at {ctx_path}")
        sys.exit(1)

    with open(ctx_path, "r") as f:
        ctx_data = json.load(f)

    ctx = ctx_data.get(args.track)
    if not ctx:
        print(f"Error: Track '{args.track}' not found in context")
        sys.exit(1)

    # 1. Update the checklist item and post comment
    print(f"Updating Planka step {args.step} ('{args.label}') for {args.track} (Success: {args.success})")
    
    # We also manually mark the checklist task in Planka as completed if success is true
    task_id = ctx.get("step_tasks", {}).get(args.step)
    if task_id:
        try:
            _planka_request(f"/api/tasks/{task_id}", "PATCH", {"isCompleted": args.success})
            print(f"Checklist task {task_id} updated isCompleted to {args.success}")
        except Exception as e:
            print(f"Failed to update checklist task: {e}")

    # Add comment to card
    card_id = ctx["card_id"]
    status_emoji = "✅" if args.success else "❌"
    comment_text = f"🤖 **Step Update: {args.step} - {args.label}**\nStatus: {status_emoji} {'Passed' if args.success else 'Failed'}\nDetails: {args.preview}"
    try:
        _planka_request(f"/api/cards/{card_id}/comments", "POST", {"text": comment_text})
        print("Comment added successfully.")
    except Exception as e:
        print(f"Failed to add comment: {e}")

    # 2. If complete flag is passed, move card to completed list
    if args.complete and args.success:
        print(f"Moving card {card_id} to completed list...")
        try:
            # Get list id for complete
            complete_list_id = ctx["lists"]["complete"]
            _planka_request(f"/api/cards/{card_id}", "PATCH", {"listId": complete_list_id, "position": 65535})
            print("Card moved to Complete list.")
        except Exception as e:
            print(f"Failed to move card: {e}")

if __name__ == "__main__":
    main()
