"""Swarm, orchestration, sovereignty, and dispatch routes.

Covers:
- POST /swarm/trigger          – kick off a research_implement workflow
- POST /orchestrate            – launch any orchestrator workflow (background)
- GET  /orchestrate/status     – poll a background orchestration job
- POST /swarm/sovereignty/sync – trigger autonomic regression analysis
- GET  /swarm/sovereignty/status – read recent sovereignty log
- POST /dispatch/claude        – send a task to the Claude Code CLI agent
- GET  /dispatch/p330/status   – ping the P330 worker
"""

import asyncio
import logging
import time
from collections import OrderedDict
import threading
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from tools.infrastructure.config import settings
from tools.infrastructure.server_deps import verify_authorization
from tools.infrastructure.orchestrator import orchestrate
from tools.audit.guardrail_agent import guardrail_agent
from tools.execution.claude_code_agent import claude_code_agent
from tools.execution.p330_worker import p330_worker
from tools.autonomic.autonomic_corrector import corrector

router = APIRouter()

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

project_root = settings.PROJECT_ROOT

ORCHESTRATE_WORKFLOWS = {
    "bug_fix",
    "code_review",
    "research_implement",
    "shadow_test",
    "design_ui",
    "wireframe",
}

_HTTP_ORCHESTRATE_JOBS: OrderedDict = OrderedDict()
_HTTP_ORCHESTRATE_JOBS_LOCK = threading.Lock()
_MAX_HTTP_ORCHESTRATE_JOBS = 50

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_http_orchestrate_job(
    job_id, workflow, task, file_path, project_path, code_snippet, tech_key,
    project_id=""
):
    try:
        result = orchestrate(
            workflow, task, file_path, project_path, code_snippet, tech_key,
            project_id
        )
        with _HTTP_ORCHESTRATE_JOBS_LOCK:
            if job_id in _HTTP_ORCHESTRATE_JOBS:
                _HTTP_ORCHESTRATE_JOBS[job_id].update(
                    status="completed", result=result
                )
    except Exception as e:
        logging.error(
            f"Orchestration job {job_id} failed: {e}", exc_info=True
        )
        with _HTTP_ORCHESTRATE_JOBS_LOCK:
            if job_id in _HTTP_ORCHESTRATE_JOBS:
                _HTTP_ORCHESTRATE_JOBS[job_id].update(
                    status="failed", error=str(e)
                )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/swarm/trigger", dependencies=[Depends(verify_authorization)])
async def trigger_swarm(payload: dict):
    objective = payload.get("objective")
    if not objective:
        return {"status": "error", "message": "No objective provided"}

    is_safe, risk_message = guardrail_agent.scan_objective(objective)
    if not is_safe:
        logging.warning(
            f"BLOCKED_SWARM_TRIGGER: {risk_message} | Objective: {objective}"
        )
        return {
            "status": "blocked",
            "message": "Security Violation: Potential Prompt Injection detected.",
            "details": risk_message,
        }

    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        None, lambda: orchestrate("research_implement", objective)
    )
    return {"status": "initiated", "objective": objective}


