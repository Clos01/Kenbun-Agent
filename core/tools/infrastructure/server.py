import os
import sys
sys.stderr.write("DEBUG: server.py IS BEING LOADED\n")
import re
import json
import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from mcp.server.fastmcp import FastMCP
import io

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

if not sys.stdout.isatty():
    import builtins
    _original_print = builtins.print
    def _stderr_print(*args, **kwargs):
        # Force all prints to stderr if not explicitly redirected
        if 'file' not in kwargs or kwargs['file'] is sys.stdout:
            kwargs['file'] = sys.stderr
        _original_print(*args, **kwargs)
    builtins.print = _stderr_print

# --- 2. CONFIGURATION ---

# --- 2. IMPORTS (Hierarchical) ---
# Hierarchical imports moved inside tool functions to prevent startup timeouts
# Global Strategy Instances
from tools.strategy.decision_logic import router
from tools.strategy.strategy_manager import governor

mcp = FastMCP("Kenbun Tools")

# ========================================================
# 📡 DOCKER LOG TAILER DAEMON FOR REAL-TIME DOZZLE LOGGING
# ========================================================
def _tail_mcp_debug_log():
    """
    Background daemon function that tails mcp_debug.log and streams host-side events to stderr.
    """
    log_path = Path(settings.PROJECT_ROOT) / "mcp_debug.log"
    # Wait for file to exist
    for _ in range(15):
        if log_path.exists():
            break
        time.sleep(1)
    if not log_path.exists():
        return
    
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            # Go to the end of the file
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                # Stream terminal chat events directly to container standard error
                if "[TERMCHAT]" in line:
                    sys.stderr.write(line)
                    sys.stderr.flush()
    except Exception as e:
        sys.stderr.write(f"DEBUG: Log tailer daemon error: {e}\n")
        sys.stderr.flush()

# Spawn the log tailer daemon immediately on server startup
import threading
import time
_tail_thread = threading.Thread(target=_tail_mcp_debug_log, daemon=True)
_tail_thread.start()


PC_IP = settings.SWARM_PC_IP
CHROMA_PORT = settings.CHROMA_PORT
LM_STUDIO_PORT = settings.LM_STUDIO_PORT
LM_STUDIO_MODEL = settings.LM_STUDIO_MODEL
PROJECT_ROOT = str(settings.PROJECT_ROOT)

# --- 0.1 SILENCE HELPER ---
import contextlib
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
        from tools.memory.chroma_db_connect import query_embeddings
        results = query_embeddings(query_text, n_results=n, category="concepts")
        raw_docs = results['documents'][0] if results['documents'] and results['documents'][0] else []
        return [doc[:4000] for doc in raw_docs]
    except Exception as e:
        debug_log(f"⚠️ System 3 Query Failed: {e}")
        return []

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
@mcp.tool()
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

    coro = run_supervisor_audit(user_proposal, code_snippet, memory_context)
    try:
        # No running loop → safe to use asyncio.run()
        asyncio.get_running_loop()
        # We ARE in a running loop (e.g. MCP server context). Run the coroutine in
        # a dedicated worker thread with its own loop to avoid the
        # "asyncio.run() cannot be called from a running event loop" error.
        import concurrent.futures
        def _run_in_thread():
            return asyncio.run(coro)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(_run_in_thread).result()
    except RuntimeError:
        # No loop running on this thread — original path is fine.
        result = asyncio.run(coro)

    if result.get("status") == "error":
        return f"❌ Supervisor Error: {result.get('critique')}"

    return json.dumps(result, indent=2)

# --- 5.1 TOOL: SYSTEM 2c (THE GUARDRAIL) ---
@mcp.tool()
def audit_guardrail(code_snippet: str, task_context: str = "") -> str:
    """
    Fast, deterministic security and style audit (System 2c).
    Use this for continuous checks before calling the full Supervisor.
    """
    debug_log(f"🛡️ SYSTEM 2c ACTIVATED")
    from tools.audit.guardrail_agent import run_guardrail_audit
    result = run_guardrail_audit(code_snippet, task_context)
    return json.dumps(result, indent=2)

# --- 5.2 TOOL: AUTOMATED LINTER AUTO-FIX (STEP 0) ---
@mcp.tool()
def autofix_linter(file_path: str, project_path: str = "") -> str:
    """
    Safe pre-flight linter auto-fix pass (eslint --fix / ruff / black).
    Prunes unused imports/variables and cleans formatting prior to deeper audits.
    """
    debug_log(f"🚀 Pre-flight linter pass activated for: {file_path}")
    from tools.audit.linter_autofix import autofix_linter as _autofix
    return _autofix(file_path, project_path)

