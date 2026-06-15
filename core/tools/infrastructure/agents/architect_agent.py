import logging
from langchain_core.messages import HumanMessage, SystemMessage
from tools.infrastructure.agents.coder_agent import build_coder_llm
from tools.memory.honcho_connect import retrieve_memory

logger = logging.getLogger(__name__)

def architect_node(state: dict) -> dict:
    """
    The Architect Agent.
    Retrieves the ultimate goal from Honcho memory, breaks it down,
    and provides a concrete specification for the Coder.
    """
    llm = build_coder_llm()  # Reuse the LLM setup
    messages = state.get("messages", [])
    retry_count = state.get("retry_count", 0)
    
    # The Architect only plans on the first pass. During error loops, the Coder handles the fix.
    if retry_count > 0:
        logger.info("Architect Node: Bypassing planning during retry loop.")
        return {} 

    human_task = ""
    for msg in messages:
        if isinstance(msg, HumanMessage):
            human_task += f"{msg.content}\n"

    # 1. Retrieve the top-level goal/state from Honcho
    try:
        logger.info("Architect Node: Querying Honcho for top-level context...")
        past_context = retrieve_memory(human_task, n_results=3, category="concepts")
        honcho_context = "\n".join(past_context) if past_context else "No prior Honcho context found."
    except Exception as e:
        logger.warning(f"Architect failed to fetch from Honcho: {e}")
        honcho_context = "Honcho retrieval failed."

    system_prompt = (
        "You are an elite Software Architect.\n"
        "Your task is to read the overarching user goal, evaluate the Honcho state memory, "
        "and output a precise, actionable coding specification for the Coder agent.\n"
        "Do NOT write the code yourself. Provide the architecture, file names, and logic steps."
    )

    prompt_context = (
        f"--- USER REQUEST ---\n{human_task}\n\n"
        f"--- HONCHO MEMORY (Top-Level State & Context) ---\n{honcho_context}\n\n"
        "Please provide a strict architectural plan and specification for the Coder."
    )

    logger.info("Architect Node: Generating specification for Coder...")
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt_context)
    ])
    
    logger.info("Architect Node: Specification complete.")
    return {
        "architect_instructions": response.content
    }
