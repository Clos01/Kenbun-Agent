import os
import sys
import json
import sqlite3
import traceback
import logging

# Ensure project root is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from tools.infrastructure.config import settings
from tools.infrastructure.orchestrator import orchestrate
from tools.strategy.kanban_tools import kanban_complete, kanban_block

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kanban_worker")

def main():
    task_id = os.environ.get("KENBUN_KANBAN_TASK") or os.environ.get("KENBUN_KANBAN_TASK")
    if not task_id:
        logger.error("❌ Error: KENBUN_KANBAN_TASK or KENBUN_KANBAN_TASK env var not set.")
        sys.exit(1)

    logger.info(f"Worker spawned for task: {task_id}")

    # Fetch task details from database
    db_path = settings.INTELLIGENCE_DB_PATH
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    cursor = conn.cursor()
    
    cursor.execute("SELECT title, body, assignee, tenant, status FROM kenbun_kanban_tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        logger.error(f"❌ Error: Task '{task_id}' not found in database.")
        sys.exit(1)

    title, body, assignee, tenant, status = row
    logger.info(f"Task info: title='{title}', assignee='{assignee}', status='{status}'")

    # Determine workflow based on assignee
    workflow = "bug_fix"
    if assignee == "auditor":
        workflow = "code_review"
    elif assignee == "designer":
        workflow = "design_ui"
    elif assignee == "coder":
        workflow = "bug_fix"

    task_prompt = f"Task Title: {title}\nDescription: {body}"

    try:
        # Run the orchestrator pipeline
        report = orchestrate(
            workflow=workflow,
            task=task_prompt,
            project_path=str(settings.PROJECT_ROOT),
            tech_key="python"
        )
        
        # Verify if task has been completed/blocked by the agent
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM kenbun_kanban_tasks WHERE id = ?", (task_id,))
        final_status = cursor.fetchone()[0]
        conn.close()

        if final_status == "running":
            # The agent completed the work but forgot to call kanban_complete. We do it automatically!
            report_summary = "\n".join(report[:5]) if isinstance(report, list) else str(report)[:500]
            logger.info("Automatic kanban_complete triggered for worker.")
            kanban_complete(
                task_id=task_id,
                summary=f"Automated completion: {report_summary}",
                metadata=json.dumps({"files_scanned": [], "agent_auto_close": True})
            )
            
        logger.info(f"✅ Task {task_id} execution finished successfully.")
        sys.exit(0)

    except Exception as e:
        error_msg = str(e)
        tb_msg = traceback.format_exc()
        logger.error(f"❌ Task {task_id} execution failed: {error_msg}\n{tb_msg}")
        
        try:
            kanban_block(
                task_id=task_id,
                reason=f"Execution error: {error_msg}",
                error=tb_msg
            )
        except Exception as block_err:
            logger.error(f"Failed to mark task as blocked: {block_err}")
            
        sys.exit(1)

if __name__ == "__main__":
    main()
