"""Deterministic audits for a generated wireframe graph document.

These run BEFORE any LLM critic. There is no point asking a model whether a
diagram is a good representation of a spec if the document is structurally
invalid or half its arrows point at nothing — those are facts, not judgements,
and cheaper to check in code than to pay a model to notice.

What changed with the move off Excalidraw
-----------------------------------------
The old audits checked PIXELS: does this text string fit the width declared on
its element, does a component's bottom edge escape the grey frame it was drawn
in, how much dead space sits under the last widget. All three questions existed
only because Python was doing the layout, and all three are now answered by the
browser — flexbox does not let a child escape its parent, and CSS text does not
overflow a box that says `overflow:hidden`.

What those audits never checked is the failure that actually made the board ugly:
two backend cards occupying the same rectangle, and cards placed outside the band
that was supposed to contain them. That went unnoticed for as long as it did
partly because nothing looked for it. The equivalent question in graph terms —
"is this a well-formed graph that a layout engine can lay out" — is what is
checked here, and node overlap itself is now an invariant of dagre rather than
something to test after the fact (see scripts/audit_wireframe_layout.mjs, which
verifies that invariant against the real layout code).
"""

VALID_KINDS = {"screen", "endpoint", "entity", "integration"}
VALID_EDGE_KINDS = {"flow", "reads", "writes", "relation", "integration"}
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}

# Component types the screen renderer knows. A type outside this set still
# renders (as text), so it is a warning rather than an error.
KNOWN_COMPONENTS = {
    "header", "subheader", "text", "input", "textarea", "button", "link", "nav",
    "card", "image", "list", "table", "checkbox", "radio", "divider", "badge",
    "avatar", "row", "column", "stack", "region", "group", "panel", "section",
}


def _walk(node, out):
    if not isinstance(node, dict):
        return
    out.append(node)
    for c in node.get("children") or []:
        _walk(c, out)


def validate_scene(doc: dict) -> list:
    """Structural validity. Returns a list of human-readable problems.

    A non-empty list means the document is an ENGINE bug, not a spec defect: it
    should be surfaced rather than fed back into a repair round, because respinning
    the spec cannot fix a duplicate node id.
    """
    problems = []
    if not isinstance(doc, dict):
        return ["document is not an object"]
    if doc.get("type") != "kenbun-wireframe":
        problems.append(f"doc.type is {doc.get('type')!r}, expected 'kenbun-wireframe'")
    if not isinstance(doc.get("version"), int):
        problems.append(f"doc.version is {doc.get('version')!r}, expected an int")

    nodes = doc.get("nodes")
    edges = doc.get("edges")
    if not isinstance(nodes, list) or not nodes:
        return problems + ["document has no nodes"]
    if not isinstance(edges, list):
        return problems + ["document.edges is not a list"]

    ids = set()
    for i, n in enumerate(nodes):
        where = f"node[{i}] id={n.get('id')!r}" if isinstance(n, dict) else f"node[{i}]"
        if not isinstance(n, dict):
            problems.append(f"{where}: not an object")
            continue
        nid = n.get("id")
        if not isinstance(nid, str) or not nid:
            problems.append(f"{where}: missing or non-string id")
        elif nid in ids:
            # React Flow drops a duplicate id silently instead of erroring, so a
            # whole node would vanish from the board with no signal anywhere.
            problems.append(f"{where}: duplicate node id")
        ids.add(nid)

        kind = n.get("kind")
        if kind not in VALID_KINDS:
            problems.append(f"{where}: unknown kind {kind!r}")
            continue
        if not isinstance(n.get("label"), str) or not n.get("label"):
            problems.append(f"{where}: missing label")

        if kind == "screen":
            body = n.get("body")
            if not isinstance(body, dict):
                problems.append(f"{where}: screen has no body")
            else:
                flat = []
                _walk(body, flat)
                for c in flat:
                    if not isinstance(c.get("type"), str):
                        problems.append(f"{where}: component with no type")
        elif kind == "endpoint":
            if n.get("method") not in METHODS:
                problems.append(f"{where}: bad method {n.get('method')!r}")
            if not isinstance(n.get("path"), str) or not n.get("path"):
                problems.append(f"{where}: missing path")
        elif kind == "entity":
            if not isinstance(n.get("fields"), list):
                problems.append(f"{where}: entity fields is not a list")

    seen_edges = set()
    handles = _screen_handles(nodes)
    for i, e in enumerate(edges):
        where = f"edge[{i}] id={e.get('id')!r}" if isinstance(e, dict) else f"edge[{i}]"
        if not isinstance(e, dict):
            problems.append(f"{where}: not an object")
            continue
        if e.get("id") in seen_edges:
            problems.append(f"{where}: duplicate edge id")
        seen_edges.add(e.get("id"))
        if e.get("kind") not in VALID_EDGE_KINDS:
            problems.append(f"{where}: unknown edge kind {e.get('kind')!r}")
        for end in ("source", "target"):
            if e.get(end) not in ids:
                problems.append(f"{where}: {end} {e.get(end)!r} is not a node in this document")
        if e.get("source") == e.get("target"):
            problems.append(f"{where}: self-loop")
        sh = e.get("sourceHandle")
        if sh is not None and sh not in handles:
            # An edge anchored to a handle that no component renders detaches and
            # springs back to the node's default anchor — visible as an arrow
            # starting from the wrong place, with nothing in the console.
            problems.append(f"{where}: sourceHandle {sh!r} is not rendered by any component")

    return problems


