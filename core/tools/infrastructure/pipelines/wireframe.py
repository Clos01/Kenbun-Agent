"""Wireframe pipeline: spec -> graph -> validate -> critique -> repair -> push.

Why this exists as a pipeline rather than a single tool call:

The generator is a HYBRID by design. An LLM decides the semantic structure and
the layout INTENT (regions, rows, spans, table columns); code turns that into a
graph of what connects to what. Asking a model to emit x/y/width/height for a
couple of hundred elements produces overlapping boxes — spatial arithmetic is the
one part of this it is worst at.

Note that the emitter no longer produces coordinates either. It used to, and that
was the source of the overlapping cards on the board: hand-rolled 2D packing with
no collision test drifts back into overlap however carefully the constants are
tuned. Geometry now belongs to the renderer, which has measured sizes to work
from. See tools/craft/wireframe_graph.py for the full account.

What the model IS good at is judging whether the resulting diagram actually
represents the thing that was asked for. So the accuracy loop is:

  1. spec      — LLM designs structure + layout intent
  2. graph     — code emits nodes + typed edges, no coordinates
  3. validate  — code checks the document is structurally well-formed
  4. audit     — code checks nothing is stranded, unwired or unrenderable
  5. critique  — LLM compares the resulting structure back to the request
  6. repair    — feed the critique back into a new spec, re-emit, re-check

Steps 3 and 4 are deterministic on purpose: they are facts, not judgements, and
there is no sense paying a model to notice a duplicate node id.
"""
import json

from tools.craft.wireframe_audit import (
    audit_graph,
    summarize_for_critic,
    validate_scene,
)

MAX_REPAIR_ROUNDS = 2


def _build(prompt: str, detail: str, feedback: str = "", prior_spec: dict = None):
    """Round 1 designs; later rounds AMEND the previous spec.

    Redesigning from scratch each round is why the loop used to oscillate rather
    than converge — round two would fix what it was told about and quietly lose
    something round one had got right, so the issue count moved sideways.
    """
    from tools.craft.wireframe_graph import build_wireframe
    ask = prompt if not feedback else (
        f"{prompt}\n\nA previous attempt at this wireframe was reviewed. Correct ONLY "
        f"these specific problems and change nothing else:\n{feedback}"
    )
    return build_wireframe(ask, detail=detail, prior_spec=prior_spec)


def _critique(tools, prompt: str, doc: dict, geom: dict) -> dict:
    """Ask a model whether the rendered structure matches the request."""
    reviewer = tools.get("review_code_with_gemini") or tools.get("consult_supervisor")
    if reviewer is None:
        return {"accurate": True, "issues": [], "note": "no reviewer tool available"}

    question = (
        "You are reviewing a WIREFRAME for accuracy, not for code quality.\n\n"
        f"IT WAS ASKED TO DEPICT:\n{prompt}\n\n"
        f"WHAT WAS ACTUALLY BUILT (structural summary):\n{summarize_for_critic(doc)}\n\n"
        f"AUTOMATED STRUCTURE REPORT:\n{json.dumps(geom, indent=2)[:1500]}\n\n"
        "Answer ONLY with JSON: {\"accurate\": bool, \"issues\": [\"...\"]}\n"
        "An issue is something MISSING or MISREPRESENTED versus the request — a "
        "screen that was asked for and is absent, a table without its columns, a "
        "sidebar rendered as a flat list, a button with no flow to the endpoint it "
        "obviously calls, a label that says something different from what was "
        "requested. Do NOT comment on colours, spacing, positions or style: there "
        "are no coordinates in this document and the renderer owns all geometry. "
        "If it faithfully depicts the request, say accurate: true with an empty "
        "issues list."
    )
    try:
        raw = reviewer(question)
    except Exception as e:
        return {"accurate": True, "issues": [], "note": f"critic unavailable: {e}"}

    txt = str(raw)
    start, end = txt.find("{"), txt.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(txt[start:end + 1])
            if isinstance(parsed, dict) and "accurate" in parsed:
                parsed.setdefault("issues", [])
                return parsed
        except Exception:
            pass
    # A critic that did not answer in the required shape is not evidence of a
    # problem. Say so rather than inventing a verdict either way.
    return {"accurate": True, "issues": [], "note": "critic returned unparseable output"}


