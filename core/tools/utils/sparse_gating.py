"""
Sparse L1 Tool Context Gating Network (ESL Ch. 3 & 18)
======================================================
Applies the "Bet on Sparsity" principle to agent tool routing.
Instead of injecting all 68+ MCP tool schemas into every prompt (p >> N),
computes an L1-regularized sparse projection to select the top k <= 6
most relevant tools for any given task context.
"""

import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple

# Domain keyword dictionaries for sparse feature projection
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "audit_security": [
        "security", "audit", "vulnerability", "sql", "injection", "xss",
        "sanitize", "guardrail", "supervisor", "auth", "jwt", "crypto", "safe"
    ],
    "ui_design": [
        "ui", "css", "layout", "design", "component", "tailwind", "flexbox",
        "grid", "color", "theme", "responsive", "frontend", "wireframe", "dom"
    ],
    "git_version": [
        "git", "commit", "push", "pull", "branch", "pr", "patch", "diff",
        "repo", "merge", "conflict", "checkout", "stash"
    ],
    "memory_hivemind": [
        "memory", "hivemind", "honcho", "recall", "remember", "vector",
        "embed", "chroma", "semantic", "learning", "knowledge"
    ],
    "research_docs": [
        "docs", "documentation", "search", "web", "research", "official",
        "api_spec", "reference", "find", "lookup", "explore"
    ],
    "database_orm": [
        "postgres", "database", "sql", "table", "schema", "query",
        "migration", "planka", "db", "sqlite", "rls", "column"
    ],
    "trading_webull": [
        "webull", "trade", "stock", "equity", "order", "option", "swing",
        "candlestick", "broker", "pfof", "position", "portfolio"
    ],
    "voice_audio": [
        "elevenlabs", "voice", "audio", "speech", "transcribe", "tts",
        "mic", "call", "agent_voice", "transcript"
    ],
}

# Core foundational tools that are always allowed to bypass sparsity if needed
CORE_DEFAULT_TOOLS = {"consult_supervisor", "run_code_safely"}


def soft_threshold(value: float, lambda_penalty: float) -> float:
    """
    Standard L1 Soft-Thresholding Operator (ESL Ch. 3.4.2):
    S_lambda(v) = sign(v) * max(0, |v| - lambda)
    Forces small, irrelevant weights strictly to zero (true sparsity).
    """
    if abs(value) <= lambda_penalty:
        return 0.0
    return math.copysign(abs(value) - lambda_penalty, value)


def extract_text_features(text: str) -> Set[str]:
    """Tokenizes and cleans input task string into token set."""
    tokens = re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", text.lower())
    return set(tokens)


def compute_sparse_tool_weights(
    task_description: str,
    available_tool_map: Dict[str, str],  # tool_id -> category/description
    lambda_penalty: float = 0.15,
    max_active_tools: int = 6
) -> List[Tuple[str, float]]:
    """
    Computes L1-sparse tool relevance weights for a given task description.
    Returns ranked list of (tool_id, sparse_weight) with len <= max_active_tools.
    """
    if not task_description.strip() or not available_tool_map:
        return [(t, 1.0) for t in list(available_tool_map.keys())[:max_active_tools]]

    task_tokens = extract_text_features(task_description)
    raw_scores: Dict[str, float] = {}

    for tool_id, desc in available_tool_map.items():
        tool_tokens = extract_text_features(f"{tool_id} {desc}")
        
        # 1. Direct lexical overlap
        overlap = len(task_tokens.intersection(tool_tokens))
        score = overlap * 1.0

        # 2. Semantic category matching
        for cat, keywords in CATEGORY_KEYWORDS.items():
            cat_overlap_task = len(task_tokens.intersection(keywords))
            cat_overlap_tool = len(tool_tokens.intersection(keywords))
            if cat_overlap_task > 0 and cat_overlap_tool > 0:
                score += (cat_overlap_task * cat_overlap_tool) * 0.5

        # Normalize score
        raw_scores[tool_id] = score / (len(task_tokens) + 1.0)

    # 3. Apply L1 Soft-Thresholding for exact sparsity
    sparse_scores: Dict[str, float] = {}
    for tool_id, raw_val in raw_scores.items():
        # Always retain core default tools with baseline non-zero weight
        if tool_id in CORE_DEFAULT_TOOLS:
            sparse_scores[tool_id] = max(raw_val, 0.2)
            continue

        sparse_val = soft_threshold(raw_val, lambda_penalty)
        if sparse_val > 0.0:
            sparse_scores[tool_id] = sparse_val

    # If all non-core tools were pruned, back off penalty to include top matches
    if len(sparse_scores) <= len(CORE_DEFAULT_TOOLS) and available_tool_map:
        sorted_raw = sorted(raw_scores.items(), key=lambda x: x[1], reverse=True)
        for tid, r_val in sorted_raw[:max_active_tools]:
            sparse_scores[tid] = max(r_val, 0.1)

    # Rank and clamp to max_active_tools
    ranked = sorted(sparse_scores.items(), key=lambda x: x[1], reverse=True)
    return ranked[:max_active_tools]


