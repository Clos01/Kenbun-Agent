"""Deterministic audits for a generated Excalidraw scene.

These run BEFORE any LLM critic. There is no point asking a model whether a
diagram is a good representation of a spec if the scene is structurally invalid
or the boxes overlap — those are facts, not judgements, and cheaper to check in
code than to pay a model to notice.
"""
from tools.craft.wireframe_generator import _text_w

# Fields Excalidraw requires on every element for a scene to load cleanly.
_REQUIRED = ("id", "type", "x", "y", "width", "height", "angle", "strokeColor",
             "backgroundColor", "seed", "opacity")
_VALID_TYPES = {"rectangle", "ellipse", "diamond", "text", "line", "arrow",
                "freedraw", "image", "frame"}
_LINEAR = {"line", "arrow"}


def validate_scene(scene: dict) -> list:
    """Structural validity. Returns a list of human-readable problems."""
    problems = []
    if scene.get("type") != "excalidraw":
        problems.append(f"scene.type is {scene.get('type')!r}, expected 'excalidraw'")
    els = scene.get("elements")
    if not isinstance(els, list) or not els:
        return problems + ["scene has no elements"]

    seen = set()
    for i, e in enumerate(els):
        where = f"element[{i}] id={e.get('id')!r} type={e.get('type')!r}"
        if not isinstance(e, dict):
            problems.append(f"{where}: not an object")
            continue
        for f in _REQUIRED:
            if f not in e:
                problems.append(f"{where}: missing required field {f!r}")
        if e.get("type") not in _VALID_TYPES:
            problems.append(f"{where}: unknown element type")
        eid = e.get("id")
        if eid in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(eid)
        for f in ("x", "y", "width", "height"):
            v = e.get(f)
            if not isinstance(v, (int, float)):
                problems.append(f"{where}: {f} is {v!r}, expected a number")
        if e.get("type") == "text":
            if "text" not in e:
                problems.append(f"{where}: text element has no 'text'")
            if e.get("containerId") not in (None, *seen):
                problems.append(f"{where}: containerId points at an unknown element")
        if e.get("type") in _LINEAR:
            pts = e.get("points")
            if not isinstance(pts, list) or len(pts) < 2:
                problems.append(f"{where}: linear element needs >=2 points")

    # bindings must reference elements that exist
    for e in els:
        for b in ("startBinding", "endBinding"):
            bind = e.get(b)
            if isinstance(bind, dict) and bind.get("elementId") not in seen:
                problems.append(
                    f"element id={e.get('id')!r}: {b} references missing "
                    f"element {bind.get('elementId')!r}")
    return problems


def audit_geometry(scene: dict) -> dict:
    """Layout quality: text overflow, content escaping frames, dead space."""
    els = scene.get("elements", [])
    texts = [e for e in els if e.get("type") == "text"]
    rects = [e for e in els if e.get("type") == "rectangle"]

    overflow = []
    for e in texts:
        for line in str(e.get("text", "")).split("\n"):
            w = _text_w(line, e.get("fontSize", 16), e.get("fontFamily", 2))
            if w > e.get("width", 0) + 1.5:
                overflow.append({"text": line[:48], "needs": round(w),
                                 "has": e.get("width")})

    # Screen frames are the big grey containers.
    frames = [r for r in rects
              if r.get("backgroundColor") == "#e9ecef" and r.get("height", 0) > 100]
    escaped, dead = [], []
    for f in frames:
        fx, fy, fw, fh = f["x"], f["y"], f["width"], f["height"]
        bottoms = []
        for e in els:
            if e is f or e.get("type") in _LINEAR:
                continue   # connectors are SUPPOSED to leave the frame
            ex, ey = e.get("x", 0), e.get("y", 0)
            if fx <= ex < fx + fw and fy <= ey < fy + fh:
                bot = ey + e.get("height", 0)
                bottoms.append(bot)
                if bot > fy + fh + 2:
                    escaped.append({"id": e.get("id"),
                                    "text": str(e.get("text", ""))[:32],
                                    "bottom": round(bot),
                                    "frame_bottom": round(fy + fh)})
        if bottoms:
            dead.append(round(fy + fh - max(bottoms)))

    return {"text_overflow": overflow, "escaped_frame": escaped,
            "dead_space_px": dead, "frames": len(frames),
            "elements": len(els), "texts": len(texts),
            "clean": not overflow and not escaped}


def summarize_for_critic(scene: dict) -> str:
    """A compact STRUCTURAL description of the scene for an LLM critic.

    The critic judges whether the diagram represents the intent; handing it 200
    raw elements with coordinates wastes context on numbers it should not be
    reasoning about anyway.
    """
    els = scene.get("elements", [])
    lines = [f"scene: {len(els)} elements"]
    frames = [e for e in els if e.get("type") == "rectangle"
              and e.get("backgroundColor") == "#e9ecef"]
    lines.append(f"screen frames: {len(frames)}")
    labels = [str(e.get("text", "")).replace("\n", " / ")
              for e in els if e.get("type") == "text"]
    lines.append("labels present, in draw order:")
    for l in labels:
        if l.strip():
            lines.append(f"  - {l[:80]}")
    return "\n".join(lines)
