import json
import re
from typing import Any, Dict, Optional

def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Robustly extracts a JSON object from text, handling markdown blocks and filler text.
    Resilient against internal backticks and verbose reasoning.
    """
    if not text:
        return None

    # Try finding the first { and last } directly as the most robust method for JSON objects
    start = text.find('{')
    end = text.rfind('}')
    
    if start != -1 and end != -1 and end > start:
        content = text[start:end+1].strip()
        try:
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            pass # Fallback to regex methods if the direct bounding fails
            
    # Fallback 1: Try to find a JSON block in markdown
    json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_match:
        content = json_match.group(1).strip()
        try:
            return json.loads(content)
        except Exception:
            pass

    # Fallback 2: Try generic code block if json specific one fails
    generic_match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if generic_match:
        content = generic_match.group(1).strip()
        try:
            return json.loads(content)
        except Exception:
            pass

    return None

def clean_llm_response(text: str) -> str:
    """
    Cleans an LLM response by removing surrounding markdown formatting and common filler phrases,
    without destroying internal backticks.
    """
    if not text:
        return ""
    
    # Strip leading/trailing backticks and language identifiers instead of global sub
    text = text.strip()
    if text.startswith("```"):
        # Remove first line which usually has ```json or ```
        parts = text.split('\n', 1)
        if len(parts) > 1:
            text = parts[1]
    if text.endswith("```"):
        text = text[:-3]
        
    return text.strip()
