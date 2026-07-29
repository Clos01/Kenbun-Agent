import asyncio
import logging
import datetime
import sys
import json
from tools.infrastructure.config import settings
from tools.infrastructure.orchestrator import orchestrate

logger = logging.getLogger("git_push_watcher_daemon")

def log_event(level: str, event: str, **kwargs):
    # Blueprint-compliant metadata
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "level": level.upper(),
        "event": event,
        "theme": "Blueprint",  # Token compliance
        **{k: str(v) for k, v in kwargs.items()}  # Robust string sanitization
    }
    try:
        sys.stdout.write(json.dumps(entry) + "\n")
        sys.stdout.flush()
    except (TypeError, ValueError):
        sys.stderr.write("LOGGING_SERIALIZATION_ERROR\n")
        sys.stderr.flush()

class GitPushWatcherDaemon:
    """
    Autonomic Git Push Integration Daemon (System 6.2).
    Polls configured Git repositories (e.g. Clos01/Kenbun-Agent)
    and integrates updates into Kenbun using the git_push_integration pipeline.
    """
    def __init__(self, loop):
        self.loop = loop
        self.is_running = False

    async def start(self):
        self.is_running = True
        log_event("info", "Git Push Watcher Daemon started", interval=settings.GIT_WATCH_INTERVAL, repos=settings.GIT_WATCH_REPOS)
        
        while self.is_running:
            try:
                await self.scan_and_integrate()
            except Exception as e:
                log_event("error", "Error in Git push watcher scan", exception=str(e))
            
            # Sleep in intervals, checking if stopped
            sleep_time = settings.GIT_WATCH_INTERVAL
            step = 10
            for _ in range(0, sleep_time, step):
                if not self.is_running:
                    break
                await asyncio.sleep(step)

    def stop(self):
        self.is_running = False
        log_event("info", "Git Push Watcher Daemon stopped")

    async def scan_and_integrate(self):
        from tools.strategy.token_governor import token_governor
        if token_governor.get_remaining_budget() < 0.20:
            log_event("warning", "Budget too low for Git push integration. Skipping cycle.", remaining_budget=token_governor.get_remaining_budget())
            return

        repos = [r.strip() for r in settings.GIT_WATCH_REPOS.split(",") if r.strip()]
        for repo in repos:
            log_event("info", "Checking for pushes on repository", repo=repo)
            
            # Execute integration pipeline in thread pool to prevent blocking the async loop
            def run_orchestrator():
                return orchestrate(
                    workflow="git_push_integration",
                    task=f"Check and integrate new updates from {repo}",
                    tech_key="python"
                )
                
            try:
                result_report = await self.loop.run_in_executor(None, run_orchestrator)
                log_event("info", "Completed push watcher cycle for repository", repo=repo, result_summary=result_report[:250])
            except Exception as e:
                import traceback
                log_event("error", "Failed git push integration run", repo=repo, exception=str(e), traceback=traceback.format_exc())
