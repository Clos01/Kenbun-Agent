import time
import os
import sys
import json
import datetime
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from tools.infrastructure.orchestrator import spawn_swarm
from tools.infrastructure.api_server import app 
from tools.utils.workspace_manager import workspace_manager
from tools.autonomic.autonomic_corrector import corrector
import uvicorn
from threading import Thread

def log_event(level: str, event: str, **kwargs):
    # Heritage-compliant metadata
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "level": level.upper(),
        "event": event,
        "theme": "Heritage",  # Token compliance
        **{k: str(v) for k, v in kwargs.items()}  # Robust string sanitization
    }
    try:
        sys.stdout.write(json.dumps(entry) + "\n")
    except (TypeError, ValueError):
        sys.stderr.write("LOGGING_SERIALIZATION_ERROR\n")

# CONFIG
PROJECTS_TO_WATCH = workspace_manager.get_projects()
IGNORE_DIRS = [".next", "node_modules", ".git", "__pycache__", "brain_health", "usage_stats.json"]
BATCH_QUEUE = [] # Tasks for the 50% cheaper Nightly Batch API

class KenbunWatchdog(FileSystemEventHandler):
    def __init__(self, loop):
        self.loop = loop
        self.last_run = 0

    def on_modified(self, event):
        if event.is_directory:
            return
        
        file_path = event.src_path
        if any(d in file_path for d in IGNORE_DIRS):
            return

        # Debounce: don't run more than once every 10 seconds
        if time.time() - self.last_run < 10:
            return
        
        self.last_run = time.time()
        log_event("info", "Change detected by watchdog", component="watchdog", file=os.path.basename(file_path), file_path=file_path)
        
        # Identify which project this file belongs to
        project_root = None
        for p in PROJECTS_TO_WATCH:
            if file_path.startswith(p):
                project_root = p
                break
        
        if not project_root:
            project_root = PROJECTS_TO_WATCH[0] # Fallback

        # Trigger an Autonomous Defensive Audit for this file
        objective = f"Autonomous Defensive Audit for recently modified file: {os.path.basename(file_path)}. Ensure no new technical debt or security flaws were introduced."
        
        # Run the swarm in the existing event loop
        asyncio.run_coroutine_threadsafe(self.run_audit(objective, file_path, project_root), self.loop)

    async def run_audit(self, objective, file_path, project_root):
        from tools.utils.error_memory import recall_fix, remember_fix
        from tools.memory.repo_mapper import scan_repo
        from tools.memory.code_indexer import search_code
        from tools.audit.gemini_reviewer import gemini_code_review
        from tools.audit.supervisor_agent import run_supervisor_audit
        from tools.audit.ui_designer import consult_ui_expert
        from tools.execution.sandbox_runner import run_code_safely
        from tools.utils.backtracker import save_checkpoint, restore_checkpoint

        tools = {
            "recall_fix": recall_fix,
            "remember_fix": remember_fix,
            "scan_repo": scan_repo,
            "search_code": search_code,
            "gemini_review": gemini_code_review,
            "run_supervisor_audit": run_supervisor_audit,
            "consult_ui_expert": consult_ui_expert,
            "run_in_sandbox": run_code_safely,
            "save_checkpoint": save_checkpoint,
            "restore_checkpoint": restore_checkpoint
        }

        # Determine which project this file belongs to
        project_root = ""
        for p in PROJECTS_TO_WATCH:
            if file_path.startswith(p):
                project_root = p
                break
        
        if not project_root:
            project_root = PROJECTS_TO_WATCH[0] if PROJECTS_TO_WATCH else "."

        log_event("info", "Spawning autonomous swarm for audit", component="watchdog", target_file=os.path.basename(file_path), project_path=project_root)
        await spawn_swarm(objective, tools, project_path=project_root)

class AutonomousTaskProcessor:
    """
    System 5b: Task Watcher.
    Scans projects for AG_TASKS.md and executes uncompleted tasks.
    """
    def __init__(self, loop):
        self.loop = loop
        self.is_running = False

    async def scan_and_execute(self):
        if self.is_running:
            return
        
        self.is_running = True
        try:
            from tools.strategy.token_governor import token_governor
            if token_governor.get_remaining_budget() < 0.20:
                log_event("warning", "Budget too low, skipping autonomous tasks", component="task_watcher", remaining_budget=token_governor.get_remaining_budget())
                return

            for project_path in PROJECTS_TO_WATCH:
                task_file = os.path.join(project_path, "AG_TASKS.md")
                if not os.path.exists(task_file):
                    continue

                with open(task_file, "r") as f:
                    lines = f.readlines()

                for i, line in enumerate(lines):
                    if line.strip().startswith("- [ ]"):
                        objective = line.replace("- [ ]", "").strip()
                        log_event("info", "Found autonomous task to execute", component="task_watcher", objective=objective)
                        
                        # Mark as In Progress
                        lines[i] = line.replace("- [ ]", "- [/]")
                        with open(task_file, "w") as f:
                            f.writelines(lines)

                        # Execute
                        success = await self.execute_task(objective, project_path)
                        
                        # Mark as Completed or Failed
                        status = "[x]" if success else "[!]"
                        lines[i] = lines[i].replace("- [/]", f"- {status}")
                        with open(task_file, "w") as f:
                            f.writelines(lines)
                        
                        # Only do one task per scan to prevent runaway spend
                        break 
        finally:
            self.is_running = False

    async def execute_task(self, objective: str, project_path: str) -> bool:
        try:
            # Re-use the swarm logic
            from tools.infrastructure.orchestrator import spawn_swarm
            # We use empty tools dict to let the orchestrator load default hivemind tools
            await spawn_swarm(f"AUTONOMOUS TASK: {objective}", {}, project_path=project_path)
            return True
        except Exception as e:
            import traceback
            log_event("error", "Task execution failed", component="task_watcher", objective=objective, exception=str(e), traceback=traceback.format_exc())
            return False

def start_api():
    """Runs the API server in a separate thread."""
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="error")

if __name__ == "__main__":
    log_event("info", "Kenbun Agentic Daemon starting...", component="daemon")
    
    # 1. Start API in background
    api_thread = Thread(target=start_api, daemon=True)
    api_thread.start()
    
    # 2. Setup Multi-Project Watchdog
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    event_handler = KenbunWatchdog(loop)
    observer = Observer()
    
    for project_path in PROJECTS_TO_WATCH:
        if os.path.exists(project_path):
            log_event("info", "Watchdog directory registered", component="daemon", watch_path=project_path)
            observer.schedule(event_handler, project_path, recursive=True)
        else:
            log_event("warning", "Watchdog project path not found", component="daemon", watch_path=project_path)
            
    # Correction Heartbeat (every 30 seconds)
    def correction_heartbeat():
        while True:
            try:
                corrector.run_correction_cycle()
            except Exception as e:
                import traceback
                log_event("error", "Autonomic heartbeat error", component="autonomic_corrector", exception=str(e), traceback=traceback.format_exc())
            time.sleep(30)
            
    Thread(target=correction_heartbeat, daemon=True).start()
            
    observer.start()

    # 3. Start Autonomous Task Watcher Loop
    task_processor = AutonomousTaskProcessor(loop)
    
    async def task_loop():
        while True:
            await task_processor.scan_and_execute()
            await asyncio.sleep(300) # Scan every 5 minutes

    # Run the task loop in the background
    asyncio.run_coroutine_threadsafe(task_loop(), loop)

    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
