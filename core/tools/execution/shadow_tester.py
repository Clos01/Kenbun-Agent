import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Import centralized settings
from tools.infrastructure.config import settings
project_root = settings.PROJECT_ROOT

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
        """Dispatch the 'shadow_test' workflow to the persistent FastAPI server.

        Posts to the same /orchestrate endpoint the MCP server itself uses
        (see server.py:_dispatch_orchestrate_http) so this runs through the
        real read → draft-test → guardrail → supervisor → sandbox pipeline
        instead of a no-op print.
        """
        task = f"Analyze the changes in {file_path.name} and suggest/write unit tests."
        print(f"🚀 Swarm Task: {task}")
        try:
            from tools.infrastructure.server_deps import get_or_create_config_token
            token = get_or_create_config_token()
            # Loopback, not settings.INTERNAL_API_URL: the watcher always runs
            # on the same host/network namespace as the FastAPI server it's
            # calling. INTERNAL_API_URL points at a Tailscale address meant
            # for cross-machine callers (e.g. the MCP client) and isn't
            # reachable via hairpin NAT from inside the same container.
            req = urllib.request.Request(
                f"http://127.0.0.1:{settings.API_PORT}/orchestrate",
                data=json.dumps({
                    "workflow": "shadow_test",
                    "task": task,
                    "file_path": str(file_path),
                    "project_path": str(self.project_path),
                }).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
            job_id = data.get("job_id")
            print(f"✅ Shadow Tester: dispatched shadow_test job {job_id} for {file_path.name}")
        except Exception as e:
            print(f"⚠️ Shadow Tester: failed to trigger swarm for {file_path.name}: {e}")

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
