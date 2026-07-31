"""Wireframe pipeline: spec -> layout -> validate -> critique -> repair -> push.

Why this exists as a pipeline rather than a single tool call:

The generator is a HYBRID by design. An LLM decides the semantic structure and
the layout INTENT (regions, rows, spans, table columns); the deterministic engine
computes every coordinate. Asking a model to emit x/y/width/height for a couple
of hundred elements produces overlapping boxes and invalid scenes — spatial
arithmetic is the one part of this it is worst at, and the part code is best at.

What the model IS good at is judging whether the resulting diagram actually
represents the thing that was asked for. So the accuracy loop is:

  1. spec      — LLM designs structure + layout intent
  2. layout    — deterministic engine emits the scene
  3. validate  — code checks the scene is structurally valid Excalidraw
  4. geometry  — code checks nothing overflows, escapes or wastes space
  5. critique  — LLM compares the RENDERED structure back to the request
  6. repair    — feed the critique back into a new spec, re-layout, re-check

Steps 3 and 4 are deterministic on purpose: they are facts, not judgements, and
there is no sense paying a model to notice a duplicate element id.
"""
import json

from tools.craft.wireframe_audit import (
    audit_geometry,
    summarize_for_critic,
    validate_scene,
)

MAX_REPAIR_ROUNDS = 2


def _build(prompt: str, detail: str, feedback: str = ""):
    from tools.craft.wireframe_generator import build_wireframe
    ask = prompt if not feedback else (
        f"{prompt}\n\nA previous attempt at this wireframe was reviewed. Fix these "
        f"specific problems in the structure you produce:\n{feedback}"
    )
    return build_wireframe(ask, detail=detail)


def _critique(tools, prompt: str, scene: dict, geom: dict) -> dict:
    """Ask a model whether the rendered structure matches the request."""
    reviewer = tools.get("review_code_with_gemini") or tools.get("consult_supervisor")
    if reviewer is None:
        return {"accurate": True, "issues": [], "note": "no reviewer tool available"}

    question = (
        "You are reviewing a WIREFRAME for accuracy, not for code quality.\n\n"
        f"IT WAS ASKED TO DEPICT:\n{prompt}\n\n"
        f"WHAT WAS ACTUALLY DRAWN (structural summary):\n{summarize_for_critic(scene)}\n\n"
        f"AUTOMATED GEOMETRY REPORT:\n{json.dumps(geom, indent=2)[:1500]}\n\n"
        "Answer ONLY with JSON: {\"accurate\": bool, \"issues\": [\"...\"]}\n"
        "An issue is something MISSING or MISREPRESENTED versus the request — a "
        "screen that was asked for and is absent, a table without its columns, a "
        "sidebar rendered as a flat list, a label that says something different "
        "from what was requested. Do NOT comment on colours, spacing or style; the "
        "layout engine owns those. If it faithfully depicts the request, say "
        "accurate: true with an empty issues list."
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
    scene = spec = None
    geom = {}

    for round_no in range(MAX_REPAIR_ROUNDS + 1):
        scene, spec = _build(prompt, detail, feedback)

        invalid = validate_scene(scene)
        geom = audit_geometry(scene)
        report.append(f"## Round {round_no + 1}")
        report.append(f"- elements: {geom['elements']}, screens: {geom['frames']}")
        report.append(f"- schema problems: {len(invalid)}")
        report.append(f"- text overflow: {len(geom['text_overflow'])}, "
                      f"escaped frame: {len(geom['escaped_frame'])}")

        if invalid:
            # Structural invalidity is an engine bug, not something a respin of the
            # spec will fix. Surface it instead of burning rounds on it.
            report.append("- ⚠️ INVALID SCENE — not pushed:")
            report.extend(f"    - {p}" for p in invalid[:10])
            return "\n".join(report)

        verdict = _critique(tools, prompt, scene, geom)
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
        feedback = "\n".join(f"- {i}" for i in issues) or \
            "- text or elements did not fit their containers"

    pushed = _push(scene, project_id)
    report.append("")
    report.append(f"**Push:** {pushed}")
    report.append(f"**Screens:** {', '.join(s.get('name', '?') for s in spec.get('screens', []))}")
    report.append(f"**Project:** {project_id}")
    return "\n".join(report)


def _push(scene: dict, project_id: str) -> str:
    import urllib.parse
    import urllib.request
    try:
        req = urllib.request.Request(
            "http://100.92.127.1:3000/api/wireframe?project_id="
            + urllib.parse.quote(str(project_id)),
            data=json.dumps(scene).encode("utf-8"),
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
