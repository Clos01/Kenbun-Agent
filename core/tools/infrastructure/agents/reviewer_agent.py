import logging
from tools.execution.e2b_runner import run_code_safely

logger = logging.getLogger(__name__)

def truncate_stack_trace(error_log: str, max_lines: int = 100) -> str:
    """
    Truncates a large stack trace or error log to prevent context window blowout.
    Returns the first and last `max_lines // 2` lines.
    """
    if not error_log:
        return ""
        
    lines = error_log.split("\n")
    if len(lines) <= max_lines:
        return error_log
        
    head = lines[: max_lines // 2]
    tail = lines[-max_lines // 2 :]
    
    return "\n".join(
        head + 
        [f"... [TRUNCATED {len(lines) - max_lines} LINES] ..."] + 
        tail
    )

def reviewer_node(state: dict) -> dict:
    """
    The Reviewer Agent.
    Executes the Coder's code in the E2B secure sandbox, evaluates the results,
    and intelligently truncates errors if they are too large.
    """
    current_code = state.get("current_code", "")
    language = state.get("language", "python")
    retry_count = state.get("retry_count", 0)
    
    if not current_code:
        return {
            "test_results": "No code provided to review.",
            "error_log": "",
            "is_success": False,
            "retry_count": retry_count + 1
        }
    
    # Execute code securely via E2B
    execution_result = run_code_safely(code=current_code, language=language)
    
    # Simple heuristic to check success (the runner outputs '✅ SUCCESS')
    is_success = "✅ SUCCESS" in execution_result
    
    # Extract just the stderr if it failed to pass it back efficiently
    error_log = ""
    if not is_success and "### stderr" in execution_result:
        try:
            parts = execution_result.split("### stderr\n```\n")
            if len(parts) > 1:
                raw_stderr = parts[1].split("\n```")[0]
                error_log = truncate_stack_trace(raw_stderr)
        except Exception as e:
            logger.error(f"Failed to parse stderr: {e}")
            error_log = execution_result # Fallback to entire result
    
    return {
        "test_results": execution_result,
        "error_log": error_log,
        "is_success": is_success,
        "retry_count": retry_count + 1 if not is_success else retry_count
    }