def filter_active_toolset(
    task_description: str,
    all_tools: Dict[str, Any],
    lambda_penalty: float = 0.15,
    max_active_tools: int = 6
) -> Dict[str, Any]:
    """
    Returns the sparse subset of all_tools relevant to the current task.
    Reduces schema payload tokens by >75%.
    """
    if len(all_tools) <= max_active_tools:
        return all_tools

    tool_desc_map = {}
    for tid, t_obj in all_tools.items():
        if hasattr(t_obj, "description"):
            tool_desc_map[tid] = t_obj.description
        elif isinstance(t_obj, dict):
            tool_desc_map[tid] = t_obj.get("description", "")
        else:
            tool_desc_map[tid] = str(t_obj)

    sparse_ranked = compute_sparse_tool_weights(
        task_description,
        tool_desc_map,
        lambda_penalty=lambda_penalty,
        max_active_tools=max_active_tools
    )

    active_tool_ids = {tid for tid, _ in sparse_ranked}
    return {tid: all_tools[tid] for tid in active_tool_ids if tid in all_tools}


# ============================================================
# LIVE REGISTRY CATALOG (the prompt-side consumer of the gate)
# ============================================================

def build_registry_tool_map() -> Dict[str, str]:
    """{tool_id -> one-line description} harvested from the live tool registry.

    Reads the registry rather than a hand-maintained constant, so the catalog
    cannot drift from what is actually registered. Returns {} if the registry
    is unavailable; callers fall back to their static text.
    """
    try:
        from tools.harvester import harvest_and_register_tools
        from tools.registry import registry
        harvest_and_register_tools()
        entries = registry.get_all_tools()
    except Exception:
        return {}

    tool_map: Dict[str, str] = {}
    for name, entry in entries.items():
        raw = (getattr(entry, "description", "") or "").strip()
        first_line = next((ln.strip() for ln in raw.splitlines() if ln.strip()), "")
        category = getattr(entry, "category", "") or ""
        tool_map[name] = f"[{category}] {first_line}" if category else first_line
    return tool_map


def render_tool_catalog(tool_map: Dict[str, str], header: str) -> str:
    """Render a {tool_id -> description} map as catalog text for a prompt."""
    lines = [header, ""]
    for i, (name, desc) in enumerate(sorted(tool_map.items()), start=1):
        lines.append(f"{i}. {name} — {desc}" if desc else f"{i}. {name}")
    return "\n".join(lines)


def gated_tool_catalog(
    task_description: str,
    max_active_tools: int = 12,
    lambda_penalty: float = 0.15,
) -> Tuple[Optional[str], Dict[str, Any]]:
    """Task-conditioned tool catalog for prompt injection.

    This is where the sparsity actually buys something: the full catalog was
    being pasted into every strategy prompt regardless of the task, so a CSS
    question paid for the Webull and ElevenLabs schemas too. Returns
    (catalog_text, stats), or (None, stats) when the registry is unavailable so
    the caller can fall back to its static catalog.
    """
    stats: Dict[str, Any] = {
        "total_tools": 0,
        "active_tools": 0,
        "full_chars": 0,
        "gated_chars": 0,
        "savings_pct": 0.0,
    }

    full_map = build_registry_tool_map()
    if not full_map:
        return None, stats

    stats["total_tools"] = len(full_map)
    full_text = render_tool_catalog(full_map, f"AVAILABLE TOOLS ({len(full_map)} total):")
    stats["full_chars"] = len(full_text)

    ranked = compute_sparse_tool_weights(
        task_description,
        full_map,
        lambda_penalty=lambda_penalty,
        max_active_tools=max_active_tools,
    )
    active = {tid: full_map[tid] for tid, _ in ranked if tid in full_map}
    if not active:
        return None, stats

    header = (
        f"RELEVANT TOOLS ({len(active)} of {len(full_map)}, "
        f"L1-gated for this task):"
    )
    gated_text = render_tool_catalog(active, header)

    stats["active_tools"] = len(active)
    stats["gated_chars"] = len(gated_text)
    if stats["full_chars"]:
        stats["savings_pct"] = round(
            (1.0 - stats["gated_chars"] / stats["full_chars"]) * 100.0, 1
        )
    return gated_text, stats
