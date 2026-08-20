"""
Residual Patching Engine (ESL Ch. 10: Forward Stagewise Additive Modeling)
========================================================================
Implements Boosting-style self-correction for System 2.

The stagewise update is f_m(x) = f_{m-1}(x) + h_m(x), where h_m is fitted to the
residual r_m rather than to the target from scratch. Concretely that means the
healer model emits ONLY the hunks it wants to change (h_m) and this module adds
them to the existing code (f_{m-1}) -- it does not ask for, and by default does
not accept, a full-file rewrite. That distinction is the whole point: a rewrite
is a fresh fit, not a stagewise update, and it silently reformats or drops
passing code that was never part of the residual.
"""

import ast
import difflib
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("tools.audit.residual_patcher")

# Hunk format the healer is instructed to emit. Chosen over unified diff because
# models produce unreliable @@ line offsets but very reliable verbatim quotes.
SEARCH_MARKER = "<<<<<<< SEARCH"
DIVIDER_MARKER = "======="
REPLACE_MARKER = ">>>>>>> REPLACE"

_HUNK_RE = re.compile(
    re.escape(SEARCH_MARKER) + r"\n(.*?)\n" + re.escape(DIVIDER_MARKER) + r"\n(.*?)\n?" + re.escape(REPLACE_MARKER),
    re.DOTALL,
)


