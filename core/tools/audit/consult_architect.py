import sys
import subprocess
from pathlib import Path

current_dir = Path(__file__).resolve().parent

from tools.infrastructure.config import settings

# --- 1. CONFIGURATION ---
CHROMA_PORT = settings.CHROMA_PORT

# --- 2. THE MEMORY SYSTEM (RAG) ---
def recall_memories(query, n_results=5):
    """Searches the PC's Vector DB for relevant code snippets."""
    print(f"🔍 Scanning Hivemind for: '{query}'...", file=sys.stderr)
    try:
        from tools.memory.honcho_connect import retrieve_memory
        results = retrieve_memory(query, n_results=n_results, category="concepts")
        
        context_text = ""
        if results:
            for i, doc in enumerate(results):
                context_text += f"\n\n--- CONCEPT {i+1} ---\n{doc}\n"
        
        return context_text
    except Exception as e:
        print(f"⚠️ Memory Recall Failed: {e}", file=sys.stderr)
        return ""

# --- 3. AUTO-SYNC ---
def auto_sync():
    """Triggers the builder script to update memories."""
    # Looks for code_indexer.py in the memory folder
    script_path = current_dir.parent / "memory" / "code_indexer.py"
    try:
        # Run silently so we don't spam the chat logs
        subprocess.run(["python3", str(script_path)], check=True, capture_output=True)
        print("✅ Hivemind Sync Complete.", file=sys.stderr)
    except Exception as e:
        print(f"⚠️ Sync Warning: {e}", file=sys.stderr)

# --- 4. THE BRAIN (LLM + CONTEXT) ---
def consult_brain(user_query):
    # A. Get Context (The RAG Step)
    context = recall_memories(user_query)
    
    if not context:
        print("⚠️ No relevant memories found. Answering with general knowledge.", file=sys.stderr)
        context = "No specific code files found in memory. Answer generally."

    # B. Construct the Prompt
    system_prompt = (
        "You are the Senior System Architect. "
        "Use the provided CODE CONTEXT to answer the user's question accurately. "
        "Cite the filenames/concepts when you explain logic. "
        "If the answer is not in the context, admit it."
    )
    
    # We combine the User's Question + The Retrieved Code
    full_user_message = f"USER QUESTION:\n{user_query}\n\nCODE CONTEXT FROM MEMORY:\n{context}"

    print("🧠 Transmitting to LLM Gateway...", file=sys.stderr)
    
    # C. Send to Gateway
    try:
        from tools.utils.llm_router import call_llm_gateway
        return call_llm_gateway(system_prompt, full_user_message)
    except Exception as e:
        return f"❌ Connection Error: {e}"

# CLI Support (So you can still test it manually in terminal)
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 consult_architect.py 'Question'")
        sys.exit()
    
    auto_sync()
    print(consult_brain(sys.argv[1]))