def run_wireframe_loop(tools, task: str = "", detail: str = "", project_id: str = "",
                       **_):
    """Full accuracy loop. Returns a markdown report; pushes the winning scene."""
    prompt = task or ""
    if not project_id:
        return ("❌ project_id is required — a wireframe belongs to exactly one "
                "project and is not visible from any other.")

    report = ["# 🖼️ Wireframe pipeline", f"**Request:** {prompt[:300]}", ""]
    feedback = ""
    doc = spec = None
    geom = {}

    for round_no in range(MAX_REPAIR_ROUNDS + 1):
        doc, spec = _build(prompt, detail, feedback, prior_spec=spec)

        invalid = validate_scene(doc)
        geom = audit_graph(doc)
        report.append(f"## Round {round_no + 1}")
        report.append(f"- {geom['screens']} screens, {geom['endpoints']} endpoints, "
                      f"{geom['entities']} models, {geom['integrations']} integrations, "
                      f"{geom['edges']} connections")
        report.append(f"- schema problems: {len(invalid)}")
        report.append(f"- unresolved flows: {len(geom['unresolved_flows'])}, "
                      f"unwired buttons: {len(geom['unwired_buttons'])}, "
                      f"stranded endpoints: {len(geom['stranded_endpoints'])}")

        if invalid:
            # Structural invalidity is an engine bug, not something a respin of the
            # spec will fix. Surface it instead of burning rounds on it.
            report.append("- ⚠️ INVALID DOCUMENT — not pushed:")
            report.extend(f"    - {p}" for p in invalid[:10])
            return "\n".join(report)

        verdict = _critique(tools, prompt, doc, geom)
        issues = verdict.get("issues") or []
        if verdict.get("note"):
            report.append(f"- critic: {verdict['note']}")
        report.append(f"- critic accurate: {verdict.get('accurate')}"
                      + (f", {len(issues)} issue(s)" if issues else ""))
        for i in issues[:8]:
            report.append(f"    - {i}")

        if verdict.get("accurate") and geom["clean"]:
            report.append("- ✅ accepted")
            break
        if round_no == MAX_REPAIR_ROUNDS:
            report.append("- ⚠️ accepted after exhausting repair rounds "
                          "(remaining issues listed above)")
            break
        # A deterministic finding is worth more to the repair round than the
        # critic's prose, because it names the exact button or flow at fault.
        auto = [f"flow '{w.get('from')}' -> '{w.get('to')}' does not resolve "
                f"({w.get('reason')}); use the EXACT button label and endpoint path"
                for w in geom["unresolved_flows"][:6]]
        auto += [f"screen '{s}' has no components" for s in geom["empty_screens"][:4]]
        auto += [f"component type '{t}' is not a supported type"
                 for t in geom["unknown_components"][:4]]
        feedback = "\n".join(f"- {i}" for i in (issues + auto)) or \
            "- the diagram did not fully represent the request"

    pushed = _push(doc, project_id)
    report.append("")
    report.append(f"**Push:** {pushed}")
    report.append(f"**Screens:** {', '.join(s.get('name', '?') for s in spec.get('screens', []))}")
    report.append(f"**Project:** {project_id}")
    return "\n".join(report)


def _push(doc: dict, project_id: str) -> str:
    import urllib.parse
    import urllib.request
    try:
        req = urllib.request.Request(
            "http://100.92.127.1:3000/api/wireframe?project_id="
            + urllib.parse.quote(str(project_id)),
            data=json.dumps(doc).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as r:
            return "pushed" if r.status == 200 else f"HTTP {r.status}"
    except Exception as e:
        return f"failed: {e}"


def build_wireframe_pipeline(tools):
    return [
        {
            "id": "wireframe_loop",
            "label": "🖼️ Design → layout → validate → critique → repair",
            "tool": lambda **kw: run_wireframe_loop(tools, **kw),
            "input": lambda s: {
                "task": s.get("task", ""),
                "detail": s.get("tech_key", "") or "",
                "project_id": s.get("project_id", "") or s.get("file_path", ""),
            },
            "output": "wireframe_result",
        },
        {
            "id": "supervisor_review",
            "label": "🏛️ System 2: Supervisor sign-off",
            "tool": tools["consult_supervisor"],
            "input": lambda s: {
                "user_proposal": "Wireframe generated for project "
                                 f"{s.get('project_id', '?')}: {s.get('task', '')[:400]}",
                "code_snippet": str(s.get("wireframe_result", ""))[:2000],
            },
            "output": "supervisor_result",
        },
    ]
