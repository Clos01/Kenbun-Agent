import time
import sys
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Import centralized settings
from tools.infrastructure.config import settings
project_root = settings.PROJECT_ROOT

from tools.infrastructure.orchestrator import run_pipeline
from tools.infrastructure.agents import PERSONAS
from tools.utils.notifications import send_notification

class ShadowTesterHandler(FileSystemEventHandler):
    """
    Handles file system events and triggers the Kenbun Swarm.
    """
    def __init__(self, project_path):
        self.project_path = project_path
        self.last_trigger = {}
        self.cooldown = 5 # seconds

    def on_modified(self, event):
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Ignore irrelevant files
        if any(part.startswith('.') for part in file_path.parts) or \
           "node_modules" in file_path.parts or \
           "__pycache__" in file_path.parts:
            return

        # Simple cooldown to prevent double triggers
        now = time.time()
        if str(file_path) in self.last_trigger and (now - self.last_trigger[str(file_path)]) < self.cooldown:
            return
        
        self.last_trigger[str(file_path)] = now
        
        msg = f"Detected change in {file_path.name}. Spawning swarm..."
        print(f"🕵️ Shadow Tester: {msg}")
        send_notification("Kenbun Shadow Tester", msg)
        
        self.trigger_swarm(file_path)

    def trigger_swarm(self, file_path):
        # This is a placeholder for the actual trigger logic
        # In a real scenario, this would call a FastAPI endpoint or a background task queue
        task = f"Analyze the changes in {file_path.name} and suggest/write unit tests."
        print(f"🚀 Swarm Task: {task}")
        # Note: run_pipeline needs the 'tools' dict which is usually managed by the FastMCP server.
        # We will implement a 'background_queue' in server.py later.

def start_shadow_tester(path_to_watch):
    print(f"🛡️ Kenbun Shadow Tester active. Watching: {path_to_watch}")
    event_handler = ShadowTesterHandler(path_to_watch)
    observer = Observer()
    observer.schedule(event_handler, path_to_watch, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Kenbun Shadow Tester")
    parser.add_argument("path", help="Path to watch for changes")
    args = parser.parse_args()
    start_shadow_tester(args.path)
