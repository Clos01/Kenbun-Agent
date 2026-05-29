from pathlib import Path

# Assuming PROJECT_ROOT is available globally or passed around
# For simplicity, let's redefine it here based on common project structure.
# In a real scenario, this might be imported from path_utils or config.
from tools.infrastructure.config import settings

def get_project_root_from_helpers():
    return settings.PROJECT_ROOT

PROJECT_ROOT_FOR_HELPERS = get_project_root_from_helpers()

def _prune_log(log_str: str, max_chars: int = 8000) -> str:
    """Aggressively prunes log strings to keep them within LLM context limits."""
    if not log_str or len(log_str) <= max_chars:
        return log_str or ""
    
    # Keep the first 10% and the last 90% of the allowed limit
    head_size = int(max_chars * 0.1)
    tail_size = max_chars - head_size - 100 # -100 for the truncation message
    
    return f"{log_str[:head_size]}\n\n... [TRUNCATED {len(log_str) - max_chars} CHARS FOR CONTEXT EFFICIENCY] ...\n\n{log_str[-tail_size:]}"


def build_context(state: dict) -> str:
    """Build a context string from accumulated state for Gemini."""
    parts = []
    if state.get("repo_map"):
        # Truncate repo map to keep prompts efficient
        parts.append(f"PROJECT STRUCTURE:\n{_prune_log(state['repo_map'], 3000)}")
    if state.get("past_fixes") and "No past fixes" not in state["past_fixes"]:
        parts.append(f"PAST FIXES:\n{_prune_log(state['past_fixes'], 1500)}")
    if state.get("memory_result"):
        lessons_list = []
        for lesson in state["memory_result"]:
            lessons_list.append(f"- **Task:** {lesson.get('task')}\n  **Fix:** {lesson.get('fix')}")
        parts.append(f"HISTORIC HIVEMIND LESSONS:\n" + "\n".join(lessons_list))
    if state.get("research_result"):
        parts.append(f"RESEARCH:\n{_prune_log(state['research_result'], 2000)}")
    parts.append(f"TASK: {state['task']}")
    return "\n\n---\n\n".join(parts)


def detect_language(file_path: str) -> str:
    """Detect language from file extension."""
    ext = Path(file_path).suffix.lower()
    if ext in (".js", ".jsx", ".ts", ".tsx", ".mjs"):
        return "node"
    return "python"
