# ⏰ Kenbun Scheduling & Push-Tracking

Kenbun employs a sophisticated background scheduling and push-tracking ecosystem within System 6 (The Autonomic). This allows agents and workflows to be executed asynchronously based on time or external events.

## 1. The Scheduler Daemon (`scheduler_daemon.py`)

The core engine for time-based autonomic tasks is the `scheduler_daemon.py`. It runs in the background and continuously polls `intelligence.db` for tasks.

### Supported Schedule Formats
The scheduler supports four distinct timing models:
1. **One-shot Delays**: Run once after a relative delay (e.g. `30m`, `2h`, `1d`).
2. **Recurring Intervals**: Run repeatedly at fixed intervals (e.g. `every 30m`, `every 12h`).
3. **ISO Timestamps**: Run once at an exact UTC time (e.g. `2026-03-15T09:00:00Z`).
4. **Cron Expressions**: Advanced scheduling via standard 5-field Unix cron syntax (powered by `croniter`).

When a task triggers, the scheduler daemon routes the payload to the Orchestrator for execution.

## 2. Git Push Tracking (`git_push_watcher_daemon.py`)

Kenbun is designed to act on events happening in external repositories.
- The `git_push_watcher_daemon.py` polls configured Git repositories (e.g. `Clos01/Kenbun-Agent`) based on the `GIT_WATCH_INTERVAL` defined in `.env` / `config.py`.
- When a new push or commit is detected, it triggers the `git_push_integration` pipeline.
- This allows Kenbun to instantly audit incoming code, run SVE checks, and ensure continuous architectural compliance.

## 3. Integration with the Governor

The Governor (System 4) oversees these background tasks. It ensures that cronjobs and one-shot tasks do not exceed the global token budget or API rate limits. If a scheduled task fails (e.g. due to a timeout), the Governor records the failure and adjusts the Bayesian tool weights accordingly to optimize future scheduling decisions.