# --- 6. TOOL: RESEARCHER (DOCS) ---
@mcp.tool()
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
@mcp.tool()
def ask_architect(query: str) -> str:
    """Directly queries Vector DB for history."""
    memories = query_system_3(query, n=5)
    return "\n\n".join(memories) if memories else "No relevant memories found."

@mcp.tool()
def ask_ui_expert(query: str) -> str:
    """Consult the Lead UI Designer for CSS/Layout help."""
    from tools.audit.ui_designer import consult_ui_expert
    return consult_ui_expert(query)

@mcp.tool()
def get_design_tokens() -> str:
    """Returns the current Design System tokens from DESIGN.md."""
    from tools.design.oracle import DesignOracle
    rules = DesignOracle.get_rules()
    return json.dumps(rules.get("tokens", {}), indent=2)

# --- 9. TOOL: GEMINI CODE REVIEWER (Cloud AI) ---
@mcp.tool()
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
@mcp.tool()
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

# --- 11. TOOL: DOCKER SANDBOX (Phase 1) ---
@mcp.tool()
def run_code_safely(code: str, language: str = "python", timeout: int = 30) -> str:
    """
    Execute code in an isolated Docker container.
    Safety: No network, memory-limited, CPU-limited, auto-destroyed.
    Supports: python, node/javascript.
    """
    from tools.execution.sandbox_runner import run_code_safely as _run_code_safely
    return _run_code_safely(code=code, language=language, timeout=timeout)

# --- 12. TOOL: REPO MAP (Phase 2) ---
@mcp.tool()
def scan_repo(project_path: str, extensions: str = ".py,.ts,.tsx,.js,.jsx") -> str:
    """
    Generate a skeleton map of a project. Shows classes, functions, and signatures
    without implementation code. Fits large codebases into a single prompt.
    """
    from tools.memory.repo_mapper import scan_repo as _scan_repo
    return _scan_repo(project_path=project_path, extensions=extensions)

# --- 13. TOOL: ERROR MEMORY — SAVE (Phase 3) ---
@mcp.tool()
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
@mcp.tool()
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
@mcp.tool()
def save_checkpoint(file_path: str, label: str = "auto") -> str:
    """
    Snapshot a file's current state before making risky changes.
    Use restore_checkpoint() to revert if the fix fails.
    """
    from tools.utils.backtracker import save_checkpoint as _save_checkpoint
    return _save_checkpoint(file_path=file_path, label=label)

# --- 16. TOOL: BACKTRACKER — RESTORE (Phase 4) ---
@mcp.tool()
def restore_checkpoint(file_path: str, label: str = "") -> str:
    """
    Revert a file to a previous checkpoint.
    If no label provided, reverts to the most recent checkpoint.
    """
    from tools.utils.backtracker import restore_checkpoint as _restore_checkpoint
    return _restore_checkpoint(file_path=file_path, label=label)

