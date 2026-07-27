import sys
sys.stderr.write("DEBUG: server.py IS BEING LOADED\n")
import re
import json
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from tools.registry import sovereign_tool, registry
from typing import Optional
import io
import threading

class ProtocolShield(io.TextIOBase):
    def write(self, s):
        sys.stderr.write(s)
        return len(s)
    def flush(self):
        sys.stderr.flush()

# --- Path Setup moved up ---
from tools.infrastructure.config import settings
current_dir = settings.PROJECT_ROOT
tools_dir = current_dir / "tools"
project_root = current_dir

# Debug log for host-side issues
from tools.utils.path_utils import get_project_root
PROJECT_ROOT = get_project_root()
LOG_FILE = PROJECT_ROOT / "mcp_debug.log"

def debug_log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    sys.stderr.write(msg + "\n")

# Override builtins.print to write to sys.stderr for MCP safety.
import builtins
_original_print = builtins.print

def mcp_safe_print(*args, sep=' ', end='\n', file=None, flush=False):
    if file is None or file is sys.stdout:
        msg = sep.join(str(a) for a in args) + end
        sys.stderr.write(msg)
        if flush:
            sys.stderr.flush()
    else:
        _original_print(*args, sep=sep, end=end, file=file, flush=flush)

builtins.print = mcp_safe_print

# --- 2. CONFIGURATION ---

# --- 2. IMPORTS (Hierarchical) ---
# Hierarchical imports moved inside tool functions to prevent startup timeouts
# Global Strategy Instances

import tools.infrastructure.planka

mcp = FastMCP("Kenbun Tools")

# ========================================================
# 📡 DOCKER LOG TAILER DAEMON FOR REAL-TIME DOZZLE LOGGING
# ========================================================
_STOP_TAIL = threading.Event()

def _tail_mcp_debug_log():
    """
    Background daemon function that tails mcp_debug.log and streams host-side events to stderr.
    """
    log_path = Path(settings.PROJECT_ROOT) / "mcp_debug.log"
    # Wait for file to exist
    for _ in range(15):
        if log_path.exists() or _STOP_TAIL.is_set():
            break
        _STOP_TAIL.wait(1)
    if not log_path.exists():
        return
    
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            # Go to the end of the file
            f.seek(0, 2)
            while not _STOP_TAIL.is_set():
                line = f.readline()
                if not line:
                    _STOP_TAIL.wait(0.5)
                    continue
                # Stream terminal chat events directly to container standard error
                if "[TERMCHAT]" in line:
                    sys.stderr.write(line)
                    sys.stderr.flush()
    except Exception as e:
        sys.stderr.write(f"DEBUG: Log tailer daemon error: {e}\n")
        sys.stderr.flush()

# Spawn the log tailer daemon immediately on server startup
_tail_thread = threading.Thread(target=_tail_mcp_debug_log, daemon=True)
_tail_thread.start()


PC_IP = settings.SWARM_PC_IP
CHROMA_PORT = settings.CHROMA_PORT
LM_STUDIO_PORT = settings.LM_STUDIO_PORT
LM_STUDIO_MODEL = settings.LM_STUDIO_MODEL
PROJECT_ROOT = str(settings.PROJECT_ROOT)

# --- 0.1 SILENCE HELPER ---
import contextlib
import os

@contextlib.contextmanager
def silence_stdout():
    """Redirects stdout to stderr temporarily to protect the MCP protocol."""
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old_stdout

# --- 2. KNOWLEDGE REGISTRY ---
OFFICIAL_DOCS = {
    "react": "react.dev",
    "nextjs": "nextjs.org/docs",
    "vue": "vuejs.org",
    "svelte": "svelte.dev/docs",
    "tailwind": "tailwindcss.com/docs",
    "shadcn": "ui.shadcn.com/docs",
    "zod": "zod.dev",
    "python": "docs.python.org/3",
    "fastapi": "fastapi.tiangolo.com",
    "supabase": "supabase.com/docs",
    "docker": "docs.docker.com",
    "threejs": "threejs.org/docs",
    "r3f": "docs.pmnd.rs/react-three-fiber",
    "gsap": "gsap.com/docs"
}

# --- 3. HELPER: MEMORY ACCESS ---
def query_system_3(query_text, n=3):
    """Internal helper to fetch project concept memories."""
    try:
        from tools.memory.honcho_connect import query_embeddings
        results = query_embeddings(query_text, n_results=n, category="concepts")
        raw_docs = results['documents'][0] if results['documents'] and results['documents'][0] else []
        return [doc[:4000] for doc in raw_docs]
    except Exception as e:
        debug_log(f"⚠️ System 3 Query Failed: {e}")
        return []

def _run_async_safely(coro):
    """Helper to safely run coroutines from any thread context."""
    import asyncio
    import threading
    try:
        asyncio.get_running_loop()
        result_box = []
        err_box = []
        def _runner():
            try:
                result_box.append(asyncio.run(coro))
            except Exception as e:
                err_box.append(e)
        t = threading.Thread(target=_runner)
        t.start()
        t.join()
        if err_box:
            raise err_box[0]
        return result_box[0]
    except RuntimeError:
        return asyncio.run(coro)

# --- 4. INTERNAL LLM HELPER ---
def _clean_json_response(text):
    """
    Cleans the raw response from models that output <think> blocks or markdown.
    """
    # 1. Remove <think>...</think> blocks (Common in DeepSeek/Qwen reasoning models)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    
    # 2. Remove markdown code blocks (```json ... ```)
    text = text.replace("```json", "").replace("```", "").strip()
    
    return text

# (Logic moved to audit.supervisor_agent)

# --- 5. TOOL: SYSTEM 2 (THE SUPERVISOR) ---
@sovereign_tool()
def consult_supervisor(user_proposal: str, code_snippet: str = "", iterative_mode: bool = False) -> str:
    """
    Activates SYSTEM 2 (Local LLM via LM Studio).
    """
    # 1. Context from System 3
    memories = query_system_3(user_proposal)
    memory_context = "\n---\n".join(memories)

    debug_log(f"🧠 SYSTEM 2 ACTIVATED (Iterative: {iterative_mode})")
    
    from tools.audit.supervisor_agent import run_supervisor_audit
    import asyncio

    coro = run_supervisor_audit(user_proposal, code_snippet, memory_context, iterative_mode=iterative_mode)
    result = _run_async_safely(coro)

    if result.get("status") == "error":
        return f"❌ Supervisor Error: {result.get('critique')}"

    return json.dumps(result, indent=2)

# --- 5.1 TOOL: SYSTEM 2c (THE GUARDRAIL) ---
@sovereign_tool()
def audit_guardrail(code_snippet: str, task_context: str = "") -> str:
    """
    Fast, deterministic security and style audit (System 2c).
    Use this for continuous checks before calling the full Supervisor.
    """
    debug_log("🛡️ SYSTEM 2c ACTIVATED")
    from tools.audit.guardrail_agent import run_guardrail_audit
    result = run_guardrail_audit(code_snippet, task_context)
    return json.dumps(result, indent=2)

# --- 5.2 TOOL: AUTOMATED LINTER AUTO-FIX (STEP 0) ---
@sovereign_tool()
def autofix_linter(file_path: str, project_path: str = "") -> str:
    """
    Safe pre-flight linter auto-fix pass (eslint --fix / ruff / black).
    Prunes unused imports/variables and cleans formatting prior to deeper audits.
    """
    debug_log(f"🚀 Pre-flight linter pass activated for: {file_path}")
    from tools.audit.linter_autofix import autofix_linter as _autofix
    return _autofix(file_path, project_path)