def _screen_handles(nodes) -> set:
    out = set()
    for n in nodes:
        if not isinstance(n, dict) or n.get("kind") != "screen":
            continue
        flat = []
        _walk(n.get("body") or {}, flat)
        for c in flat:
            if c.get("handleId"):
                out.add(c["handleId"])
    return out


def audit_graph(doc: dict) -> dict:
    """Semantic quality: is anything stranded, unreachable or unwired?

    None of these are fatal — a read-only GET that no button calls is legitimate,
    and so is a screen with no CTA. They are reported so the critic and the repair
    round can tell the difference between "deliberately standalone" and "the spec
    forgot to wire this up".
    """
    nodes = [n for n in (doc.get("nodes") or []) if isinstance(n, dict)]
    edges = [e for e in (doc.get("edges") or []) if isinstance(e, dict)]

    by_kind = {}
    for n in nodes:
        by_kind.setdefault(n.get("kind"), []).append(n)

    inbound, outbound = {}, {}
    for e in edges:
        inbound.setdefault(e.get("target"), []).append(e)
        outbound.setdefault(e.get("source"), []).append(e)

    # An endpoint nothing calls AND that touches no data is floating: it is in the
    # picture but connected to nothing in it.
    stranded_endpoints = [
        n["label"] for n in by_kind.get("endpoint", [])
        if not inbound.get(n["id"]) and not outbound.get(n["id"])
    ]
    unused_entities = [
        n["label"] for n in by_kind.get("entity", [])
        if not any(e.get("kind") in ("reads", "writes") for e in inbound.get(n["id"], []))
    ]
    unreached_integrations = [
        n["label"] for n in by_kind.get("integration", [])
        if not inbound.get(n["id"])
    ]

    buttons, unknown_components, empty_screens = [], set(), []
    for n in by_kind.get("screen", []):
        flat = []
        _walk(n.get("body") or {}, flat)
        leaves = [c for c in flat if not c.get("children")]
        if not leaves:
            empty_screens.append(n["label"])
        for c in flat:
            t = c.get("type")
            if t not in KNOWN_COMPONENTS:
                unknown_components.add(str(t))
            if t == "button" and c.get("handleId"):
                buttons.append((n["label"], c.get("label"), c["handleId"]))

    wired = {e.get("sourceHandle") for e in edges if e.get("kind") == "flow"}
    unwired_buttons = [f"{s} / {lbl}" for s, lbl, h in buttons if h not in wired]

    return {
        "nodes": len(nodes),
        "edges": len(edges),
        "screens": len(by_kind.get("screen", [])),
        "endpoints": len(by_kind.get("endpoint", [])),
        "entities": len(by_kind.get("entity", [])),
        "integrations": len(by_kind.get("integration", [])),
        "buttons": len(buttons),
        "stranded_endpoints": stranded_endpoints,
        "unused_entities": unused_entities,
        "unreached_integrations": unreached_integrations,
        "unwired_buttons": unwired_buttons,
        "empty_screens": empty_screens,
        "unknown_components": sorted(unknown_components),
        # Flows the emitter could not resolve to a real button/endpoint. This is
        # the one signal here that is always a genuine spec defect.
        "unresolved_flows": doc.get("warnings") or [],
        "clean": not empty_screens and not unknown_components
        and not (doc.get("warnings") or []),
    }


