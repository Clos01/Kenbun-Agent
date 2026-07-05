import re
from typing import Optional, List, Callable, NamedTuple

class IntentHandler(NamedTuple):
    name: str
    pattern: re.Pattern
    formatter: Callable[[re.Match], Optional[str]]

# Helper function to strip trailing/leading punctuation from filenames
def clean_filename(path: str) -> str:
    # Strip trailing/leading punctuation that might be part of natural language punctuation
    cleaned = re.sub(r'^[.,?!;:_"\']+|[.,?!;:_"\']+$', '', path.strip())
    return cleaned

# Helper function to prepare queries for double-quoted argument strings
def clean_query(query: str) -> str:
    # Strip outer quotes if the user typed them
    cleaned = query.strip()
    if len(cleaned) >= 2 and (
        (cleaned.startswith('"') and cleaned.endswith('"')) or
        (cleaned.startswith("'") and cleaned.endswith("'"))
    ):
        cleaned = cleaned[1:-1].strip()
    # Replace double quotes inside with single quotes to avoid breaking CLI argument parser
    cleaned = cleaned.replace('"', "'")
    return cleaned

# Formatter functions for mapped commands
def format_scan_repo(match: re.Match) -> Optional[str]:
    return "/run scan_repo project_path=."

def format_audit(match: re.Match) -> Optional[str]:
    return "/run audit_package_safety"

def format_lint(match: re.Match) -> Optional[str]:
    fn = clean_filename(match.group(1))
    return f"/run autofix_linter file_path={fn}" if fn else None

def format_checkpoint(match: re.Match) -> Optional[str]:
    fn = clean_filename(match.group(1))
    return f"/run save_checkpoint file_path={fn} label=pre_fix" if fn else None

def format_recall(match: re.Match) -> Optional[str]:
    q = clean_query(match.group(1))
    return f'/run recall_fix error_message="{q}"' if q else None

def format_research(match: re.Match) -> Optional[str]:
    q = clean_query(match.group(1))
    return f'/run research_official_docs query="{q}"' if q else None

# Pre-compiled registry of intent handlers
INTENT_HANDLERS: List[IntentHandler] = [
    IntentHandler(
        name="scan_repo",
        pattern=re.compile(r'(?i)\b(?:scan\s+(?:the\s+|this\s+|my\s+)?(?:repo|repository|files)|project\s+map|map\s+project|repo\s+map)\b'),
        formatter=format_scan_repo
    ),
    IntentHandler(
        name="audit_package_safety",
        pattern=re.compile(r'(?i)\b(?:audit\s+package|audit\s+safety)\b'),
        formatter=format_audit
    ),
    IntentHandler(
        name="lint_file",
        pattern=re.compile(r'(?i)\blint\s+(?:file\s+)?([^\s]+)'),
        formatter=format_lint
    ),
    IntentHandler(
        name="fix_syntax",
        pattern=re.compile(r'(?i)\bfix\s+syntax\s+(?:in|for)?\s+([^\s]+)'),
        formatter=format_lint
    ),
    IntentHandler(
        name="save_checkpoint",
        pattern=re.compile(r'(?i)\bcheckpoint\s+(?:file\s+)?([^\s]+)'),
        formatter=format_checkpoint
    ),
    IntentHandler(
        name="recall_fix",
        pattern=re.compile(r'(?i)^\s*recall\s+(.+)$'),
        formatter=format_recall
    ),
    IntentHandler(
        name="research_docs",
        pattern=re.compile(r'(?i)^\s*research\s+(.+)$'),
        formatter=format_research
    )
]

def predict_tool_command(user_input: str) -> Optional[str]:
    """
    Programmatic tool predictor that maps user natural language intents
    to recommended sovereign tool run commands without using an LLM.
    """
    if not user_input or not isinstance(user_input, str):
        return None

    normalized = user_input.strip()

    for handler in INTENT_HANDLERS:
        # Search the normalized string using pre-compiled regex
        match = handler.pattern.search(normalized)
        if match:
            command = handler.formatter(match)
            if command:
                return command

    return None