@router.post("/orchestrate", dependencies=[Depends(verify_authorization)])
async def run_orchestrate(payload: dict):
    """Launch an orchestrator workflow from the dashboard Run button.

    Body: {workflow, task, project_path?, file_path?, code_snippet?, tech_key?,
           project_id?}   project_id is the Planka project a wireframe belongs to.
    Always dispatches in the background and returns a job_id; poll
    GET /orchestrate/status/{job_id} for status + the final report.
    """
    workflow = (payload.get("workflow") or "").strip()
    task = (payload.get("task") or "").strip()

    if workflow not in ORCHESTRATE_WORKFLOWS:
        return {
            "status": "error",
            "message": f"Unknown workflow '{workflow}'. Valid: {sorted(ORCHESTRATE_WORKFLOWS)}",
        }
    if not task:
        return {"status": "error", "message": "No task provided"}

    # --- INJECTION GUARDRAIL --- (same gate as /swarm/trigger)
    is_safe, risk_message = guardrail_agent.scan_objective(task)
    if not is_safe:
        logging.warning(f"BLOCKED_ORCHESTRATE: {risk_message} | Task: {task}")
        return {
            "status": "blocked",
            "message": "Security Violation: Potential Prompt Injection detected.",
            "details": risk_message,
        }

    # Register the job, then dispatch the pipeline on the executor.
    job_id = uuid.uuid4().hex[:12]
    with _HTTP_ORCHESTRATE_JOBS_LOCK:
        _HTTP_ORCHESTRATE_JOBS[job_id] = {
            "status": "running",
            "workflow": workflow,
            "task": task,
            "result": None,
            "error": None,
        }
        while len(_HTTP_ORCHESTRATE_JOBS) > _MAX_HTTP_ORCHESTRATE_JOBS:
            _HTTP_ORCHESTRATE_JOBS.popitem(last=False)

    # An unreachable project_path is a hard error, never a substitution.
    #
    # This used to silently rewrite an absolute host path that doesn't exist in
    # the container (e.g. a Mac path like `/Users/.../eko-veritas-prod`) to ".",
    # which resolves to `/app` — Kenbun's OWN repo. The caller asked to review
    # project A and got a confident review of project B, with no error and only
    # an info-level log. Observed twice on 2026-08-11: a code_review that
    # scanned /app and a research_implement that emitted a patch for
    # `webhook/handler.py`, a Flask file that exists in neither project. The
    # guardrail and the adversarial court both APPROVED that patch, because
    # there was no real code in front of them to find fault with.
    #
    # Reviewing the wrong codebase is strictly worse than reviewing none: the
    # output is indistinguishable from a real result. Fail loudly instead.
    # An OMITTED project_path must stay omitted. This line used to read
    # `payload.get("project_path", ".") or "."`, and the MCP tool sends
    # `project_path: ""` whenever the caller does not set it — so `"" or "."`
    # produced ".", walking straight into the /app trap described above by a
    # different door. The earlier fix only covered unreachable ABSOLUTE paths;
    # the far more common case, a caller who passes code inline and never
    # mentions a project at all, still got Kenbun's own repo scanned and
    # reported as theirs.
    incoming_project_path = payload.get("project_path", "") or ""
    if incoming_project_path not in (".", ""):
        from pathlib import Path as _Path
        try:
            unreachable = (
                _Path(incoming_project_path).is_absolute()
                and not _Path(incoming_project_path).exists()
            )
        except OSError as _path_err:
            unreachable = True
            logging.warning(f"project_path check failed for "
                            f"'{incoming_project_path}': {_path_err}")
        if unreachable:
            logging.error(
                f"❌ /orchestrate: refusing job — project_path "
                f"'{incoming_project_path}' is not reachable from this container"
            )
            return JSONResponse(
                status_code=400,
                content={
                    "status": "rejected",
                    "error": "project_path_unreachable",
                    "project_path": incoming_project_path,
                    "detail": (
                        f"'{incoming_project_path}' does not exist inside the "
                        f"Kenbun container, so the requested code cannot be read. "
                        f"The job was NOT run: scanning a different repository "
                        f"would produce confident output about the wrong code. "
                        f"Pass a container-visible path, or send the source "
                        f"via code_snippet. Omitting project_path means 'no "
                        f"project' — the pipeline will then report that it had "
                        f"nothing to review rather than substituting a repo."
                    ),
                },
            )

    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        None,
        _run_http_orchestrate_job,
        job_id,
        workflow,
        task,
        payload.get("file_path", ""),
        incoming_project_path,
        payload.get("code_snippet", ""),
        payload.get("tech_key", ""),
        payload.get("project_id", ""),
    )

    return {
        "status": "initiated",
        "job_id": job_id,
        "workflow": workflow,
        "task": task,
    }


@router.get("/orchestrate/status/{job_id}")
async def orchestrate_status(job_id: str):
    """Poll the status / result of an HTTP-initiated orchestration job."""
    with _HTTP_ORCHESTRATE_JOBS_LOCK:
        job = _HTTP_ORCHESTRATE_JOBS.get(job_id)
        if job is None:
            return JSONResponse(
                status_code=404,
                content={"status": "not_found", "job_id": job_id},
            )
        return {
            "job_id": job_id,
            "status": job["status"],
            "workflow": job["workflow"],
            "task": job["task"],
            "result": job.get("result"),
            "error": job.get("error"),
        }


@router.post(
    "/swarm/sovereignty/sync",
    dependencies=[Depends(verify_authorization)],
)
async def trigger_sovereignty_sync():
    result = corrector.analyze_regressions()
    return result


@router.get("/swarm/sovereignty/status")
async def sovereignty_status():
    log_file = project_root / "brain_health" / "SOVEREIGNTY_LOG.md"
    recent_shifts = []
    if log_file.exists():
        with open(log_file, "r") as f:
            recent_shifts = f.readlines()[-20:]
    return {
        "active": True,
        "mode": "AUTONOMOUS",
        "last_sync": time.time(),
        "recent_log": [line.strip() for line in recent_shifts],
    }


@router.post(
    "/dispatch/claude", dependencies=[Depends(verify_authorization)]
)
async def dispatch_to_claude(payload: dict):
    task = payload.get("task", "")
    context_files = payload.get("context_files", [])
    if not task:
        return {"status": "error", "message": "No task provided"}

    if not claude_code_agent.is_available():
        return {
            "status": "unavailable",
            "message": (
                "Claude Code CLI not installed. "
                "Run: npm install -g @anthropic-ai/claude-code"
            ),
        }

    result = claude_code_agent.dispatch(
        task, context_files=context_files or None, print_output=False
    )
    return {
        "status": "success" if result.success else "error",
        "output": result.output,
        "duration_seconds": result.duration_seconds,
        "error": result.error,
    }


@router.get("/dispatch/p330/status")
async def p330_status():
    return p330_worker.ping()