# --- 17. TOOL: BACKTRACKER — LIST (Phase 4) ---
@mcp.tool()
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
@mcp.tool()
def orchestrate(
    workflow: str,
    task: str,
    project_path: str = "",
    file_path: str = "",
    code_snippet: str = "",
    tech_key: str = "",
) -> str:
    from tools.infrastructure.orchestrator import run_pipeline
    from tools.audit.reflection_agent import reflect_and_distill as _reflect_and_distill
    from tools.audit.guardrail_agent import run_guardrail_audit
    from tools.utils.maze_protocol import backward_verify
    from tools.audit.discovery_agent import generate_discovery_form
    from tools.memory.repo_mapper import scan_repo
    from tools.utils.error_memory import remember_fix, recall_fix
    from tools.utils.backtracker import save_checkpoint, restore_checkpoint
    from tools.execution.sandbox_runner import run_code_safely
    from tools.audit.gemini_reviewer import gemini_code_review, gemini_research
    from tools.audit.supervisor_agent import run_supervisor_audit
    import asyncio

    def _local_view_file(AbsolutePath: str) -> str:
        # Path Traversal Guardrail (Security Hardening)
        path = Path(AbsolutePath).resolve()
        root = settings.PROJECT_ROOT.resolve()
        if not str(path).startswith(str(root)):
            raise PermissionError(f"Security Breach Blocked: Path '{path}' is outside project root '{root}'.")
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    # Build tool registry — pass all tool functions to the orchestrator
    tool_registry = {
        "scan_repo": scan_repo,
        "recall_fix": lambda error_message: recall_fix(error_message, PC_IP, CHROMA_PORT),
        "remember_fix": lambda error_message, solution, file_context="": remember_fix(
            error_message, solution, file_context, PC_IP, CHROMA_PORT
        ),
        "save_checkpoint": save_checkpoint,
        "restore_checkpoint": restore_checkpoint,
        "run_code_safely": run_code_safely,
        "review_code_with_gemini": lambda code_snippet, review_context="", tech_key="", cross_check=True, thinking=False, thinking_level="medium": gemini_code_review(
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
    }

    coro = run_pipeline(
        workflow=workflow,
        task=task,
        tools=tool_registry,
        project_path=project_path,
        file_path=file_path,
        code_snippet=code_snippet,
        tech_key=tech_key,
    )
    try:
        asyncio.get_running_loop()
        import concurrent.futures
        def _run_in_thread():
            return asyncio.run(coro)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(_run_in_thread).result()
    except RuntimeError:
        result = asyncio.run(coro)
    return result


# ============================================================
# KNOWLEDGE MANAGEMENT (Explicit Hivemind Control)
# ============================================================

@mcp.tool()
def save_to_hivemind(title: str, content: str, tags: str, category: str = "concepts") -> str:
    """
    Use this when the user says 'Save this to the Hivemind' or wants to store a new architectural rule, pattern, or concept.
    """
    from tools.memory.knowledge_manager import learn_concept
    return learn_concept(title, content, tags, category=category)

@mcp.tool()
def search_hivemind_concepts(query: str, category: str = "concepts") -> str:
    """
    Use this to pull up past architectural rules or concepts, especially when asked to compare new ideas against old ones.
    """
    from tools.memory.knowledge_manager import list_concepts
    return list_concepts(query, category=category)

@mcp.tool()
def delete_from_hivemind(concept_id: str, category: str = "concepts") -> str:
    """
    Use this to delete outdated concepts from the database when the user explicitly asks to forget them.
    """
    from tools.memory.knowledge_manager import forget_concept
    return forget_concept(concept_id, category=category)


# ============================================================
# CODEBASE VECTORIZATION (Semantic Code Understanding)
# ============================================================

@mcp.tool()
def index_codebase(project_path: str = "") -> str:
    """
    Indexes the entire project's code into the Hivemind (ChromaDB) using semantic code chunking.
    Call this when the user wants the system to 'understand' their massive codebase.
    """
    if not project_path:
        project_path = PROJECT_ROOT
    from tools.memory.code_indexer import index_project
    return index_project(project_path)

@mcp.tool()
def search_codebase(query: str) -> str:
    """
    Searches the semantic code index for a specific function, logic, or implementation pattern.
    Use this instead of grep when you need semantic, mathematical understanding of what the code does.
    """
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

CLOUD AI:
10. review_code_with_gemini(code_snippet, review_context, tech_key, cross_check, thinking, thinking_level) — Full 4-stage code review pipeline
11. research_with_gemini(query, tech_key, thinking, thinking_level) — Cloud-based research grounded in official docs

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

@mcp.tool()
def think_about_tools(task: str) -> str:
    """
    Analyze a task and recommend which tools to use and in what order.
    Think before you act — this planner knows all 15 tools and suggests the optimal strategy.
    """
    try:
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

    except Exception as e:
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
@mcp.tool()
def patch_hivemind_concept(concept_id: str, title: str = None, content: str = None, tags: str = None) -> str:
    """Updates an existing concept in the Hivemind. Only provided fields will be updated."""
    from tools.memory.knowledge_manager import patch_concept
    return patch_concept(concept_id, title, content, tags)

@mcp.tool()
def ingest_knowledge_from_pdf(pdf_path: str, tech_key: str = "general") -> str:
    """
    Ingests technical knowledge from a PDF file into the Hivemind.
    Use this to 'teach' the AI new libraries (e.g. Three.js, Next.js) using official PDFs.
    """
    from tools.memory.pdf_ingestor import ingest_pdf_to_hivemind
    return ingest_pdf_to_hivemind(pdf_path, tech_key)

@mcp.tool()
def prune_hivemind() -> str:
    """Removes outdated or redundant concepts from the Hivemind to maintain precision."""
    from tools.memory import knowledge_manager
    return knowledge_manager.prune_hivemind()

@mcp.tool()
def get_intelligence_stats() -> str:
    """Returns the current Bayesian intelligence stats for all tools (Remote Storage)."""
    try:
        # Using the governor already imported at the top of the file
        if not governor.collection:
            return "No intelligence data collected yet or remote store disconnected."
        
        # Get all entries from the special intelligence collection
        res = governor.collection.get()
        if not res["ids"]:
            return "No intelligence data collected yet."
            
        stats = ["# 🧠 System 4: Remote Intelligence Dashboard\n"]
        for i in range(len(res["ids"])):
            tool = res["ids"][i]
            m = res["metadatas"][i]
            a = float(m.get("alpha", 2.0))
            b = float(m.get("beta", 2.0))
            s = int(m.get("success_count", 0))
            f = int(m.get("failure_count", 0))
            prob = a / (a + b)
            stats.append(f"• **{tool}**: {prob:.2%} success probability ({s}S/{f}F)")
        return "\n".join(stats)
    except Exception as e:
        return f"ERROR: Failed to retrieve stats. {e}"

@mcp.tool()
def reflect_on_task(task: str, tool_logs: str) -> str:
    """
    Analyzes tool logs to extract architectural patterns for the Hivemind.
    Usually called automatically by orchestrate(), but can be run manually.
    """
    from tools.audit.reflection_agent import reflect_and_distill as _reflect_and_distill
    return _reflect_and_distill(task, tool_logs)

@mcp.tool()
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
            latest_version = data.get("system_version", "unknown")
            last_updated = data.get("last_updated", "unknown")
            benchmarks_list = data.get("benchmarks", [])
            if isinstance(benchmarks_list, list) and benchmarks_list:
                latest = benchmarks_list[-1]
        else:
            return f"ERROR: Unrecognized JSON structure type: {type(data).__name__}"

        if not isinstance(latest, dict):
            return f"ERROR: Latest benchmark entry is not a valid object."
            
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

@mcp.tool()
def audit_package_safety(package_name: str, ecosystem: str = "npm") -> str:
    """
    Audits a package for supply-chain risks (malware, typosquatting, age) before installation.
    Supports: npm, pip.
    """
    try:
        if ecosystem == "npm":
            # Check package metadata
            cmd = ["npm", "view", package_name, "time", "maintainers", "--json"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return f"❌ Package '{package_name}' not found or error querying npm."
            
            data = json.loads(result.stdout)
            created_at = data.get("created")
            if not created_at:
                # Some packages have complex time objects
                created_at = data.get("time", {}).get("created")
            
            if not created_at:
                return f"⚠️ Could not verify creation date for '{package_name}'."
            
            created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            age_days = (datetime.now(created_date.tzinfo) - created_date).days
            
            # Risk Analysis
            risks = []
            if age_days < 90:
                risks.append(f"🔴 CRITICAL: Package is only {age_days} days old (High Malware Risk).")
            
            # Check for maintainers
            maintainers = data.get("maintainers", [])
            if len(maintainers) < 2:
                risks.append(f"🟡 WARNING: Only {len(maintainers)} maintainer(s).")
            
            status = "SECURE ✅" if not risks else "RISKY ⚠️"
            report = [
                f"# 🛡️ Supply Chain Audit: {package_name}",
                f"**Status:** {status}",
                f"**Age:** {age_days} days",
                f"**Maintainers:** {len(maintainers)}",
                "",
                "## 🔍 Risk Findings"
            ]
            if not risks:
                report.append("- No immediate red flags detected.")
            else:
                report.extend([f"- {r}" for r in risks])
                report.append("\n**Recommendation:** Use `npm install --ignore-scripts` if installation is mandatory.")
            
            return "\n".join(report)
            
        return f"Ecosystem '{ecosystem}' not yet supported for deep audit."
        
    except Exception as e:
        return f"ERROR: Audit failed. {str(e)}"

if __name__ == "__main__":
    # If running manually, we can print status. 
    try:
        # Absolute silence required for MCP protocol.
        # No startup banners allowed.
        mcp.run()
    except Exception as e:
        import traceback
        debug_log(f"CRITICAL CRASH: {e}")
        debug_log(traceback.format_exc())