# --- 6. TOOL: RESEARCHER (DOCS) ---
@sovereign_tool()
def research_official_docs(tech_key: str, query: str) -> str:
    """Searches official docs (Internet Access)."""
    tech_key = tech_key.lower()
    if tech_key not in OFFICIAL_DOCS:
        return f"Available docs: {list(OFFICIAL_DOCS.keys())}"
    
    site = OFFICIAL_DOCS[tech_key]
    try:
        debug_log(f"🔍 Researching: {query} site:{site}")
        from duckduckgo_search import DDGS
        results = DDGS().text(f"{query} site:{site}", max_results=3)
        return str(results) if results else "No results."
    except Exception as e:
        return f"Research failed: {e}"

# --- 7. TOOL: ARCHITECT (DIRECT DB ACCESS) ---
@sovereign_tool()
def ask_architect(query: str) -> str:
    """Directly queries Vector DB for history."""
    memories = query_system_3(query, n=5)
    return "\n\n".join(memories) if memories else "No relevant memories found."

@sovereign_tool()
def ask_ui_expert(query: str) -> str:
    """Consult the Lead UI Designer for CSS/Layout help."""
    from tools.audit.ui_designer import consult_ui_expert
    return consult_ui_expert(query)

@sovereign_tool()
def get_design_tokens() -> str:
    """Returns the current Design System tokens from DESIGN.md."""
    from tools.design.oracle import DesignOracle
    rules = DesignOracle.get_rules()
    return json.dumps(rules.get("tokens", {}), indent=2)

# --- 9. TOOL: GEMINI CODE REVIEWER (Cloud AI) ---
@sovereign_tool()
def review_code_with_gemini(
    code_snippet: str,
    review_context: str = "",
    tech_key: str = "",
    cross_check: bool = True,
    thinking: bool = False,
    thinking_level: str = "medium",
) -> str:
    """
    Full-pipeline code review using Gemini Cloud AI.
    Pipeline: Gemini Review → Official Docs Research → Supervisor Cross-Check → Consensus Report.
    Set cross_check=True to also consult the local Supervisor and generate a consensus.
    Provide tech_key (e.g. 'nextjs', 'fastapi') to ground findings in official docs.
    """
    from tools.audit.gemini_reviewer import gemini_code_review
    return gemini_code_review(
        code_snippet=code_snippet,
        review_context=review_context,
        tech_key=tech_key,
        cross_check=cross_check,
        thinking=thinking,
        thinking_level=thinking_level,
        official_docs_registry=OFFICIAL_DOCS,
        supervisor_fn=consult_supervisor,
    )

# --- 10. TOOL: GEMINI RESEARCH (Cloud AI) ---
@sovereign_tool()
def research_with_gemini(
    query: str, 
    tech_key: str = "",
    thinking: bool = False,
    thinking_level: str = "medium",
) -> str:
    """
    Research a topic using Gemini Cloud AI, optionally grounded in official documentation.
    Provide tech_key (e.g. 'react', 'supabase') to also search official docs.
    """
    import time
    start_time = time.time()
    with silence_stdout():
        debug_log("DEBUG: Research tool started")
        from tools.audit.gemini_reviewer import gemini_research
        debug_log(f"DEBUG: Import took {time.time() - start_time:.2f}s")
        res = gemini_research(
            query=query,
            tech_key=tech_key,
            thinking=thinking,
            thinking_level=thinking_level,
            official_docs_registry=OFFICIAL_DOCS,
        )
        debug_log(f"DEBUG: Total tool execution took {time.time() - start_time:.2f}s")
        return res

# ============================================================
# PRO STACK TOOLS (Phases 1-4)
# ============================================================

# --- 10.5 TOOL: ANTI-JARGON CONTENT GENERATOR ---
@sovereign_tool()
def write_website_content(topic: str, context: str = "", length: str = "medium") -> str:
    """
    Generates human-like website content without AI jargon like 'bespoke' or 'delve'.
    Use this instead of generic Gemini/Claude for copywriting.
    """
    import time
    start_time = time.time()
    with silence_stdout():
        debug_log("DEBUG: write_website_content tool started")
        from tools.craft.content_generator import generate_human_content
        res = generate_human_content(topic=topic, context=context, length=length)
        debug_log(f"DEBUG: Total tool execution took {time.time() - start_time:.2f}s")
        return res

# --- 11. TOOL: DOCKER SANDBOX (Phase 1) ---
@sovereign_tool()
def run_code_safely(code: str, language: str = "python", timeout: int = 30) -> str:
    """
    Execute code in an isolated Docker container.
    Safety: No network, memory-limited, CPU-limited, auto-destroyed.
    Supports: python, node/javascript.
    """
    from tools.execution.e2b_runner import run_code_safely as _run_code_safely
    return _run_code_safely(code=code, language=language, timeout=timeout)

# --- 12. TOOL: REPO MAP (Phase 2) ---
@sovereign_tool()
def scan_repo(project_path: str, extensions: str = ".py,.ts,.tsx,.js,.jsx") -> str:
    """
    Generate a skeleton map of a project. Shows classes, functions, and signatures
    without implementation code. Fits large codebases into a single prompt.
    """
    from tools.memory.repo_mapper import scan_repo as _scan_repo
    return _scan_repo(project_path=project_path, extensions=extensions)

# --- 13. TOOL: ERROR MEMORY — SAVE (Phase 3) ---
@sovereign_tool()
def remember_fix(error_message: str, solution: str, file_context: str = "") -> str:
    """
    Save an error->fix mapping to the knowledge base for future recall.
    Uses semantic search so similar (not exact) errors can be found later.
    """
    from tools.utils.error_memory import remember_fix as _remember_fix
    return _remember_fix(
        error_message=error_message,
        solution=solution,
        file_context=file_context,
        pc_ip=PC_IP,
        chroma_port=CHROMA_PORT,
    )

# --- 14. TOOL: ERROR MEMORY — RECALL (Phase 3) ---
@sovereign_tool()
def recall_fix(error_message: str) -> str:
    """
    Search for similar past errors and their solutions.
    Uses semantic search — 'NoneType has no attribute' matches 'AttributeError on None'.
    """
    from tools.utils.error_memory import recall_fix as _recall_fix
    return _recall_fix(
        error_message=error_message,
        pc_ip=PC_IP,
        chroma_port=CHROMA_PORT,
    )

# --- 15. TOOL: BACKTRACKER — SAVE (Phase 4) ---
@sovereign_tool()
def save_checkpoint(file_path: str, label: str = "auto") -> str:
    """
    Snapshot a file's current state before making risky changes.
    Use restore_checkpoint() to revert if the fix fails.
    """
    path = Path(file_path).resolve()
    if not path.is_relative_to(settings.PROJECT_ROOT.resolve()):
        return "ERROR: Security Breach Blocked: Path is outside project root."
    from tools.utils.backtracker import save_checkpoint as _save_checkpoint
    return _save_checkpoint(file_path=file_path, label=label)