def _strip_code_fence(text: str) -> str:
    """Remove a surrounding ```lang ... ``` fence if present."""
    candidate = text.strip()
    if "```" not in candidate:
        return candidate
    fence = re.search(r"```[a-zA-Z0-9_+-]*\n(.*?)```", candidate, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return candidate.replace("```", "").strip()


def _top_level_defs(code: str) -> Dict[str, str]:
    """Map {qualified def name -> exact source segment} for top-level defs/classes.

    Used to prove a patch touched only what the residual pointed at. Returns {}
    when the code does not parse, in which case the caller skips the check.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {}

    segments: Dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            segment = ast.get_source_segment(code, node)
            if segment is not None:
                segments[node.name] = segment
    return segments


def _enclosing_definition(tree: ast.AST, code: str, line_no: int) -> Optional[str]:
    """Name of the innermost def/class containing line_no, if any."""
    best: Optional[Tuple[int, str]] = None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        start = getattr(node, "lineno", None)
        end = getattr(node, "end_lineno", None)
        if start is None or end is None:
            continue
        if start <= line_no <= end:
            span = end - start
            if best is None or span < best[0]:
                best = (span, node.name)
    return best[1] if best else None


def _snap_to_code_line(lines: List[str], line_no: int) -> int:
    """Snap a critique-reported line to the nearest line that is actual code.

    Audit critiques routinely point one line off, or at the comment that labels
    the defect rather than the defect itself. Anchoring the residual on a blank
    line or a comment gives the healer a target with no semantics in it, so walk
    forward (then backward) to the closest line carrying real code.
    """
    if not lines:
        return line_no

    def is_code(idx: int) -> bool:
        if idx < 0 or idx >= len(lines):
            return False
        stripped = lines[idx].strip()
        return bool(stripped) and not stripped.startswith("#")

    idx = line_no - 1  # to 0-based
    if is_code(idx):
        return line_no

    for offset in range(1, len(lines) + 1):
        if is_code(idx + offset):
            return idx + offset + 1
        if is_code(idx - offset):
            return idx - offset + 1
    return line_no


def compute_residual(code_snippet: str, critique: str) -> Dict[str, Any]:
    """
    Computes the residual error vector r_m from the audit critique and AST analysis.

    The critique supplies the error class and a rough location; the AST supplies
    the actual structure -- which line really holds code, and which function
    encloses it. Both halves matter: the critique alone points at comments and
    blank lines, and the AST alone has no idea what is wrong.
    """
    residual: Dict[str, Any] = {
        "syntax_valid": True,
        "syntax_error": None,
        "target_lines": [],
        "target_definitions": [],
        "target_source": [],
        "risk_categories": [],
        "critique": critique.strip(),
    }

    lines = code_snippet.splitlines()

    tree: Optional[ast.AST] = None
    try:
        tree = ast.parse(code_snippet)
    except SyntaxError as syn_err:
        residual["syntax_valid"] = False
        residual["syntax_error"] = str(syn_err)
        if syn_err.lineno:
            residual["target_lines"].append(syn_err.lineno)

    critique_lower = critique.lower()

    # Extract line numbers mentioned in critique (e.g., "line 12", "lines 14-16", "L22")
    raw_lines: List[int] = list(residual["target_lines"])
    for m in re.findall(r"(?:line|lines|l)\s*([0-9]+)", critique_lower):
        try:
            raw_lines.append(int(m))
        except ValueError:
            pass

    # Snap onto real code and de-duplicate, preserving order.
    snapped: List[int] = []
    for ln in raw_lines:
        if not (1 <= ln <= max(len(lines), 1)):
            continue
        fixed = _snap_to_code_line(lines, ln)
        if fixed not in snapped:
            snapped.append(fixed)
    residual["target_lines"] = snapped

    # Attach the enclosing definition and the verbatim source of each target line,
    # so the healer can quote it back exactly in a SEARCH block.
    for ln in snapped:
        if 1 <= ln <= len(lines):
            residual["target_source"].append({"line": ln, "code": lines[ln - 1]})
        if tree is not None:
            name = _enclosing_definition(tree, code_snippet, ln)
            if name and name not in residual["target_definitions"]:
                residual["target_definitions"].append(name)

    # Classify risk categories (pseudo-gradient directions)
    if any(k in critique_lower for k in ["injection", "sql", "execute", "cursor"]):
        residual["risk_categories"].append("sql_injection")
    if any(k in critique_lower for k in ["secret", "password", "token", "api_key", "hardcode"]):
        residual["risk_categories"].append("hardcoded_secret")
    if any(k in critique_lower for k in ["tenant", "isolation", "x-tenant-id", "rls"]):
        residual["risk_categories"].append("tenancy_isolation")
    if any(k in critique_lower for k in ["xss", "sanitize", "escape", "html"]):
        residual["risk_categories"].append("xss_vulnerability")
    if any(k in critique_lower for k in ["infinite", "loop", "timeout", "blocking"]):
        residual["risk_categories"].append("concurrency_block")

    return residual


def build_residual_prompt(code_snippet: str, residual: Dict[str, Any], user_proposal: str) -> Tuple[str, str]:
    """
    Constructs a stagewise residual prompt that asks for h_m -- the hunks alone --
    rather than a regenerated file.
    """
    system_prompt = (
        "You are the Forward Stagewise Residual Patcher in Kenbun System 2 (ESL Ch. 10 Boosting).\n"
        "You emit a MINIMAL PATCH that eliminates the residual defect. You do NOT rewrite the file.\n"
        "RULES:\n"
        "1. Fix ONLY the lines identified in the residual. Leave every other line untouched.\n"
        "2. Do NOT reformat, rename, reorder, or 'improve' anything outside the residual.\n"
        "3. Output ONE OR MORE hunks in EXACTLY this format and nothing else:\n"
        f"{SEARCH_MARKER}\n"
        "<verbatim lines copied from the current code, including indentation>\n"
        f"{DIVIDER_MARKER}\n"
        "<the replacement lines>\n"
        f"{REPLACE_MARKER}\n"
        "4. The SEARCH block must match the current code EXACTLY, character for character.\n"
        "5. Keep each SEARCH block as small as possible while remaining unique in the file.\n"
        "6. No prose, no explanation, no markdown fences around the hunks."
    )

    if residual["target_lines"]:
        targets_str = f"Target Lines: {residual['target_lines']}"
    else:
        targets_str = "Target: Whole block review"

    if residual["risk_categories"]:
        risks_str = f"Risk Classes: {', '.join(residual['risk_categories'])}"
    else:
        risks_str = "General quality"

    defs_str = ""
    if residual.get("target_definitions"):
        defs_str = f"- Enclosing Definitions: {', '.join(residual['target_definitions'])}\n"

    source_str = ""
    if residual.get("target_source"):
        quoted = "\n".join(f"    L{item['line']}: {item['code']}" for item in residual["target_source"])
        source_str = f"- Offending Source:\n{quoted}\n"

    # The code is numbered so the model can align the residual's line refs with
    # what it is quoting, but it must still copy SEARCH blocks WITHOUT the numbers.
    numbered = "\n".join(
        f"{i + 1:>4} | {line}" for i, line in enumerate(code_snippet.splitlines())
    )

    user_message = (
        f"USER OBJECTIVE: {user_proposal}\n\n"
        f"CURRENT CODE f_{{m-1}}(x) (line numbers are for reference only -- never include them in a SEARCH block):\n"
        f"```python\n{numbered}\n```\n\n"
        f"RESIDUAL ERROR r_m:\n"
        f"- {targets_str}\n"
        f"{defs_str}"
        f"{source_str}"
        f"- {risks_str}\n"
        f"- Critique: {residual['critique']}\n\n"
        f"Emit the minimal patch h_m now, as SEARCH/REPLACE hunks only:"
    )

    return system_prompt, user_message


def parse_patch_hunks(healed_candidate: str) -> List[Tuple[str, str]]:
    """Extract [(search_text, replace_text), ...] from the healer's output."""
    if not healed_candidate:
        return []
    return [(m.group(1), m.group(2)) for m in _HUNK_RE.finditer(healed_candidate)]


def apply_patch_hunks(original_code: str, hunks: List[Tuple[str, str]]) -> Tuple[Optional[str], List[str]]:
    """Apply SEARCH/REPLACE hunks to original_code.

    Returns (patched_code, errors). patched_code is None if any hunk failed to
    apply -- a partially applied patch is worse than no patch, so it is all or
    nothing. A SEARCH block that matches more than once is rejected rather than
    guessed at.
    """
    errors: List[str] = []
    patched = original_code

    for idx, (search, replace) in enumerate(hunks):
        if not search.strip():
            errors.append(f"hunk {idx + 1}: empty SEARCH block")
            continue

        occurrences = patched.count(search)
        if occurrences == 0:
            # Retry ignoring trailing whitespace per line, the one deviation
            # models make constantly that carries no semantic meaning.
            relaxed = "\n".join(line.rstrip() for line in search.splitlines())
            relaxed_body = "\n".join(line.rstrip() for line in patched.splitlines())
            if relaxed_body.count(relaxed) == 1:
                patched = relaxed_body.replace(relaxed, replace, 1)
                continue
            errors.append(f"hunk {idx + 1}: SEARCH block not found in source")
            continue
        if occurrences > 1:
            errors.append(f"hunk {idx + 1}: SEARCH block is ambiguous ({occurrences} matches)")
            continue

        patched = patched.replace(search, replace, 1)

    if errors:
        return None, errors
    return patched, []


def apply_stagewise_patch(
    original_code: str,
    healed_candidate: str,
    allow_full_rewrite: bool = True,
) -> str:
    """
    Validates and accepts the stagewise update f_m(x) = f_{m-1}(x) + h_m(x).

    Preferred path is hunk application. A full-file rewrite is accepted only as a
    fallback (models do disobey the format), is logged as such, and is still
    required to parse. Callers wanting the strict stagewise guarantee pass
    allow_full_rewrite=False.

    Returns original_code unchanged when the update cannot be trusted.
    """
    result, _ = apply_stagewise_patch_verbose(
        original_code, healed_candidate, allow_full_rewrite=allow_full_rewrite
    )
    return result


def apply_stagewise_patch_verbose(
    original_code: str,
    healed_candidate: str,
    allow_full_rewrite: bool = True,
) -> Tuple[str, Dict[str, Any]]:
    """apply_stagewise_patch, plus a stats dict describing what actually happened.

    The stats are what make the 'minimal patch' claim checkable instead of
    asserted: mode, hunk count, how many lines really changed, and which
    top-level definitions were modified.
    """
    stats: Dict[str, Any] = {
        "mode": "rejected",
        "hunks": 0,
        "changed_lines": 0,
        "total_lines": len(original_code.splitlines()),
        "modified_definitions": [],
        "collateral_definitions": [],
        "errors": [],
    }

    if not healed_candidate or not healed_candidate.strip():
        stats["errors"].append("empty candidate")
        return original_code, stats

    orig_had_valid_syntax = True
    try:
        ast.parse(original_code)
    except SyntaxError:
        orig_had_valid_syntax = False

    hunks = parse_patch_hunks(healed_candidate)
    candidate: Optional[str] = None

    if hunks:
        stats["hunks"] = len(hunks)
        candidate, errors = apply_patch_hunks(original_code, hunks)
        if candidate is None:
            stats["errors"].extend(errors)
            logger.warning(f"Stagewise hunks failed to apply: {errors}")
            return original_code, stats
        stats["mode"] = "stagewise"
    else:
        if not allow_full_rewrite:
            stats["errors"].append("no SEARCH/REPLACE hunks found and full rewrite disallowed")
            logger.warning("Healer returned no hunks and full rewrite is disallowed. Rejecting patch.")
            return original_code, stats
        candidate = _strip_code_fence(healed_candidate)
        stats["mode"] = "full_rewrite"
        logger.warning(
            "Healer ignored the stagewise hunk format and returned a whole block; "
            "accepting as a full rewrite fallback."
        )

    if not candidate or candidate.strip() == original_code.strip():
        stats["mode"] = "rejected"
        stats["errors"].append("candidate identical to original")
        return original_code, stats

    if orig_had_valid_syntax:
        try:
            ast.parse(candidate)
        except SyntaxError as e:
            stats["mode"] = "rejected"
            stats["errors"].append(f"syntax error: {e}")
            logger.warning(f"Healed candidate introduced syntax error: {e}. Rejecting patch.")
            return original_code, stats

    # Measure what actually moved.
    orig_lines = original_code.splitlines()
    new_lines = candidate.splitlines()
    changed = sum(
        1
        for d in difflib.ndiff(orig_lines, new_lines)
        if d.startswith("- ") or d.startswith("+ ")
    )
    stats["changed_lines"] = changed

    before_defs = _top_level_defs(original_code)
    after_defs = _top_level_defs(candidate)
    if before_defs and after_defs:
        for name, segment in before_defs.items():
            if name in after_defs and after_defs[name] != segment:
                stats["modified_definitions"].append(name)
            elif name not in after_defs:
                stats["collateral_definitions"].append(f"{name} (removed)")

        targeted = set(stats["modified_definitions"])
        for name in after_defs:
            if name not in before_defs:
                stats["collateral_definitions"].append(f"{name} (added)")
        if stats["mode"] == "stagewise" and len(targeted) > 1:
            logger.info(f"Stagewise patch touched {len(targeted)} definitions: {sorted(targeted)}")

    return candidate, stats
