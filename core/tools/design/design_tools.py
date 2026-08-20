import json
import logging
import time
import urllib.parse as _urlparse
import urllib.request
from typing import Any, Optional

from tools.infrastructure.config import settings
from tools.registry import sovereign_tool
from tools.utils.helpers import debug_log, silence_stdout

logger = logging.getLogger("tools.design")


@sovereign_tool()
def ask_ui_expert(query: str) -> str:
    """Consult the Lead UI Designer for CSS/Layout help."""
    from tools.audit.ui_designer import consult_ui_expert
    return consult_ui_expert(query)


@sovereign_tool()
def get_design_tokens() -> str:
    """Returns the current Design System tokens from DESIGN.md."""
    from tools.design.oracle import DesignOracle
    rules = DesignOracle.get_rules()
    if "error" in rules:
        return json.dumps({"error": rules["error"], "tokens": {}}, indent=2)
    return json.dumps(rules.get("tokens", {}), indent=2)


@sovereign_tool()
def write_website_content(topic: str, context: str = "", length: str = "medium") -> str:
    """
    Generates human-like website content without AI jargon like 'bespoke' or 'delve'.
    Use this instead of generic Gemini/Claude for copywriting.
    """
    start_time = time.time()
    with silence_stdout():
        debug_log("DEBUG: write_website_content tool started")
        from tools.craft.content_generator import generate_human_content
        res = generate_human_content(topic=topic, context=context, length=length)
        debug_log(f"DEBUG: Total tool execution took {time.time() - start_time:.2f}s")
        return res


@sovereign_tool()
def generate_wireframe(prompt: str, project_id: str = "", detail: str = "") -> str:
    """Generate a UI + backend architecture wireframe from a natural-language feature
    description and push it to that PROJECT'S Wireframe canvas on /board.
    """
    project_id = str(project_id or "").strip()
    if not project_id:
        return ("ERROR: project_id is required. A wireframe belongs to exactly one project "
                "and is not visible from any other. Run planka_get_structure() to find the "
                "project id, then pass it as project_id.")

    with silence_stdout():
        try:
            from tools.craft.wireframe_graph import build_wireframe
            doc, spec = build_wireframe(prompt, detail=detail)
        except Exception as e:
            return f"ERROR: wireframe generation failed: {e}"
        try:
            body = json.dumps(doc).encode("utf-8")
            req = urllib.request.Request(
                "http://100.92.127.1:3000/api/wireframe?project_id="
                + _urlparse.quote(project_id),
                data=body,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                pushed = (r.status == 200)
        except Exception as e:
            return (f"⚠️ Wireframe built ({len(doc['nodes'])} nodes) but push to board failed: {e}. "
                    f"The dashboard /api/wireframe endpoint may be unreachable.")
    screens = [s.get("name", "?") for s in spec.get("screens", [])]
    return (
        f"✅ Wireframe **{spec.get('title', 'Untitled')}** {'pushed to /board' if pushed else 'built'}.\n"
        f"• Screens: {', '.join(screens) or '(none)'}\n"
        f"• Nodes: {len(doc['nodes'])}, connections: {len(doc['edges'])}\n"
        f"• Project: {project_id}\n"
        f"Open the board for THIS project → **Wireframe** tab (reload the canvas to view)."
    )
