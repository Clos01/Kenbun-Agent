import json
import re
from typing import Any, Dict, Optional


def _repair_truncated_json(text: str) -> Optional[str]:
    """
    Best-effort repair of JSON that was cut off by an LLM token budget.

    Handles the common LM Studio / small-model failure mode where the model
    runs out of tokens mid-string and leaves us with something like:
        {"status": "REVIEW_NEEDED", "critique": "The proposal looks risky because
    Strategy:
      1. Strip everything before the first `{`.
      2. Walk the text tracking string state and brace/bracket depth.
      3. If we hit EOF while inside a string, close it.
      4. Close every still-open `{` or `[` in reverse order.
      5. Trim a trailing comma if one is now dangling before the auto-close.
    Returns the repaired JSON string, or None if no opening `{` was found.
    """
    if not text:
        return None
    start = text.find('{')
    if start == -1:
        return None
    body = text[start:]

    in_string = False
    escape = False
    stack = []  # entries: '{' or '['
    for ch in body:
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            stack.append('}')
        elif ch == '[':
            stack.append(']')
        elif ch in ('}', ']') and stack and stack[-1] == ch:
            stack.pop()

    repaired = body
    if in_string:
        repaired += '"'

    # Drop a dangling comma if it's now the last non-whitespace char
    stripped = repaired.rstrip()
    if stripped.endswith(','):
        repaired = stripped[:-1]

    # Close still-open containers in reverse order
    while stack:
        repaired += stack.pop()

    return repaired


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Robustly extracts a JSON object from text, handling markdown blocks and filler text.
    Resilient against internal backticks, verbose reasoning, AND truncated payloads
    from small local LLMs that ran out of output tokens mid-string.
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

    # Fallback 3: Repair-and-retry for truncated JSON (LM Studio truncation case).
    # This is the last resort — we'd rather return a slightly-imperfect dict than
    # bubble up "Parse failure" to the user.
    repaired = _repair_truncated_json(text)
    if repaired:
        try:
            return json.loads(repaired)
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
