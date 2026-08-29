import glob
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.infrastructure.config import settings
from tools.infrastructure.orchestrator import HEAVY_WORKFLOWS
from tools.registry import sovereign_tool
from tools.utils.helpers import debug_log
from tools.utils.path_utils import get_project_root

logger = logging.getLogger("tools.orchestration")
PROJECT_ROOT = get_project_root()


def _get_config_token(force_fresh: bool = False) -> str:
    """Resolve the CONFIG_TOKEN for talking to the persistent FastAPI server."""
    if force_fresh:
        env_token = getattr(settings, "CONFIG_TOKEN", None) or os.getenv("CONFIG_TOKEN")
        if env_token:
            return env_token
        token_file = settings.BRAIN_HEALTH_DIR / "config_token.secret"
        if token_file.exists():
            try:
                with open(token_file, "r", encoding="utf-8") as f:
                    val = f.read().strip()
                    if val:
                        return val
            except Exception:
                pass
    from tools.infrastructure.server_deps import get_or_create_config_token
    return get_or_create_config_token()


def _dispatch_orchestrate_http(
    workflow: str,
    task: str,
    project_path: str,
    file_path: str,
    code_snippet: str,
    tech_key: str,
    project_id: str,
    token: str,
) -> dict:
    """POST the orchestration to the persistent FastAPI server."""
    import urllib.request
    req = urllib.request.Request(
        f"{settings.INTERNAL_API_URL}/orchestrate",
        data=json.dumps({
            "workflow": workflow,
            "task": task,
            "project_path": project_path,
            "file_path": file_path,
            "code_snippet": code_snippet,
            "tech_key": tech_key,
            "project_id": project_id
        }).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _record_dispatch_fallback(workflow: str, reason: str) -> None:
    """Append a JSONL event when orchestrate falls back from async to inline."""
    try:
        brain_dir = settings.BRAIN_HEALTH_DIR
        if not brain_dir:
            return
        brain_dir.mkdir(parents=True, exist_ok=True)
        log_path = brain_dir / "dispatch_fallbacks.jsonl"
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "workflow": workflow,
            "reason": reason,
        }
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")
    except Exception as telemetry_err:
        debug_log(f"⚠️ Failed to record dispatch_fallback event: {telemetry_err}")


def _execute_orchestration(
    workflow: str,
    task: str,
    project_path: str = "",
    file_path: str = "",
    code_snippet: str = "",
    tech_key: str = "",
    project_id: str = "",
) -> str:
    """Execute orchestration inline within this process."""
    from tools.infrastructure.orchestrator import run_orchestration_pipeline
    return run_orchestration_pipeline(
        workflow=workflow,
        task=task,
        project_path=project_path,
        file_path=file_path,
        code_snippet=code_snippet,
        tech_key=tech_key,
        project_id=project_id,
    )