# Kept under the old name so the pipeline, which calls audit_geometry(), does not
# have to care that the failure modes it names no longer involve geometry.
audit_geometry = audit_graph


def summarize_for_critic(doc: dict) -> str:
    """A compact STRUCTURAL description of the document for an LLM critic.

    The critic judges whether the diagram represents the intent. It is given the
    hierarchy and the wiring, not coordinates — there are no coordinates any more,
    and handing a model 200 numbers to not reason about was always wasted context.
    """
    nodes = [n for n in (doc.get("nodes") or []) if isinstance(n, dict)]
    edges = [e for e in (doc.get("edges") or []) if isinstance(e, dict)]
    label_of = {n.get("id"): n.get("label", "?") for n in nodes}
    lines = [f"title: {doc.get('title', '?')}", f"detail level: {doc.get('detail', '?')}", ""]

    def render(node, depth):
        pad = "  " * depth
        t = node.get("type", "?")
        lbl = node.get("label") or ""
        extra = ""
        if t in ("list", "table") and node.get("columns"):
            extra = f" columns={node['columns']}"
        elif t == "button":
            extra = f" [{node.get('variant', 'primary')} CTA]"
        elif t in ("card", "avatar") and node.get("value"):
            extra = f" value={node['value']!r}"
        elif node.get("role"):
            extra = f" role={node['role']}"
        lines.append(f"{pad}- {t}{': ' + lbl if lbl else ''}{extra}")
        for c in node.get("children") or []:
            render(c, depth + 1)

    lines.append("SCREENS:")
    for n in nodes:
        if n.get("kind") != "screen":
            continue
        lines.append(f"  screen: {n.get('label')}")
        for c in (n.get("body") or {}).get("children") or []:
            render(c, 2)

    lines.append("")
    lines.append("BACKEND:")
    for kind, header in (("endpoint", "endpoints"), ("entity", "data models"),
                         ("integration", "integrations")):
        group = [n for n in nodes if n.get("kind") == kind]
        if not group:
            continue
        lines.append(f"  {header}:")
        for n in group:
            if kind == "endpoint":
                lines.append(f"    - {n.get('label')}"
                             + (f" — {n['desc']}" if n.get("desc") else ""))
            elif kind == "entity":
                lines.append(f"    - {n.get('label')}({', '.join(n.get('fields') or [])})")
            else:
                lines.append(f"    - {n.get('label')} ({n.get('service', '')})")

    lines.append("")
    lines.append("CONNECTIONS:")
    for e in edges:
        src, tgt = label_of.get(e.get("source"), "?"), label_of.get(e.get("target"), "?")
        via = f" (button {e['label']!r})" if e.get("kind") == "flow" and e.get("label") else ""
        lines.append(f"  {src} --{e.get('kind')}--> {tgt}{via}")

    return "\n".join(lines)