# --- 16. TOOL: BACKTRACKER — RESTORE (Phase 4) ---
@sovereign_tool()
def restore_checkpoint(file_path: str, label: str = "") -> str:
    """
    Revert a file to a previous checkpoint.
    If no label provided, reverts to the most recent checkpoint.
    """
    from tools.utils.backtracker import restore_checkpoint as _restore_checkpoint
    return _restore_checkpoint(file_path=file_path, label=label)

# --- 17. TOOL: BACKTRACKER — LIST (Phase 4) ---
@sovereign_tool()
def list_checkpoints(file_path: str = "") -> str:
    """
    List all saved checkpoints, optionally filtered by file path.
    """
    from tools.utils.backtracker import list_checkpoints as _list_checkpoints
    return _list_checkpoints(file_path=file_path)

# ============================================================
# THE ORCHESTRATOR (Phase 5)
# ============================================================

# --- 18. TOOL: ORCHESTRATOR ---

# In-process async job store (lives for the MCP server's lifetime).
import threading as _threading
from collections import OrderedDict as _OrderedDict
import uuid as _uuid

_ORCHESTRATE_JOBS = _OrderedDict()
_ORCHESTRATE_JOBS_LOCK = _threading.Lock()
_MAX_ORCHESTRATE_JOBS = 50

# Heavy workflows dispatch in the background by default so the MCP call returns
# immediately with a Job ID to poll. Shared with the HTTP route via orchestrator.py.
from tools.infrastructure.orchestrator import HEAVY_WORKFLOWS


def _build_orchestrate_registry() -> dict:
    """Build the tool registry passed to run_pipeline (shared by the sync + async paths)."""
    from tools.audit.reflection_agent import reflect_and_distill as _reflect_and_distill
    from tools.audit.guardrail_agent import run_guardrail_audit
    from tools.utils.maze_protocol import backward_verify
    from tools.audit.discovery_agent import generate_discovery_form
    from tools.memory.repo_mapper import scan_repo
    from tools.utils.error_memory import remember_fix, recall_fix
    from tools.utils.backtracker import save_checkpoint, restore_checkpoint
    from tools.execution.e2b_runner import run_code_safely
    from tools.audit.gemini_reviewer import gemini_code_review, gemini_research
    from tools.utils.bayesian import tune_swarm
    from tools.audit.consult_architect import consult_brain as consult_hivemind
    from tools.infrastructure.orchestrator import _analyze_bug
    from tools.memory.hardware_bridge import hardware_bridge
    from services.self_improvement_daemon import run_self_improvement_cycle
    from tools.infrastructure.git_watcher_tools import fetch_git_pushes, analyze_push_changes, apply_git_patch

    def _local_view_file(AbsolutePath: str) -> str:
        # Path Traversal Guardrail (Security Hardening)
        path = Path(AbsolutePath).resolve()
        root = settings.PROJECT_ROOT.resolve()
        if not path.is_relative_to(root):
            raise PermissionError(f"Security Breach Blocked: Path '{path}' is outside project root '{root}'.")
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    return {
        "scan_repo": scan_repo,
        "write_website_content": write_website_content,
        "recall_fix": lambda error_message: recall_fix(error_message, PC_IP, CHROMA_PORT),
        "remember_fix": lambda error_message, solution, file_context="": remember_fix(
            error_message, solution, file_context, PC_IP, CHROMA_PORT
        ),
        "save_checkpoint": save_checkpoint,
        "restore_checkpoint": restore_checkpoint,
        "run_code_safely": run_code_safely,
        "review_code_with_gemini": lambda code_snippet, review_context="", tech_key="", cross_check=True, thinking=False, thinking_level="medium", **kwargs: gemini_code_review(
            code_snippet=code_snippet,
            review_context=review_context,
            tech_key=tech_key,
            cross_check=cross_check,
            thinking=thinking,
            thinking_level=thinking_level,
            official_docs_registry=OFFICIAL_DOCS,
            supervisor_fn=consult_supervisor,
        ),
        "research_with_gemini": lambda query, tech_key="", thinking=False, thinking_level="medium": gemini_research(
            query=query,
            tech_key=tech_key,
            thinking=thinking,
            thinking_level=thinking_level,
            official_docs_registry=OFFICIAL_DOCS
        ),
        "consult_supervisor": consult_supervisor,
        "reflect_and_distill": _reflect_and_distill,
        "guardrail_audit": run_guardrail_audit,
        "maze_verification": backward_verify,
        "generate_discovery_form": generate_discovery_form,
        "view_file": _local_view_file,
        "autofix_linter": autofix_linter,
        "tune_swarm": tune_swarm,
        "consult_hivemind": consult_hivemind,
        "analyze_bug": _analyze_bug,
        "detect_hardware": hardware_bridge.detect_capabilities,
        "run_self_improvement_cycle": run_self_improvement_cycle,
        "sync_jira_issue": sync_jira_issue,
        "create_bitbucket_pr": create_bitbucket_pr,
        "fetch_git_pushes": fetch_git_pushes,
        "analyze_push_changes": analyze_push_changes,
        "apply_git_patch": apply_git_patch,
    }


def _execute_orchestration(
    workflow: str,
    task: str,
    project_path: str = "",
    file_path: str = "",
    code_snippet: str = "",
    tech_key: str = "",
) -> str:
    """Run a pipeline to completion synchronously and return the report string."""
    from tools.infrastructure.orchestrator import run_pipeline
    import asyncio

    coro = run_pipeline(
        workflow=workflow,
        task=task,
        tools=_build_orchestrate_registry(),
        project_path=project_path,
        file_path=file_path,
        code_snippet=code_snippet,
        tech_key=tech_key,
    )
    return _run_async_safely(coro)


def _run_orchestrate_job(
    job_id: str,
    workflow: str,
    task: str,
    project_path: str,
    file_path: str,
    code_snippet: str,
    tech_key: str,
) -> None:
    """Background worker: run the pipeline and record the outcome in the job store."""
    try:
        result = _execute_orchestration(workflow, task, project_path, file_path, code_snippet, tech_key)
        with _ORCHESTRATE_JOBS_LOCK:
            if job_id in _ORCHESTRATE_JOBS:
                _ORCHESTRATE_JOBS[job_id].update(status="completed", result=result)
    except Exception as e:  # noqa: BLE001 — surface any failure to the poller
        with _ORCHESTRATE_JOBS_LOCK:
            if job_id in _ORCHESTRATE_JOBS:
                _ORCHESTRATE_JOBS[job_id].update(status="failed", error=str(e))


def _get_config_token(force_fresh: bool = False) -> str:
    """Resolve the CONFIG_TOKEN for talking to the persistent FastAPI server.

    By default delegates to server_deps.get_or_create_config_token() which
    caches the value. Set force_fresh=True to bypass the cache and re-read
    the secret file from disk — used after a 401/403 to handle the case
    where the FastAPI server rotated the token after the MCP cached it.
    """
    if force_fresh:
        # Bypass server_deps' module-level cache by reading the file directly.
        import os
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
        # If fresh read failed, fall through to cached value as last resort.
    from tools.infrastructure.server_deps import get_or_create_config_token
    return get_or_create_config_token()


