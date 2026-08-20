import glob as _glob
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.infrastructure.config import settings
from tools.registry import sovereign_tool
from tools.utils.helpers import (
    OFFICIAL_DOCS,
    _run_async_safely,
    debug_log,
    query_system_3,
    silence_stdout,
)
from tools.utils.path_utils import get_project_root

logger = logging.getLogger("tools.supervisor")
PROJECT_ROOT = get_project_root()


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
        from tools.utils.web_engine import ddgs_search
        results = ddgs_search(f"{query} site:{site}", limit=3)
        return str(results) if results else "No results."
    except Exception as e:
        return f"Research failed: {e}"


# --- 7. TOOL: ARCHITECT (DEFENSIVE MULTI-LAYER REASONING) ---
def _gather_infrastructure_context(query: str) -> str:
    """Scan project infrastructure files for architectural context."""
    context_parts = []
    
    # 1. Docker Compose files (all variants)
    compose_patterns = [
        str(PROJECT_ROOT / "docker-compose*.yml"),
        str(PROJECT_ROOT / "docker-compose*.yaml"),
    ]
    for pattern in compose_patterns:
        for f in sorted(_glob.glob(pattern)):
            try:
                with open(f, "r") as fh:
                    content = fh.read()
                basename = os.path.basename(f)
                context_parts.append(
                    f"### {basename}\n```yaml\n{content[:4000]}\n```"
                )
            except Exception:
                pass
    
    # 2. Environment variables (infrastructure-relevant keys only)
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        try:
            infra_keywords = [
                "TAILSCALE", "BIND_IP", "PORT", "PROJECT_ROOT",
                "DASHBOARD", "API_", "DOCKER", "HOST", "IP",
                "SWARM_PC", "LM_STUDIO", "CHROMA",
            ]
            with open(env_file, "r") as fh:
                env_lines = [
                    line.strip() for line in fh
                    if line.strip()
                    and not line.startswith("#")
                    and any(k in line.upper() for k in infra_keywords)
                ]
            if env_lines:
                safe_lines = []
                for line in env_lines[:30]:
                    key = line.split("=", 1)[0].upper() if "=" in line else ""
                    if any(s in key for s in ["PASSWORD", "SECRET", "TOKEN", "KEY", "AUTH"]):
                        safe_lines.append(f"{key}=***REDACTED***")
                    else:
                        safe_lines.append(line)
                context_parts.append(
                    "### .env (Infrastructure Keys)\n```\n"
                    + "\n".join(safe_lines)
                    + "\n```"
                )
        except Exception:
            pass
    
    # 3. STRUCTURE.md (project architecture map)
    structure_file = PROJECT_ROOT / "STRUCTURE.md"
    if structure_file.exists():
        try:
            with open(structure_file, "r") as fh:
                context_parts.append(
                    f"### STRUCTURE.md\n{fh.read()[:2500]}"
                )
        except Exception:
            pass
    
    # 4. Dockerfile
    dockerfile = PROJECT_ROOT / "Dockerfile"
    if dockerfile.exists():
        try:
            with open(dockerfile, "r") as fh:
                context_parts.append(
                    f"### Dockerfile\n```dockerfile\n{fh.read()[:1500]}\n```"
                )
        except Exception:
            pass
    
    # 5. Docker context list (if available)
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "context", "ls", "--format", "{{.Name}}: {{.DockerEndpoint}}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            context_parts.append(
                f"### Docker Contexts\n```\n{result.stdout.strip()}\n```"
            )
    except Exception:
        pass
    
    return "\n\n".join(context_parts)


@sovereign_tool()
def ask_architect(query: str) -> str:
    """Multi-layer architectural reasoning with defensive fallbacks.
    
    Layer 1: Vector DB memories (ChromaDB embeddings)
    Layer 2: Hivemind concept search (Honcho long-term memory)
    Layer 3: Infrastructure context scan (docker-compose, .env, STRUCTURE.md)
    Layer 4: LLM synthesis when raw context is found but no memories exist
    """
    # ── Layer 1: Vector DB Memories ──
    memories = query_system_3(query, n=5)
    
    # ── Layer 2: Hivemind Concepts ──
    hivemind_results = []
    try:
        with silence_stdout():
            from tools.memory.knowledge_manager import list_concepts
            hive_raw = list_concepts(query, category="concepts")
            if hive_raw and "No concepts found" not in hive_raw and "error" not in hive_raw.lower():
                hivemind_results = [hive_raw[:4000]]
    except Exception as e:
        debug_log(f"⚠️ ask_architect: Hivemind fallback failed: {e}")
    
    all_memories = memories + hivemind_results
    
    # ── If memories found, return them enriched ──
    if all_memories:
        return "\n\n---\n\n".join(all_memories)
    
    # ── Layer 3: DEFENSIVE FALLBACK — Infrastructure Context Scan ──
    debug_log("⚠️ ask_architect: No memories found. Activating infrastructure scan fallback.")
    
    infra_context = _gather_infrastructure_context(query)
    
    if not infra_context.strip():
        return (
            "No relevant memories found.\n\n"
            "💡 **Defensive Note**: Infrastructure scan also returned empty. "
            "Consider saving architectural knowledge with `save_to_hivemind` "
            "or checking if the project has a STRUCTURE.md file."
        )
    
    # ── Layer 4: LLM Synthesis ──
    try:
        from tools.audit.supervisor_agent import _call_local_senior
        
        system_prompt = (
            "You are a Senior Infrastructure Architect for the Kenbun project. "
            "You must analyze infrastructure configuration files (docker-compose, "
            ".env, Dockerfile) and provide precise, actionable architectural answers. "
            "Focus on: deployment topology, service locations, port mappings, "
            "volume mounts, network modes (Tailscale, container networking), "
            "and how to apply code changes to the correct deployment target. "
            "Be specific about container names, Docker contexts, and IPs."
        )
        
        user_message = (
            f"**Developer Question:** {query}\n\n"
            f"**Infrastructure Context (auto-scanned from project files):**\n\n"
            f"{infra_context[:6000]}"
        )
        
        llm_answer, llm_error = _call_local_senior(system_prompt, user_message, max_tokens=2000)
        
        if llm_answer:
            return (
                f"📐 **Architect Analysis** (Defensive Fallback — no prior memories)\n\n"
                f"{llm_answer}\n\n"
                f"---\n"
                f"*Sources: Infrastructure scan of docker-compose files, .env, and project config*\n"
                f"*💡 Tip: Save key architectural decisions with `save_to_hivemind` "
                f"so this knowledge is available instantly next time.*"
            )
        else:
            debug_log(f"⚠️ ask_architect: LLM synthesis failed: {llm_error}")
            return (
                f"📐 **Infrastructure Context** (Raw — LLM synthesis unavailable)\n\n"
                f"{infra_context[:5000]}\n\n"
                f"---\n*LLM Error: {llm_error}*"
            )
    except Exception as e:
        debug_log(f"⚠️ ask_architect: Full fallback triggered: {e}")
        return (
            f"📐 **Infrastructure Context** (Raw — fallback mode)\n\n"
            f"{infra_context[:5000]}\n\n"
            f"---\n*Note: LLM synthesis unavailable ({e}). Returning raw infrastructure scan.*"
        )


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
