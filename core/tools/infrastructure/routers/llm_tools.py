import asyncio
from core.tools.audit.supervisor_agent import run_supervisor_audit
from core.tools.audit.gemini_reviewer import gemini_code_review, gemini_research

from core.tools.utils.orchestrator_helpers import build_context

# Constants previously in server.py
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

def query_system_3(query_text, n=3):
    """Internal helper to fetch project concept memories."""
    from core.tools.infrastructure.server import debug_log
    try:
        from core.tools.memory.chroma_db_connect import query_embeddings
        results = query_embeddings(query_text, n_results=n, category="concepts")
        raw_docs = results['documents'][0] if results['documents'] and results['documents'][0] else []
        return [doc[:4000] for doc in raw_docs]
    except Exception as e:
        debug_log(f"⚠️ System 3 Query Failed: {e}")
        return []

def consult_supervisor(user_proposal: str, code_snippet: str = "", iterative_mode: bool = False) -> str:
    """
    Activates SYSTEM 2 (Local LLM via LM Studio).
    """
    from core.tools.infrastructure.server import debug_log
    memories = query_system_3(user_proposal)
    memory_context = "\n---\n".join(memories)

    debug_log(f"🧠 SYSTEM 2 ACTIVATED (Iterative: {iterative_mode})")
    
    coro = run_supervisor_audit(user_proposal, code_snippet, memory_context)
    try:
        asyncio.get_running_loop()
        import concurrent.futures
        def _run_in_thread():
            return asyncio.run(coro)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(_run_in_thread).result()
    except RuntimeError:
        result = asyncio.run(coro)

    if result.get("status") == "error":
        return f"❌ Supervisor Error: {result.get('critique')}"
    return f"✅ Supervisor Analysis:\n{result.get('critique')}"

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

def research_with_gemini(
    query: str,
    tech_key: str = "",
    thinking: bool = False,
    thinking_level: str = "medium"
) -> str:
    """
    Deep architectural research using Gemini Cloud AI + Google Search grounding.
    """
    return gemini_research(
        query=query,
        tech_key=tech_key,
        thinking=thinking,
        thinking_level=thinking_level,
        official_docs_registry=OFFICIAL_DOCS
    )

def research_official_docs(tech_key: str, query: str) -> str:
    """
    Query the official documentation for a specific technology using Google Search Grounding.
    Valid tech_keys: react, nextjs, vue, svelte, tailwind, shadcn, zod, python, fastapi, supabase, docker, threejs, r3f, gsap.
    """
    from core.tools.infrastructure.server import debug_log
    debug_log(f"📚 RESEARCHING OFFICIAL DOCS: {tech_key} | {query}")
    if tech_key not in OFFICIAL_DOCS:
        return f"⚠️ Unknown tech_key '{tech_key}'. Valid keys: {list(OFFICIAL_DOCS.keys())}"
    
    site = OFFICIAL_DOCS[tech_key]
    try:
        debug_log(f"🔍 Researching: {query} site:{site}")
        from duckduckgo_search import DDGS
        results = DDGS().text(f"{query} site:{site}", max_results=3)
        return str(results) if results else "No results."
    except Exception as e:
        return f"Research failed: {e}"

def register_llm_tools(mcp):
    mcp.add_tool(consult_supervisor)
    mcp.add_tool(review_code_with_gemini)
    mcp.add_tool(research_with_gemini)
    mcp.add_tool(research_official_docs)