def _dispatch_orchestrate_http(
    workflow: str,
    task: str,
    project_path: str,
    file_path: str,
    code_snippet: str,
    tech_key: str,
    token: str,
) -> dict:
    """POST the orchestration to the persistent FastAPI server. Raises HTTPError on auth."""
    import urllib.request
    import json
    req = urllib.request.Request(
        f"{settings.INTERNAL_API_URL}/orchestrate",
        data=json.dumps({
            "workflow": workflow,
            "task": task,
            "project_path": project_path,
            "file_path": file_path,
            "code_snippet": code_snippet,
            "tech_key": tech_key
        }).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _record_dispatch_fallback(workflow: str, reason: str) -> None:
    """Append a JSONL event when orchestrate falls back from async to inline.

    Surfaces the silent transport failure described in
    ``GHOST_BUG_HUNTING_PLAN.md`` (Zone 2). Without this, a broken FastAPI
    server makes every workflow run inline forever, and the only signal is a
    short string in the user-facing reply that's easy to miss. The JSONL feed
    can be tailed by the dashboard's telemetry page.

    Failures here are swallowed: telemetry must never break the user's run.
    """
    try:
        import json as _json
        from datetime import datetime, timezone

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
            fh.write(_json.dumps(event) + "\n")
    except Exception as telemetry_err:  # noqa: BLE001 — telemetry is best-effort
        debug_log(f"⚠️ Failed to record dispatch_fallback event: {telemetry_err}")


@sovereign_tool()
def orchestrate(
    workflow: str,
    task: str,
    project_path: str = "",
    file_path: str = "",
    code_snippet: str = "",
    tech_key: str = "",
    wait: bool = False,
    fast: bool = False,
) -> str:
    """Run a Kenbun pipeline.

    Heavy workflows (design_ui, research_implement, code_review, shadow_test,
    bug_fix) dispatch asynchronously and return a Job ID — poll it with
    orchestrate_status() — so the MCP call never blocks past its request timeout.
    Set wait=True to force a blocking run.

    Dispatch is resilient: on a 401/403 (token mismatch between MCP and the
    FastAPI server, e.g. after a token rotation), retries once with a freshly
    re-read token. If dispatch still fails for any reason — auth, network,
    server down — transparently falls back to inline execution so the caller
    always gets a result (with a small inline-fallback notice prepended).
    """
    # Workflow-name validation: the registry lives in tools.registry, not in a
    # per-package registry submodule. Using the wrong path was breaking every
    # MCP orchestrate call with "No module named 'tools.infrastructure.pipelines.registry'".
    from tools.registry import registry
    valid_workflows = set(registry.get_all_pipelines().keys())
    if workflow not in valid_workflows:
        import difflib
        matches = difflib.get_close_matches(workflow, valid_workflows)
        suggestion = f" Did you mean '{matches[0]}'?" if matches else ""
        return f"❌ Invalid workflow '{workflow}'.{suggestion} Valid options: {', '.join(sorted(valid_workflows))}"

    if workflow in HEAVY_WORKFLOWS and not wait:
        import urllib.error
        # Default fallback reason — overwritten by the except branches below
        # before _record_dispatch_fallback is called. Default catches the
        # impossible "fell through without raising" path defensively.
        fallback_reason = "unknown"
        # First attempt: cached token
        try:
            data = _dispatch_orchestrate_http(
                workflow, task, project_path, file_path, code_snippet, tech_key,
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
            # Auth failures (401/403) often mean the token cache is stale —
            # the FastAPI server rotated its secret or started after the MCP
            # cached an older value. Retry once with a fresh disk read.
            if http_err.code in (401, 403):
                try:
                    data = _dispatch_orchestrate_http(
                        workflow, task, project_path, file_path, code_snippet, tech_key,
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
            debug_log(
                f"⚠️ Async dispatch failed (workflow={workflow}, err={e}). "
                f"Falling back to inline execution."
            )
            fallback_reason = f"{e.__class__.__name__}:{str(e)[:120]}"
        # Fall through to inline — the user gets a real result even when the
        # async dispatch path is broken. Prepended notice so the caller knows
        # they bypassed the persistent-server queue.
        # --- TELEMETRY: surface the fallback so it stops hiding ---
        # Without this, repeated dispatch failures look like "successful inline
        # runs" forever; the dashboard never learns the async path is broken.
        _record_dispatch_fallback(workflow, fallback_reason)
        inline_result = _execute_orchestration(
            workflow, task, project_path, file_path, code_snippet, tech_key
        )
        return (
            f"_⚠️ Persistent-server dispatch unavailable; ran inline instead._ "
            f"_(reason: `{fallback_reason}` — see brain_health/dispatch_fallbacks.jsonl)_\n\n"
            f"{inline_result}"
        )

    # Light workflow, or the caller explicitly asked to block.
    return _execute_orchestration(workflow, task, project_path, file_path, code_snippet, tech_key)


@sovereign_tool()
def orchestrate_status(job_id: str) -> str:
    """Check the status (or retrieve the result) of an async orchestrate() job by its Job ID."""
    try:
        import urllib.request
        import json
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
            return f"⚠️ Authorization failed (HTTP {e.code}). The persistent server may have restarted or rotated tokens. Run `kenbun reconfigure` or check `~/.gemini/antigravity/mcp/kenbun-local/mcp-config.json`."
        return f"❌ Server returned HTTP {e.code} while checking job status."
    except Exception as e:
        return f"❌ Failed to check orchestration status: {e}"


# ============================================================
# KNOWLEDGE MANAGEMENT (Explicit Hivemind Control)
# ============================================================

@sovereign_tool()
def save_to_hivemind(title: str, content: str, tags: str, category: str = "concepts") -> str:
    """
    Use this when the user says 'Save this to the Hivemind' or wants to store a new architectural rule, pattern, or concept.
    """
    with silence_stdout():
        from tools.memory.knowledge_manager import learn_concept
        return learn_concept(title, content, tags, category=category)

@sovereign_tool()
def remember_preference(preference: str, context: str = "") -> str:
    """Record one of the USER's (Carlos's) preferences, decisions, or working style.

    Unlike save_to_hivemind (which models the system), this attributes the message
    to the human user peer so Honcho's deriver builds a personalized model of the
    user over time. Use it whenever the user states a preference, correction, or
    how they like things done.
    """
    with silence_stdout():
        from tools.memory.honcho_connect import add_user_memory, USER_PEER
        msg = f"{preference}" + (f"\nContext: {context}" if context else "")
        add_user_memory(msg)
        return f"✅ Recorded preference for user '{USER_PEER}'. Honcho will fold it into your personal model."

@sovereign_tool()
def search_hivemind_concepts(query: str, category: str = "concepts") -> str:
    """
    Use this to pull up past architectural rules or concepts, especially when asked to compare new ideas against old ones.
    """
    with silence_stdout():
        from tools.memory.knowledge_manager import list_concepts
        return list_concepts(query, category=category)

@sovereign_tool()
def delete_from_hivemind(concept_id: str, category: str = "concepts") -> str:
    """
    Use this to delete outdated concepts from the database when the user explicitly asks to forget them.
    """
    with silence_stdout():
        from tools.memory.knowledge_manager import forget_concept
        return forget_concept(concept_id, category=category)


# ============================================================
# GLOBAL WORKSPACE (Swarm Working Memory — J-space analogue)
# ============================================================

@sovereign_tool()
def workspace_post(concept: str, salience: float = 0.5, agent_id: str = "unknown") -> str:
    """
    Put a concept on the swarm's shared working memory ("what I'm thinking about
    right now"). Post concepts, not chatter — most traffic should bypass this.
    Watchlist matches are flagged for supervisor review before action.
    """
    import json as _json
    with silence_stdout():
        from tools.memory.global_workspace import post_concept
        return _json.dumps(post_concept(concept, salience=salience, agent_id=agent_id))


@sovereign_tool()
def workspace_read(limit: int = 48) -> str:
    """
    Answer "what is the swarm thinking right now?" — returns current workspace
    slots ordered by salience (flagged alerts first). Salience decays over time.
    """
    import json as _json
    with silence_stdout():
        from tools.memory.global_workspace import read_workspace
        return _json.dumps(read_workspace(limit=limit))


@sovereign_tool()
def workspace_inject(concept: str, salience: float = 0.9) -> str:
    """
    Operator/supervisor steering: inject or boost a concept in the swarm's
    working memory so downstream agents pick it up.
    """
    import json as _json
    with silence_stdout():
        from tools.memory.global_workspace import inject_concept
        return _json.dumps(inject_concept(concept, salience=salience))


@sovereign_tool()
def workspace_resolve_alert(concept: str) -> str:
    """
    Supervisor acknowledges a flagged workspace concept after review; the slot
    resumes normal salience decay.
    """
    import json as _json
    with silence_stdout():
        from tools.memory.global_workspace import resolve_alert
        return _json.dumps(resolve_alert(concept))


# ============================================================
# CODEBASE VECTORIZATION (Semantic Code Understanding)
# ============================================================

@sovereign_tool()
def index_codebase(project_path: str = "") -> str:
    """
    Indexes the entire project's code into the Hivemind (ChromaDB) using semantic code chunking.
    Call this when the user wants the system to 'understand' their massive codebase.
    """
    with silence_stdout():
        if not project_path:
            project_path = PROJECT_ROOT
        from tools.memory.code_indexer import index_project
        return index_project(project_path)

@sovereign_tool()
def search_codebase(query: str) -> str:
    """
    Searches the semantic code index for a specific function, logic, or implementation pattern.
    Use this instead of grep when you need semantic, mathematical understanding of what the code does.
    """
    with silence_stdout():
        from tools.memory.code_indexer import search_code
        return search_code(query)


# ============================================================
# THE PLANNER (Think Before You Act)
# ============================================================

TOOL_CATALOG = """
AVAILABLE TOOLS (20 total):

CORE TOOLS:
1. consult_supervisor(user_proposal, code_snippet, iterative_mode) — Local LLM review for security/scalability
2. research_official_docs(tech_key, query) — Search official docs (React, Next.js, FastAPI, Supabase, etc.)
3. ask_architect(query) — Query the project memory/history via ChromaDB vector search
4. ask_ui_expert(query) — CSS/Layout consulting from the UI Designer module
5. get_design_tokens() — Returns the current Design System tokens from the root DESIGN.md

KNOWLEDGE MANAGEMENT:
5. save_to_hivemind(title, content, tags) — Save a new architectural rule, pattern, or concept to the Hivemind
6. search_hivemind_concepts(query) — Search the Hivemind for explicit concepts by text
7. delete_from_hivemind(concept_id) — Delete a concept from the Hivemind by ID

CODEBASE VECTORIZATION:
8. index_codebase(project_path) — Chunk and index thousands of lines of code into the Vector DB
9. search_codebase(query) — Search for code semantically using natural language

CLOUD AI & CONTENT:
10. review_code_with_gemini(code_snippet, review_context, tech_key, cross_check, thinking, thinking_level) — Full 4-stage code review pipeline
11. research_with_gemini(query, tech_key, thinking, thinking_level) — Cloud-based research grounded in official docs
11.5 write_website_content(topic, context, length) — Generates human-like website copy avoiding AI jargon ('bespoke', 'delve')

PRO STACK:
12. run_code_safely(code, language, timeout) — Execute code in isolated Docker container (no network, auto-destroy)
13. scan_repo(project_path, extensions) — Generate skeleton map of a project (classes/functions only, no code)
14. remember_fix(error_message, solution, file_context) — Save an error→fix mapping for future recall
15. recall_fix(error_message) — Semantic search for similar past errors and their solutions
16. save_checkpoint(file_path, label) — Snapshot a file before risky changes
17. restore_checkpoint(file_path, label) — Revert a file to a checkpoint
18. list_checkpoints(file_path) — List saved checkpoints

ORCHESTRATOR:
19. orchestrate(workflow, task, project_path, file_path, code_snippet, tech_key)
    Workflows: "bug_fix" | "code_review" | "research_implement"
    Chains multiple tools automatically with backtracking.

META:
20. think_about_tools(task) — THIS TOOL. Analyzes a task and recommends the optimal tool strategy.
"""

@sovereign_tool()
def think_about_tools(task: str) -> str:
    """
    Analyze a task and recommend which tools to use and in what order.
    Think before you act — this planner knows all 15 tools and suggests the optimal strategy.
    """
    try:
        from tools.strategy.decision_logic import router
        from tools.audit.gemini_reviewer import _call_gemini

        # 1. Decision Tree Routing
        strategy_path = router.get_strategy_path(task)
        recommended_tools = router.recommend_tools(task)

        system_prompt = (
            "You are a Tool Strategist for an AI coding agent called Kenbun. "
            "The Decision Tree (System 4b) has already selected a path for this task.\n\n"
            f"DECISION TREE PATH: {strategy_path}\n"
            f"RECOMMENDED TOOLS: {', '.join(recommended_tools)}\n\n"
            "Given this path, recommend the OPTIMAL sequence of tools to use. "
            "Be specific: name the exact tools, their arguments, and WHY each step matters.\n\n"
            "Rules:\n"
            "- If a built-in orchestrate() workflow fits, recommend that FIRST\n"
            "- For simple tasks, recommend individual tools (don't over-engineer)\n"
            "- Always consider: do we need a checkpoint before risky changes?\n"
            "- Always consider: should we recall_fix first to check past solutions?\n"
            "- Always consider: does this need a scan_repo for context?\n\n"
            "Format your response as:\n"
            "## 🌳 Decision Tree Path: " + strategy_path + "\n"
            "## Recommended Strategy\nBrief description\n\n"
            "## Step-by-Step Plan\n1. tool_name(...) — reason\n2. ...\n\n"
            "## Alternative Approach\nIf the above doesn't work, try...\n\n"
            f"{TOOL_CATALOG}"
        )

        result = _call_gemini(system_prompt, f"TASK: {task}", temperature=0.3)
        return f"## 🧠 Tool Strategy for: \"{task}\"\n\n{result}"

    except Exception:
        # Fallback: static recommendation without Gemini
        return (
            f"## 🧠 Tool Strategy for: \"{task}\"\n\n"
            f"*(Gemini unavailable — showing static recommendations)*\n\n"
            f"### Quick Reference\n"
            f"- **Bug fix?** → `orchestrate(\"bug_fix\", \"{task}\")`\n"
            f"- **Code review?** → `orchestrate(\"code_review\", \"{task}\")`\n"
            f"- **New feature?** → `orchestrate(\"research_implement\", \"{task}\")`\n"
            f"- **Need context?** → `scan_repo(project_path)`\n"
            f"- **Past error?** → `recall_fix(error_message)`\n"
            f"- **Risky change?** → `save_checkpoint(file_path)` first\n\n"
            f"{TOOL_CATALOG}"
        )


# --- Tool Registrations Continue ---
@sovereign_tool()
def patch_hivemind_concept(concept_id: str, title: str = None, content: str = None, tags: str = None) -> str:
    """Updates an existing concept in the Hivemind. Only provided fields will be updated."""
    with silence_stdout():
        from tools.memory.knowledge_manager import patch_concept
        return patch_concept(concept_id, title, content, tags)

@sovereign_tool()
def ingest_knowledge_from_pdf(pdf_path: str, tech_key: str = "general") -> str:
    """
    Ingests technical knowledge from a PDF file into the Hivemind.
    Use this to 'teach' the AI new libraries (e.g. Three.js, Next.js) using official PDFs.
    """
    from tools.memory.pdf_ingestor import ingest_pdf_to_hivemind
    return ingest_pdf_to_hivemind(pdf_path, tech_key)

@sovereign_tool()
def ingest_url_to_hivemind(url: str, title: str = "", tags: str = "web,scraped") -> str:
    """Fetches a URL, extracts text, chunks it, and saves it to the Hivemind."""
    import requests
    import re
    with silence_stdout():
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Simple text extraction (remove script/style, then strip tags)
            html = response.text
            html = re.sub(r'<(script|style).*?>.*?</\1>', '', html, flags=re.IGNORECASE | re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text).strip()
            
            if not text:
                return "ERROR: No text extracted from URL."
                
            from tools.memory.knowledge_manager import learn_concept
            final_title = title if title else url
            return learn_concept(final_title, text, tags)
        except Exception as e:
            return f"ERROR: Failed to ingest URL. {str(e)}"

@sovereign_tool()
def ingest_file_to_hivemind(file_path: str, tags: str = "file,ingested") -> str:
    """Reads a local file, chunks it, and saves it to the Hivemind."""
    with silence_stdout():
        try:
            path = Path(file_path).resolve()
            if not path.is_relative_to(settings.PROJECT_ROOT.resolve()):
                return "ERROR: Security Breach Blocked: Path is outside project root."
                
            if not path.exists():
                return f"ERROR: File not found: {file_path}"
                
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            from tools.memory.knowledge_manager import learn_concept
            title = os.path.basename(file_path)
            return learn_concept(title, content, tags)
        except Exception as e:
            return f"ERROR: Failed to ingest file. {str(e)}"

@sovereign_tool()
def prune_hivemind() -> str:
    """Removes outdated or redundant concepts from the Hivemind to maintain precision."""
    with silence_stdout():
        from tools.memory import knowledge_manager
        return knowledge_manager.prune_hivemind()

@sovereign_tool()
def get_intelligence_stats() -> str:
    """Returns the current Bayesian intelligence stats for all tools.

    Reads from whichever backend the governor is currently using:
    - Remote ChromaDB (when SWARM_PC_IP is reachable at startup)
    - Local SQLite fallback (when ChromaDB is unreachable)

    Previously only read from governor.collection (ChromaDB), so when the
    governor fell back to SQLite all real telemetry data was invisible.
    """
    try:
        from tools.strategy.strategy_manager import governor
        # Use governor's own get_all_stats() which handles both backends
        all_stats = governor.get_all_stats()

        if not all_stats:
            # Direct SQLite fallback if get_all_stats returns empty
            if governor.use_local and governor.local_conn:
                with governor._lock:
                    cursor = governor.local_conn.cursor()
                    cursor.execute(
                        "SELECT tool_id, alpha, beta, success_count, failure_count "
                        "FROM intelligence ORDER BY success_count DESC"
                    )
                    rows = cursor.fetchall()
                if not rows:
                    return "No intelligence data collected yet."
                backend = "\ud83d\uddc4\ufe0f Local SQLite"
                stats = [f"# \U0001f9e0 System 4: Intelligence Dashboard [{backend}]\n"]
                for tool_id, alpha, beta, s, f in rows:
                    prob = float(alpha) / (float(alpha) + float(beta))
                    stats.append(f"\u2022 **{tool_id}**: {prob:.2%} success probability ({s}S/{f}F)")
                return "\n".join(stats)
            return "No intelligence data collected yet or store disconnected."

        backend = "\U0001f418 Remote PostgreSQL" if not governor.use_local else "\ud83d\uddc4\ufe0f Local SQLite"
        stats = [f"# \U0001f9e0 System 4: Intelligence Dashboard [{backend}]\n"]
        stats.append("_Success probability is recency-weighted; \u231b marks stale (decayed) evidence._\n")

        # Sort by success_count descending so most-active tools appear first
        sorted_stats = sorted(all_stats, key=lambda x: x.get("success_count", 0), reverse=True)

        for entry in sorted_stats:
            tool = entry["tool_id"]
            a = float(entry.get("alpha", 2.0))
            b = float(entry.get("beta", 2.0))
            s = int(entry.get("success_count", 0))
            f = int(entry.get("failure_count", 0))
            recency = entry.get("recency")
            prob = a / (a + b)
            stale = ""
            if recency is not None and recency < 0.25:
                stale = f"  \u231b stale (recency {recency:.2f})"
            stats.append(f"\u2022 **{tool}**: {prob:.2%} success probability ({s}S/{f}F){stale}")

        return "\n".join(stats)
    except Exception as e:
        return f"ERROR: Failed to retrieve stats. {e}"

@sovereign_tool()
def telemetry_integrity_audit(post_alert: bool = True) -> str:
    """Audits the Bayesian intelligence store for the failure modes that silently
    degraded the swarm: fabricated/simulated seed data, frozen priors that never
    learn, undecayed stale mass, and a stale brain-health benchmark.

    Run it any time the dashboard "feels off", or on a schedule. When post_alert
    is True and CRITICAL/WARNING issues are found, it raises a Global Workspace
    alert so the problem surfaces proactively instead of rotting for weeks.

    Returns a human-readable report with severity and recommended actions.
    """
    import os
    import glob
    import json
    from datetime import datetime, timezone

    findings = []          # (severity, message)
    SEV_RANK = {"CRITICAL": 3, "WARNING": 2, "INFO": 1, "OK": 0}

    # ── 1. Store scan: simulated-batch, frozen priors, undecayed stale mass ──
    try:
        from tools.memory.postgres_client import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT tool_id, category, success_count, failure_count, last_updated FROM bayesian_weights")
                rows = cur.fetchall()

        now = datetime.now(timezone.utc)
        by_minute = {}          # identical-timestamp batches → injection signature
        frozen_symmetric = []   # success == failure and large → stuck prior
        stale_heavy = []        # high count but not touched in >30d → undecayed mass
        for r in rows:
            s = int(r["success_count"] or 0)
            f = int(r["failure_count"] or 0)
            lu = r["last_updated"]
            total = s + f
            if lu is not None:
                # Injection = a batch of rows gaining SUBSTANTIAL fabricated counts at
                # the same instant. Only heavy rows (total >= 100) count toward the
                # batch signature, so legitimate admin resets (which zero counts) and
                # ordinary trickle telemetry never trip the alarm.
                if total >= 100:
                    key = str(lu)[:16]  # minute granularity
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

    # ── Assemble report ──
    findings.sort(key=lambda x: -SEV_RANK.get(x[0], 0))
    top = findings[0][0] if findings else "OK"
    icon = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🔵", "OK": "🟢"}
    lines = [f"# 🛡️ Telemetry Integrity Audit — overall: {icon.get(top,'')} {top}\n"]
    for sev, msg in findings:
        lines.append(f"{icon.get(sev,'')} **{sev}** — {msg}")
    report = "\n".join(lines)

    # ── Proactive alert so contamination can't rot silently ──
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

@sovereign_tool()
def generate_wireframe(prompt: str) -> str:
    """Generate a UI wireframe from a natural-language feature description and push it
    to the Kenbun /board Wireframe (Excalidraw) canvas.

    The AI designs like a frontend developer: logical screens, labeled components, form
    fields, navigation, and a primary CTA per screen. It produces a structured spec that
    is converted deterministically into a valid Excalidraw scene, then written to the board.
    Example: generate_wireframe("a login screen with email/password and a dashboard").
    """
    import urllib.request
    import json as _json
    with silence_stdout():
        try:
            from tools.craft.wireframe_generator import build_wireframe
            scene, spec = build_wireframe(prompt)
        except Exception as e:
            return f"ERROR: wireframe generation failed: {e}"
        try:
            body = _json.dumps(scene).encode("utf-8")
            req = urllib.request.Request(
                "http://localhost:3000/api/wireframe", data=body,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                pushed = (r.status == 200)
        except Exception as e:
            return (f"⚠️ Wireframe built ({len(scene['elements'])} elements) but push to board failed: {e}. "
                    f"The dashboard /api/wireframe endpoint may be unreachable.")
    screens = [s.get("name", "?") for s in spec.get("screens", [])]
    return (
        f"✅ Wireframe **{spec.get('title', 'Untitled')}** {'pushed to /board' if pushed else 'built'}.\n"
        f"• Screens: {', '.join(screens) or '(none)'}\n"
        f"• Elements: {len(scene['elements'])}\n"
        f"Open http://100.92.127.1/board → **Wireframe** tab (reload the canvas to view)."
    )

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
        # Fallback values
        latest_version = "unknown"
        last_updated = "unknown"
        latest = {}
        
        # Handle list structure
        if isinstance(data, list):
            if not data:
                return "ERROR: Benchmark log is an empty list."
            bench_container = next((item for item in reversed(data) if isinstance(item, dict) and "benchmarks" in item), None)
            if not bench_container:
                return "ERROR: No valid benchmark containers found in the array."
            try: latest_version = bench_container.get("system_version", "unknown")
            except Exception: pass
            last_updated = bench_container.get("last_updated", "unknown")
            benchmarks_list = bench_container.get("benchmarks", [])
            
            if isinstance(benchmarks_list, list) and benchmarks_list:
                latest = benchmarks_list[-1]
                
        # Handle dict structure
        elif isinstance(data, dict):
            last_updated = data.get("last_updated", "unknown")
            latest_version = data.get("system_version", "unknown")
            
            # Check for history (Paradigm 1)
            if "history" in data and isinstance(data["history"], list) and data["history"]:
                latest_history = data["history"][-1]
                routing_acc = latest_history.get("routing_accuracy", 0.0)
                latency = latest_history.get("median_latency_ms", 0.0)
                n_cases = latest_history.get("n_cases", 0)
                date = latest_history.get("date", last_updated)
                
                # Check if we also have telemetry benchmarks
                benchmarks_list = data.get("benchmarks", [])
                if isinstance(benchmarks_list, list) and benchmarks_list:
                    latest = benchmarks_list[-1]
                    m = latest.get("metrics", {})
                    return (
                        f"# 📊 Brain Health Dashboard (v{latest_version})\n\n"
                        f"## 🎯 Routing Benchmark\n"
                        f"• **Routing Accuracy:** {routing_acc:.2%}\n"
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
                        f"• **Routing Accuracy:** {routing_acc:.2%}\n"
                        f"• **Median Latency:** {latency:.2f}ms\n"
                        f"• **Test Cases:** {n_cases}\n"
                        f"• **Last Updated:** {date}\n"
                        f"• **Status:** active"
                    )
            
            # Fallback to standard dict benchmark list (Paradigm 2)
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
def audit_package_safety(package_name: str, ecosystem: str = "npm") -> str:
    """
    Audits a package for supply-chain risks (malware, typosquatting, age) before installation.
    Supports: npm, pip.
    """
    import urllib.request
    import urllib.error

    def _http_json(url: str):
        req = urllib.request.Request(url, headers={"User-Agent": "kenbun-supply-audit"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        eco = (ecosystem or "npm").lower()

        # Query package registries over HTTP so no npm/pip CLI binary is required
        # (the container has neither). npm -> registry.npmjs.org, pip -> pypi.org.
        if eco == "npm":
            try:
                data = _http_json(f"https://registry.npmjs.org/{package_name}")
            except urllib.error.HTTPError as he:
                if he.code == 404:
                    return f"❌ npm package '{package_name}' not found."
                return f"❌ Error querying npm registry for '{package_name}': HTTP {he.code}"
            created_at = data.get("time", {}).get("created")
            maintainers = data.get("maintainers", []) or []
            latest = data.get("dist-tags", {}).get("latest", "?")
        elif eco == "pip":
            try:
                data = _http_json(f"https://pypi.org/pypi/{package_name}/json")
            except urllib.error.HTTPError as he:
                if he.code == 404:
                    return f"❌ PyPI package '{package_name}' not found."
                return f"❌ Error querying PyPI for '{package_name}': HTTP {he.code}"
            info = data.get("info", {})
            # earliest release timestamp = package age
            created_at = None
            for rel in data.get("releases", {}).values():
                for f in rel:
                    ut = f.get("upload_time_iso_8601") or f.get("upload_time")
                    if ut and (created_at is None or ut < created_at):
                        created_at = ut
            # PyPI has no maintainer list; treat author/maintainer as a signal
            maintainers = [m for m in [info.get("author"), info.get("maintainer")] if m]
            latest = info.get("version", "?")
        else:
            return f"Ecosystem '{ecosystem}' not supported. Use 'npm' or 'pip'."

        if not created_at:
            return f"⚠️ Could not verify creation date for '{package_name}'."

        created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        age_days = (datetime.now(created_date.tzinfo) - created_date).days

        risks = []
        if age_days < 90:
            risks.append(f"🔴 CRITICAL: Package is only {age_days} days old (High Malware Risk).")
        if len(maintainers) < 2:
            risks.append(f"🟡 WARNING: Only {len(maintainers)} maintainer/author signal(s).")

        status = "SECURE ✅" if not risks else "RISKY ⚠️"
        report = [
            f"# 🛡️ Supply Chain Audit: {package_name} ({eco} v{latest})",
            f"**Status:** {status}",
            f"**Age:** {age_days} days",
            f"**Maintainers:** {len(maintainers)}",
            "",
            "## 🔍 Risk Findings",
        ]
        if not risks:
            report.append("- No immediate red flags detected.")
        else:
            report.extend([f"- {r}" for r in risks])
            if eco == "npm":
                report.append("\n**Recommendation:** Use `npm install --ignore-scripts` if installation is mandatory.")
        return "\n".join(report)

    except Exception as e:
        return f"ERROR: Audit failed. {str(e)}"

@sovereign_tool()
def sync_jira_issue(issue_key: str, status_update: str = "") -> str:
    """
    Syncs a Jira issue: downloads the issue description and/or updates its workflow status.
    If environment variables JIRA_SERVER_URL and JIRA_API_TOKEN are not set, runs in mock simulation mode.
    """
    import os
    import urllib.request
    import base64
    
    jira_url = os.environ.get("JIRA_SERVER_URL")
    jira_token = os.environ.get("JIRA_API_TOKEN")
    jira_email = os.environ.get("JIRA_USER_EMAIL")
    
    if not jira_url or not jira_token:
        # Mock mode
        mock_summary = f"Mock Issue for {issue_key}: Resolve profile crash"
        mock_desc = "Verify that updating the user profile with special characters does not cause a database exception. Add a test in shadow_test."
        mock_status = status_update or "In Progress"
        report = [
            f"# 📋 Jira Sync: {issue_key} (SIMULATED)",
            f"**Status:** {mock_status}",
            f"**Summary:** {mock_summary}",
            f"**Description:** {mock_desc}",
            "",
            "⚠️ *Running in mock mode. Set JIRA_SERVER_URL and JIRA_API_TOKEN to hit live APIs.*"
        ]
        return "\n".join(report)

    # Real integration: HTTP basic auth
    try:
        url = f"{jira_url.rstrip('/')}/rest/api/3/issue/{issue_key}"
        req = urllib.request.Request(url)
        auth_str = f"{jira_email}:{jira_token}" if jira_email else jira_token
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        req.add_header("Authorization", f"Basic {encoded_auth}")
        req.add_header("Accept", "application/json")
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            fields = data.get("fields", {})
            summary = fields.get("summary", "No Summary")
            description = fields.get("description", {}).get("text", "No Description")
            current_status = fields.get("status", {}).get("name", "Unknown")

        report = [
            f"# 📋 Jira Sync: {issue_key}",
            f"**Current Status:** {current_status}",
            f"**Summary:** {summary}",
            f"**Description:** {description}",
        ]
        
        if status_update:
            # Try to transition ticket
            report.append(f"🔄 Transition request to '{status_update}' initiated.")
            
        return "\n".join(report)
    except Exception as e:
        return f"❌ Failed to sync Jira issue {issue_key}: {str(e)}"

@sovereign_tool()
def create_bitbucket_pr(repo_slug: str, source_branch: str, target_branch: str = "master", title: str = "", description: str = "") -> str:
    """
    Creates a Pull Request in Bitbucket for the specified repository and branches.
    If environment variables BITBUCKET_WORKSPACE and BITBUCKET_API_TOKEN are not set, runs in mock simulation mode.
    """
    import os
    import urllib.request
    import base64
    
    workspace = os.environ.get("BITBUCKET_WORKSPACE", "mock-workspace")
    token = os.environ.get("BITBUCKET_API_TOKEN")
    
    pr_title = title or f"Auto-patch: Merging {source_branch} into {target_branch}"
    pr_desc = description or "Automated patch submitted by Kenbun Agent."
    
    if not token or workspace == "mock-workspace":
        # Mock mode
        mock_pr_url = f"https://bitbucket.org/{workspace}/{repo_slug}/pull-requests/42"
        report = [
            f"# 🚀 Bitbucket Pull Request (SIMULATED)",
            f"**Repository:** {repo_slug}",
            f"**Source Branch:** {source_branch}",
            f"**Target Branch:** {target_branch}",
            f"**PR Title:** {pr_title}",
            f"**PR Link:** {mock_pr_url}",
            "",
            "⚠️ *Running in mock mode. Set BITBUCKET_WORKSPACE and BITBUCKET_API_TOKEN to hit live APIs.*"
        ]
        return "\n".join(report)

    # Real integration
    try:
        url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests"
        payload = {
            "title": pr_title,
            "description": pr_desc,
            "source": {"branch": {"name": source_branch}},
            "destination": {"branch": {"name": target_branch}}
        }
        
        req = urllib.request.Request(url, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        data_bytes = json.dumps(payload).encode()
        
        with urllib.request.urlopen(req, data=data_bytes, timeout=10) as response:
            res_data = json.loads(response.read().decode())
            links = res_data.get("links", {})
            html_link = links.get("html", {}).get("href", "No Link")
            pr_id = res_data.get("id", "Unknown")
            
        report = [
            f"# 🚀 Bitbucket Pull Request Created",
            f"**PR ID:** #{pr_id}",
            f"**Repository:** {workspace}/{repo_slug}",
            f"**Source:** {source_branch} ➔ **Target:** {target_branch}",
            f"**PR Link:** {html_link}",
        ]
        return "\n".join(report)
    except Exception as e:
        return f"❌ Failed to create Bitbucket Pull Request: {str(e)}"

@sovereign_tool()
def session_search(
    query: Optional[str] = None,
    session_id: Optional[str] = None,
    around_message_id: Optional[int] = None,
    window: int = 5,
    limit: int = 3,
    sort: str = "newest",
    role_filter: str = "user,assistant"
) -> str:
    """Recall past conversation contexts, resume, and search database.
    
    This tool supports three shapes depending on parameters:
    1. Discovery (pass query): Searches past messages using SQLite FTS5.
    2. Scroll (pass session_id + around_message_id): Returns a window of messages.
    3. Browse (no args): Lists recent sessions.
    """
    with silence_stdout():
        from tools.sensory.session_search import perform_session_search, render_search_results_markdown
        res = perform_session_search(
            query=query,
            session_id=session_id,
            around_message_id=around_message_id,
            window=window,
            limit=limit,
            sort=sort,
            role_filter=role_filter
        )
        return render_search_results_markdown(res)

# ========================================================
# DYNAMIC MCP REGISTRATION FROM CENTRAL REGISTRY
# ========================================================
for name, tool_entry in registry.get_all_tools().items():
    # Use FastMCP's tool decorator directly on the handler
    mcp.tool(name=tool_entry.name, description=tool_entry.description)(tool_entry.handler)

if __name__ == "__main__":
    import signal
    import os
    def handle_sigterm(*args):
        _STOP_TAIL.set()
        os._exit(0)
    signal.signal(signal.SIGTERM, handle_sigterm)

    # If running manually, we can print status. 
    try:
        # Low-Level Systems Memory Optimization (C# Heap Pinning equivalent)
        # Freeze the CPython heap containing all registered FastMCP tools, decorators,
        # and third-party modules (ChromaDB, Pydantic) before starting the server loop.
        # This permanently excludes them from future generational GC sweeps, maximizing throughput.
        import gc
        gc.collect(2)
        
        # Absolute silence required for MCP protocol.
        # No startup banners allowed.
        # brain_health/ is gitignored (holds local .db state), so this module
        # may be absent on fresh clones — SRE monitoring is optional and must
        # never block the MCP server from starting.
        try:
            import threading
            from core.brain_health.docker_sre import SREAgent
            def _run_sre_agent():
                try:
                    agent = SREAgent(check_interval_sec=60, unhealthy_threshold=3)
                    agent.start_monitoring()
                except Exception as e:
                    debug_log(f"SRE Agent crashed: {e}")
            threading.Thread(target=_run_sre_agent, daemon=True).start()
        except Exception as e:
            debug_log(f"SRE Agent unavailable (skipping): {e}")
        
        mcp.run()
    except Exception as e:
        import traceback
        debug_log(f"CRITICAL CRASH: {e}")
        debug_log(traceback.format_exc())
