import re
import copy
from core.tools.infrastructure.ai_gateway import build_system_prompt
from core.tools.utils.console_ui import C_P, C_R, C_D
from core.tools.utils.bayesian import get_best_tool

def process_edge_routing(user_input: str, history: list, actual_url: str, actual_model: str, llm_model: str, env: dict):
    """
    Scans the user input for edge routing tags (@local, @lmstudio, or specific models like @gemma).
    If found, overrides the URL and Model, and returns a deeply copied history 
    with a dynamically regenerated nano-tier system prompt to prevent hallucination.
    """
    active_history = history
    
    # Extract candidate models
    pull_models = env.get("OLLAMA_PULL_MODELS", "")
    candidates = [m for m in pull_models.split() if m.strip()]
    default_edge = env.get("OLLAMA_EDGE_MODEL", "deepseek-r1:8b")
    if default_edge not in candidates:
        candidates.append(default_edge)

    # 1. Check for specific dynamic tags like @gemma or @deepseek
    tags = re.findall(r'@([a-zA-Z0-9_-]+)\b', user_input)
    matched_specific_model = None
    
    if tags:
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower in ["local", "fast", "ollama", "lmstudio"]:
                continue # Skip reserved generic tags
            
            # Collect all candidates that fuzzy match the tag
            matches = [c for c in candidates if tag_lower in c.lower()]
            
            if matches:
                if len(matches) == 1:
                    matched_specific_model = matches[0]
                else:
                    # Collision detected! Delegate to Bayesian Router to pick the best variant
                    best_match, _ = get_best_tool(category="local_routing", candidate_tools=matches)
                    matched_specific_model = best_match
                break

    ollama_url = env.get("OLLAMA_API_BASE", "http://localhost:11434/v1")

    if matched_specific_model:
        actual_url = ollama_url
        actual_model = matched_specific_model
        print(f"\n{C_P}⚡ Edge Router Active: Direct Model Override -> {actual_model}{C_R}")
        
        active_history = copy.deepcopy(history)
        if active_history and active_history[0]["role"] == "system":
            active_history[0]["content"] = build_system_prompt("nano", actual_model)

    elif re.search(r'@(local|fast|ollama)\b', user_input, re.IGNORECASE):
        actual_url = ollama_url
        
        if candidates:
            best_model, confidence = get_best_tool(category="local_routing", candidate_tools=candidates)
            actual_model = best_model
        else:
            actual_model = default_edge

        print(f"\n{C_P}⚡ Edge Router Active: Bayesian Engine selected GPU model ({actual_model}){C_R}")
        
        active_history = copy.deepcopy(history)
        if active_history and active_history[0]["role"] == "system":
            active_history[0]["content"] = build_system_prompt("nano", actual_model)
            
    elif re.search(r'@lmstudio\b', user_input, re.IGNORECASE):
        actual_url = "http://localhost:1234/v1"
        actual_model = env.get("LMSTUDIO_EDGE_MODEL", "local-model")
        print(f"\n{C_P}⚡ Edge Router Active: Offloading task to LM Studio ({actual_model}){C_R}")
        
        active_history = copy.deepcopy(history)
        if active_history and active_history[0]["role"] == "system":
            active_history[0]["content"] = build_system_prompt("nano", actual_model)
            
    return active_history, actual_url, actual_model
