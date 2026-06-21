import asyncio
from core.tools.infrastructure.server import TOOL_CATALOG
from core.tools.audit.supervisor_agent import _call_local_senior
from core.tools.infrastructure.config import get_settings

def run_benchmark():
    settings = get_settings()
    settings.PRIMARY_LLM_MODEL = "google/gemma-4-12b-qat"
    print(f"DEBUG: Active Primary Model -> {settings.PRIMARY_LLM_MODEL}")
    
    scenario = (
        "User Request: 'My Next.js build is failing with a mysterious out-of-memory (OOM) error "
        "only during the Vercel production build when generating static pages. I think it might be "
        "a memory leak in one of the data fetching functions across multiple files. "
        "I need you to find the root cause, review the entire project's fetching architecture, "
        "and implement a comprehensive fix.'"
    )
    
    print(f"\n[SCENARIO]\n{scenario}\n")
    
    system_prompt = (
        "You are an elite AI Orchestrator. You have access to the following tools:\n\n"
        f"{TOOL_CATALOG}\n\n"
        "Based on the user's complex debugging request, your ONLY job is to select the single best "
        "tool to handle this entire request autonomously. Explain your reasoning step-by-step, and "
        "then output the exact tool call you would make at the end (e.g. `orchestrate(...)`)."
    )
    
    print("\n[PROMPTING GEMMA-4-12B...]")
    response, err = _call_local_senior(system_prompt, scenario)
    
    if err:
        print(f"ERROR: {err}")
    else:
        print(f"\n--- Gemma 4-12b Response ---\n{response}\n-----------------------------")

if __name__ == "__main__":
    run_benchmark()
