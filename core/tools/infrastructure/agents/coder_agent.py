import os
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

def build_coder_llm():
    """Build the ChatOpenAI client pointing to the primary LLM."""
    base_url = os.getenv("PRIMARY_LLM_URL", "http://127.0.0.1:11434/v1")
    model_name = os.getenv("PRIMARY_LLM_MODEL", "llama3")
    api_key = os.getenv("OPENAI_API_KEY", "not-needed")
    
    # If using anthropic/gemini through proxy or directly, adjust accordingly.
    # We default to ChatOpenAI assuming an OpenAI compatible endpoint (like Ollama).
    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model_name,
        temperature=0.1
    )

def coder_node(state: dict) -> dict:
    """
    The Coder Agent.
    Responsible for writing or fixing code based on instructions and test results.
    """
    llm = build_coder_llm()
    
    messages = state.get("messages", [])
    current_code = state.get("current_code", "")
    test_results = state.get("test_results", "")
    error_log = state.get("error_log", "")
    retry_count = state.get("retry_count", 0)
    
    system_prompt = (
        "You are an elite autonomous Coder Agent.\n"
        "Your task is to write high-quality, production-ready code.\n"
        "Return ONLY the raw code inside standard markdown blocks (e.g. ```python ... ```).\n"
        "Do not include any pleasantries or conversational text."
    )
    
    architect_instructions = state.get("architect_instructions", "")
    
    # Construct the context for the coder
    prompt_context = "Here is the objective:\n"
    if architect_instructions:
        prompt_context += f"--- ARCHITECT SPECIFICATION ---\n{architect_instructions}\n\n"
        
    for msg in messages:
        if isinstance(msg, HumanMessage):
            prompt_context += f"--- ORIGINAL USER REQUEST ---\n{msg.content}\n\n"
            
    if retry_count > 0:
        prompt_context += "\n--- PREVIOUS ATTEMPT FAILED ---\n"
        prompt_context += f"The code you wrote previously:\n```\n{current_code}\n```\n"
        prompt_context += f"Execution Results:\n{test_results}\n"
        if error_log:
            prompt_context += f"Error Output:\n{error_log}\n"
        prompt_context += "\nPlease fix the code and return the entire updated script."
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt_context)
    ])
    
    # Extract code from markdown block
    content = response.content
    new_code = content
    if "```" in content:
        # Simple extraction logic: grab what's inside the first ``` block
        parts = content.split("```")
        if len(parts) >= 3:
            # part 0 is before code, part 1 is code, part 2 is after
            code_block = parts[1]
            # Strip the language identifier (e.g. "python\n")
            if "\n" in code_block:
                new_code = code_block.split("\n", 1)[1]
            else:
                new_code = code_block
    
    return {
        "current_code": new_code.strip(),
        # We don't increment retry_count here, Reviewer will do it if it fails again
    }
