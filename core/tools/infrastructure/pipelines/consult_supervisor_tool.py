import asyncio
from core.tools.audit.supervisor_agent import run_supervisor_audit
from core.tools.infrastructure.server import debug_log, query_system_3

def consult_supervisor(user_proposal: str, code_snippet: str = "", iterative_mode: bool = False) -> str:
    """
    Activates SYSTEM 2 (Local LLM via LM Studio).
    """
    # 1. Context from System 3
    memories = query_system_3(user_proposal)
    memory_context = "\n---\n".join(memories)

    debug_log(f"🧠 SYSTEM 2 ACTIVATED (Iterative: {iterative_mode})")
    
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

    return f"✅ Supervisor Analysis:\n{result.get('critique')}"