@sovereign_tool()
def orchestrate(
    workflow: str,
    task: str,
    project_path: str = "",
    file_path: str = "",
    code_snippet: str = "",
    tech_key: str = "",
    project_id: str = "",
    wait: bool = False,
    fast: bool = False,
) -> str:
    """Run a Kenbun pipeline.

    Heavy workflows (design_ui, research_implement, code_review, shadow_test,
    bug_fix) dispatch asynchronously and return a Job ID — poll it with
    orchestrate_status() — so the MCP call never blocks past its request timeout.
    Set wait=True to force a blocking run.
    """
    from tools.registry import registry
    valid_workflows = set(registry.get_all_pipelines().keys())
    if workflow not in valid_workflows:
        import difflib
        matches = difflib.get_close_matches(workflow, valid_workflows)
        suggestion = f" Did you mean '{matches[0]}'?" if matches else ""
        return f"❌ Invalid workflow '{workflow}'.{suggestion} Valid options: {', '.join(sorted(valid_workflows))}"

    if workflow in HEAVY_WORKFLOWS and not wait:
        import urllib.error
        fallback_reason = "unknown"
        try:
            data = _dispatch_orchestrate_http(
                workflow, task, project_path, file_path, code_snippet, tech_key, project_id,
                token=_get_config_token()
            )
            job_id = data.get("job_id")
            return (
                f"🚀 **Orchestration initiated (async)**\n"
                f"- **Job ID:** `{job_id}`\n"
                f"- **Workflow:** `{workflow}`\n"
                f"- **Task:** {task}\n\n"
                f"This workflow was securely dispatched to the permanent FastAPI server. "
                f"Retrieve the result with `orchestrate_status(\"{job_id}\")`."
            )
        except urllib.error.HTTPError as http_err:
            if http_err.code in (401, 403):
                try:
                    data = _dispatch_orchestrate_http(
                        workflow, task, project_path, file_path, code_snippet, tech_key, project_id,
                        token=_get_config_token(force_fresh=True)
                    )
                    job_id = data.get("job_id")
                    return (
                        f"🚀 **Orchestration initiated (async)** _(after token refresh)_\n"
                        f"- **Job ID:** `{job_id}`\n"
                        f"- **Workflow:** `{workflow}`\n"
                        f"- **Task:** {task}\n\n"
                        f"Retrieve the result with `orchestrate_status(\"{job_id}\")`."
                    )
                except Exception as retry_err:
                    debug_log(
                        f"⚠️ Async dispatch failed after token-refresh retry "
                        f"(workflow={workflow}, err={retry_err}). Falling back to inline."
                    )
                    fallback_reason = f"http_{http_err.code}_after_token_refresh:{retry_err.__class__.__name__}"
            else:
                debug_log(
                    f"⚠️ Async dispatch HTTP {http_err.code} "
                    f"(workflow={workflow}). Falling back to inline."
                )
                fallback_reason = f"http_{http_err.code}"
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            debug_log(
                f"⚠️ Async dispatch failed (workflow={workflow}, err={e}). "
                f"Falling back to inline execution.\n{tb}"
            )
            fallback_reason = f"{e.__class__.__name__}:{str(e)[:120]}"

        _record_dispatch_fallback(workflow, fallback_reason)
        
        try:
            inline_result = _execute_orchestration(
                workflow, task, project_path, file_path, code_snippet, tech_key, project_id
            )
            return (
                f"_⚠️ Persistent-server dispatch unavailable; ran inline instead._ "
                f"_(reason: `{fallback_reason}` — see brain_health/dispatch_fallbacks.jsonl)_\n\n"
                f"{inline_result}"
            )
        except Exception as inline_e:
            import traceback
            tb = traceback.format_exc()
            return f"❌ Inline orchestration crashed: {inline_e}\n\nTraceback:\n{tb}"

    try:
        return _execute_orchestration(workflow, task, project_path, file_path, code_snippet, tech_key, project_id)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return f"❌ Inline orchestration crashed (wait mode): {e}\n\nTraceback:\n{tb}"


