from core.tools.infrastructure.server import ask_architect
from core.tools.audit.supervisor_agent import _call_local_senior
from core.tools.infrastructure.config import get_settings

def run_benchmark():
    settings = get_settings()
    print(f"DEBUG: Active Primary Model -> {settings.PRIMARY_LLM_MODEL}")
    
    # Step 1: Fetch from Hivemind
    query = "Next.js Production SEO & Performance Audit Protocols"
    print(f"\n[1] Querying Hivemind for: '{query}'")
    context = ask_architect(query)
    print(f"--- Retrieved Context ---\n{context[:200]}...\n-----------------------")
    
    # Step 2: Query the LLM
    print("\n[2] Prompting Local Model (Gemma 4-26b-a4b) with Context...")
    system_prompt = "You are a Next.js SEO expert. Use the following Hivemind context to answer the user's question exactly as specified in the rules.\n\nHIVEMIND CONTEXT:\n" + context
    user_message = "According to our internal protocols, what is the required Redirect type for Next.js and why?"
    
    response, err = _call_local_senior(system_prompt, user_message)
    if err:
        print(f"ERROR: {err}")
    else:
        print(f"\n--- Model Response ---\n{response}\n----------------------")

if __name__ == "__main__":
    run_benchmark()