@sovereign_tool()
def orchestrate_status(job_id: str) -> str:
    """Check the status (or retrieve the result) of an async orchestrate() job by its Job ID."""
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(
            f"{settings.INTERNAL_API_URL}/orchestrate/status/{job_id}",
            headers={"Authorization": f"Bearer {_get_config_token()}"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            
        status = data.get("status")
        workflow = data.get("workflow")
        task = data.get("task")
        result = data.get("result")
        error = data.get("error")

        if status == "running":
            return f"⏳ Job `{job_id}` (`{workflow}`) is still running.\nTask: {task}"
        if status == "failed":
            return f"❌ Job `{job_id}` (`{workflow}`) failed:\n{error}"
        return f"✅ Job `{job_id}` (`{workflow}`) completed.\n\n{result}"

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"❌ No orchestration job `{job_id}` found on the server."
        if e.code in (401, 403):
            return f"⚠️ Authorization failed (HTTP {e.code}). The persistent server may have restarted or rotated tokens."
        return f"❌ Server returned HTTP {e.code} while checking job status."
    except Exception as e:
        return f"❌ Failed to check orchestration status: {e}"


@sovereign_tool()
def reflect_on_task(task: str, tool_logs: str) -> str:
    """
    Analyzes tool logs to extract architectural patterns for the Hivemind.
    Usually called automatically by orchestrate(), but can be run manually.
    """
    from tools.audit.reflection_agent import reflect_and_distill as _reflect_and_distill
    result = _reflect_and_distill(task, tool_logs)
    if isinstance(result, dict):
        return result.get("report", str(result))
    return str(result)


@sovereign_tool()
def get_brain_health() -> str:
    """
    Returns the latest performance metrics from brain_health/BENCHMARKS.json.
    Use this to monitor system accuracy and logical depth over time.
    """
    path = Path(PROJECT_ROOT) / "brain_health" / "BENCHMARKS.json"
    if not path.exists():
        return "No benchmark data found."
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return "ERROR: BENCHMARKS.json is corrupted or not valid JSON."
    except Exception as e:
        return f"ERROR: Failed to read benchmarks. Reason: {str(e)}"
    
    try:
        latest_version = "unknown"
        last_updated = "unknown"
        latest = {}
        
        if isinstance(data, list):
            if not data:
                return "ERROR: Benchmark log is an empty list."
            bench_container = next((item for item in reversed(data) if isinstance(item, dict) and "benchmarks" in item), None)
            if not bench_container:
                return "ERROR: No valid benchmark containers found in the array."
            try:
                latest_version = bench_container.get("system_version", "unknown")
            except Exception:
                pass
            last_updated = bench_container.get("last_updated", "unknown")
            benchmarks_list = bench_container.get("benchmarks", [])
            
            if isinstance(benchmarks_list, list) and benchmarks_list:
                latest = benchmarks_list[-1]
                
        elif isinstance(data, dict):
            last_updated = data.get("last_updated", "unknown")
            latest_version = data.get("system_version", "unknown")
            
            if "history" in data and isinstance(data["history"], list) and data["history"]:
                latest_history = data["history"][-1]
                routing_acc = latest_history.get(
                    "routing_accuracy_full", latest_history.get("routing_accuracy", 0.0)
                )
                routing_acc_keyword = latest_history.get("routing_accuracy", 0.0)
                latency = latest_history.get("median_latency_ms", 0.0)
                n_cases = latest_history.get("n_cases", 0)
                date = latest_history.get("date", last_updated)
                
                benchmarks_list = data.get("benchmarks", [])
                if isinstance(benchmarks_list, list) and benchmarks_list:
                    latest = benchmarks_list[-1]
                    m = latest.get("metrics", {})
                    return (
                        f"# 📊 Brain Health Dashboard (v{latest_version})\n\n"
                        f"## 🎯 Routing Benchmark\n"
                        f"• **Routing Accuracy (production):** {routing_acc:.2%}\n"
                        f"• **Routing Accuracy (keyword-only baseline):** {routing_acc_keyword:.2%}\n"
                        f"• **Median Latency:** {latency:.2f}ms\n"
                        f"• **Test Cases:** {n_cases}\n\n"
                        f"## ⚙️ Execution Telemetry\n"
                        f"• **Approval Rate:** {m.get('supervisor_approval_rate', 0):.0%}\n"
                        f"• **Logical Depth:** {m.get('logical_depth_score', 0)} steps/task\n"
                        f"• **Tool Efficiency:** {m.get('tool_efficiency_ratio', 0):.2f}\n"
                        f"• **Last Updated:** {date}\n"
                        f"• **Status:** {latest.get('status', 'unknown')}"
                    )
                else:
                    return (
                        f"# 📊 Brain Health Dashboard (v{latest_version})\n\n"
                        f"• **Routing Accuracy (production):** {routing_acc:.2%}\n"
                        f"• **Routing Accuracy (keyword-only baseline):** {routing_acc_keyword:.2%}\n"
                        f"• **Median Latency:** {latency:.2f}ms\n"
                        f"• **Test Cases:** {n_cases}\n\n"
                        f"• **Last Updated:** {date}\n"
                        f"• **Status:** active"
                    )
            
            benchmarks_list = data.get("benchmarks", [])
            if isinstance(benchmarks_list, list) and benchmarks_list:
                latest = benchmarks_list[-1]
        else:
            return f"ERROR: Unrecognized JSON structure type: {type(data).__name__}"

        if not latest or not isinstance(latest, dict):
            return "ERROR: Latest benchmark entry is not a valid object."
            
        m = latest.get("metrics", {})
        if not isinstance(m, dict):
            m = {}

        return (
            f"# 📊 Brain Health Dashboard (v{latest_version})\n\n"
            f"• **Approval Rate:** {m.get('supervisor_approval_rate', 0):.0%}\n"
            f"• **Logical Depth:** {m.get('logical_depth_score', 0)} steps/task\n"
            f"• **Tool Efficiency:** {m.get('tool_efficiency_ratio', 0):.2f}\n"
            f"• **Last Updated:** {last_updated}\n"
            f"• **Status:** {latest.get('status', 'unknown')}"
        )
    except Exception as e:
        return f"ERROR: Unexpected schema failure during parsing: {str(e)}"


@sovereign_tool()
def telemetry_integrity_audit(post_alert: bool = True) -> str:
    """Audits the Bayesian intelligence store for failure modes."""
    findings = []
    SEV_RANK = {"CRITICAL": 3, "WARNING": 2, "INFO": 1, "OK": 0}

    # ── 1. Store scan: simulated-batch, frozen priors, undecayed stale mass ──
    try:
        from tools.memory.postgres_client import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT tool_id, category, success_count, failure_count, last_updated FROM bayesian_weights")
                rows = cur.fetchall()

        now = datetime.now(timezone.utc)
        by_minute = {}
        frozen_symmetric = []
        stale_heavy = []
        for r in rows:
            s = int(r["success_count"] or 0)
            f = int(r["failure_count"] or 0)
            lu = r["last_updated"]
            total = s + f
            if lu is not None:
                if total >= 100:
                    key = str(lu)[:16]
                    by_minute.setdefault(key, 0)
                    by_minute[key] += 1
                try:
                    ts = lu if hasattr(lu, "tzinfo") else datetime.fromisoformat(str(lu))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    age_days = (now - ts).total_seconds() / 86400.0
                except Exception:
                    age_days = 0.0
            else:
                age_days = 9999.0
            if s == f and s >= 40:
                frozen_symmetric.append(f"{r['tool_id']}/{r['category']} ({s}S/{f}F)")
            if total >= 400 and age_days > 30:
                stale_heavy.append(f"{r['tool_id']}/{r['category']} ({total} runs, {age_days:.0f}d old)")

        big_batches = {k: n for k, n in by_minute.items() if n >= 15}
        if big_batches:
            worst = sorted(big_batches.items(), key=lambda x: -x[1])[:3]
            detail = ", ".join(f"{n} rows @ {k}" for k, n in worst)
            findings.append(("CRITICAL",
                f"Batch-injection signature: {len(big_batches)} timestamp(s) each mutate ≥15 rows at once ({detail}). "
                f"This is how simulate_bayesian_data.py fabricates data — verify these are real."))
        if frozen_symmetric:
            findings.append(("WARNING",
                f"{len(frozen_symmetric)} frozen symmetric prior(s) (never learned): {', '.join(frozen_symmetric[:6])}"
                + (" …" if len(frozen_symmetric) > 6 else "")))
        if stale_heavy:
            findings.append(("INFO",
                f"{len(stale_heavy)} heavy row(s) older than 30d (decay neutralises impact, but consider pruning): "
                + ", ".join(stale_heavy[:6]) + (" …" if len(stale_heavy) > 6 else "")))
        if not (big_batches or frozen_symmetric or stale_heavy):
            findings.append(("OK", f"Store clean: {len(rows)} rows, no injection/frozen/stale-mass signatures."))
    except Exception as e:
        findings.append(("WARNING", f"Could not scan intelligence store: {e}"))

    # ── 2. Backend / label sanity ──
    try:
        from tools.strategy.strategy_manager import governor
        governor._ensure_db()
        backend = "Local SQLite (remote unreachable!)" if governor.use_local else "Remote PostgreSQL"
        sev = "WARNING" if governor.use_local else "OK"
        findings.append((sev, f"Active backend: {backend}."))
    except Exception as e:
        findings.append(("WARNING", f"Could not determine governor backend: {e}"))

    # ── 3. Brain-health benchmark freshness ──
    try:
        candidates = [
            "/app/brain_health/BENCHMARKS.json",
            os.path.join(os.path.dirname(__file__), "../../../brain_health/BENCHMARKS.json"),
        ]
        candidates += glob.glob("/app/**/brain_health/BENCHMARKS.json", recursive=True)
        bpath = next((p for p in candidates if os.path.exists(p)), None)
        if bpath:
            with open(bpath) as fh:
                data = json.load(fh)
            hist = data.get("history", [])
            last_ts = hist[-1].get("timestamp") if hist else None
            if last_ts:
                ts = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age_days = (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0
                sev = "WARNING" if age_days > 14 else "OK"
                findings.append((sev, f"Brain-health benchmark last run {age_days:.0f}d ago ({last_ts})."
                                 + (" Re-run recommended." if age_days > 14 else "")))
            else:
                findings.append(("WARNING", "Brain-health benchmark file has no history entries."))
        else:
            findings.append(("INFO", "Brain-health benchmark file not found; cannot assess freshness."))
    except Exception as e:
        findings.append(("INFO", f"Could not read brain-health benchmark: {e}"))

    findings.sort(key=lambda x: -SEV_RANK.get(x[0], 0))
    top = findings[0][0] if findings else "OK"
    icon = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🔵", "OK": "🟢"}
    lines = [f"# 🛡️ Telemetry Integrity Audit — overall: {icon.get(top,'')} {top}\n"]
    for sev, msg in findings:
        lines.append(f"{icon.get(sev,'')} **{sev}** — {msg}")
    report = "\n".join(lines)

    if post_alert and SEV_RANK.get(top, 0) >= 2:
        try:
            from tools.memory.global_workspace import post_concept
            post_concept(
                concept=f"Telemetry integrity: {top} — {findings[0][1][:160]}",
                salience=0.9 if top == "CRITICAL" else 0.7,
                agent_id="telemetry_integrity_audit",
            )
            report += "\n\n_(alert posted to Global Workspace)_"
        except Exception as e:
            report += f"\n\n_(could not post workspace alert: {e})_"

    return report
