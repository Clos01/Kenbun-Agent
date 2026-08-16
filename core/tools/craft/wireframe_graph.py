"""AI wireframe generator — graph emitter.

prompt -> LLM structured spec -> a LAYOUT-FREE graph document -> board.

Why there are no coordinates in here
------------------------------------
The previous emitter (spec_to_excalidraw) computed every x/y itself and shipped a
finished Excalidraw scene. That is where the diagram's messiness came from, and it
was structural rather than a bug you could chase:

  * Backend cards were positioned by "centre me under the button that calls me",
    with the stacking cursor keyed on the resulting exact x. Two buttons 10px apart
    produced two different keys, so their 320px-wide endpoint cards started at the
    same y and overlapped by 310px.
  * An endpoint no button calls fell back to x = fz_x + 40, which after centring
    became x = -70 — 120px OUTSIDE the left edge of the backend band it was
    supposed to sit in. Every un-flowed GET piled up out there.
  * Entities and integrations shared one stacking dict keyed by x, but were
    different widths, so they never collided in the dict and always collided on
    the canvas.
  * Component heights were hand-summed in Python, so every new component type was
    a fresh chance for content to escape its frame.

None of that is fixable by nudging constants: hand-rolled 2D packing with no
collision test will always drift back into overlap. So the split moved. Python now
emits only WHAT is connected to WHAT; the dashboard runs dagre (a real layered
graph layout, with collision as an invariant rather than an aspiration) for the
graph, and CSS flexbox for the inside of each screen mock. Neither can overlap by
construction, which is the whole point.

The LLM-facing spec schema is UNCHANGED — see WIREFRAME_SYSTEM_PROMPT in this
module. Only the render target moved.
"""
import json
import re
from typing import Optional

SCHEMA_VERSION = 1

# Component types the screen renderer knows how to draw. Anything else is drawn as
# plain text, which is a degraded but honest rendering rather than a crash.
LEAF_TYPES = {
    "header", "subheader", "text", "input", "textarea", "button", "link", "nav",
    "card", "image", "list", "table", "checkbox", "radio", "divider", "badge",
    "avatar",
}
CONTAINER_TYPES = {"row", "column", "stack", "region", "group", "panel", "section"}

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")


def _slug(s: str, fallback: str = "x") -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(s).strip().lower()).strip("-")
    return s or fallback


def _norm_key(s) -> str:
    """The join key between a flow and the thing it names.

    Flows reference buttons by label and endpoints by path, both typed by an LLM,
    so they arrive with inconsistent case and whitespace. Normalising in ONE place
    means the frontend never has to guess how the two sides were spelled.
    """
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


class _Ids:
    """Stable, collision-free node ids.

    React Flow keys nodes by id; a duplicate id silently drops a node rather than
    erroring, so uniqueness is enforced here rather than hoped for.
    """

    def __init__(self):
        self._seen = {}

    def make(self, prefix: str, name: str) -> str:
        base = f"{prefix}:{_slug(name)}"
        n = self._seen.get(base, 0)
        self._seen[base] = n + 1
        return base if n == 0 else f"{base}-{n + 1}"


def _normalize_node(node, ids: _Ids, screen_id: str, buttons: dict):
    """Turn one spec component/container into the shape the renderer consumes.

    Returns a dict with a resolved `type`, its own props, and normalised children.
    Buttons additionally get a `handleId`: React Flow can anchor an edge to a
    specific handle inside a node, so a flow arrow starts at the exact button that
    triggers it instead of at the screen's outline. That is what removes the
    "yarn ball" — the ambiguity was never the router's fault, the old arrows
    genuinely all started from the same place.
    """
    if not isinstance(node, dict):
        return {"type": "text", "label": str(node)}

    t = str(node.get("type") or "").lower()
    raw_children = node.get("components") or node.get("children") or []
    children = [_normalize_node(c, ids, screen_id, buttons) for c in raw_children]

    # A node with children and no recognised leaf type is a container, whatever it
    # called itself. Trusting the declared type alone loses whole subtrees when the
    # model invents a container name.
    if children and t not in LEAF_TYPES:
        if t not in CONTAINER_TYPES:
            t = "column"
    elif t not in LEAF_TYPES and not children:
        t = "text"

    out = {"type": t, "label": str(node.get("label") or "")}

    if children:
        out["children"] = children
    if node.get("span") is not None:
        try:
            out["span"] = max(0.01, float(node["span"]))
        except (TypeError, ValueError):
            pass
    if node.get("width") is not None:
        try:
            out["width"] = max(0.01, float(node["width"]))
        except (TypeError, ValueError):
            pass
    if node.get("role"):
        out["role"] = str(node["role"]).lower()

    if t == "button":
        variant = str(node.get("variant") or "primary").lower()
        out["variant"] = variant if variant in ("primary", "secondary") else "primary"
        handle = ids.make(f"{screen_id}#btn", out["label"] or "button")
        out["handleId"] = handle
        # Keyed by label so flow.from (an exact button label) resolves without the
        # frontend knowing anything about how handles are named.
        buttons.setdefault(_norm_key(out["label"]), {
            "screenId": screen_id, "handleId": handle, "label": out["label"],
        })
    elif t in ("list", "table"):
        cols = [str(c) for c in (node.get("columns") or []) if str(c).strip()]
        if cols:
            out["columns"] = cols
        try:
            out["rows"] = max(1, min(int(node.get("rows") or 4), 8))
        except (TypeError, ValueError):
            out["rows"] = 4
    elif t in ("card", "avatar"):
        body = node.get("value") or node.get("text") or ""
        if body:
            out["value"] = str(body)

    return out


def spec_to_graph(spec: dict, detail: str = "") -> dict:
    """Convert an LLM spec into the layout-free graph document.

    Progressive detail, unchanged from the old emitter:
      0 overview  = screens + endpoints + flows
      1 data      = + entities, endpoint->entity access, entity relationships
      2 contracts = + external integrations + request/response payloads
    """
    level = {"": 0, "overview": 0, "data": 1, "contracts": 2, "full": 2}.get(
        str(detail).lower(), 0)

    spec = spec if isinstance(spec, dict) else {}
    screens = [s for s in (spec.get("screens") or []) if isinstance(s, dict)]
    backend = spec.get("backend") if isinstance(spec.get("backend"), dict) else {}
    endpoints = [e for e in (backend.get("endpoints") or []) if isinstance(e, dict)]
    entities = [e for e in (backend.get("entities") or []) if isinstance(e, dict)]
    integrations = [i for i in (backend.get("integrations") or []) if isinstance(i, dict)]
    flows = [f for f in (backend.get("flows") or []) if isinstance(f, dict)]

    ids = _Ids()
    nodes = []
    edges = []
    buttons = {}          # normalised button label -> {screenId, handleId}
    endpoint_by_key = {}      # "post /api/x" -> node id (exact, unambiguous)
    endpoints_by_path = {}    # "/api/x" -> [(method, node id), ...] (may be many)
    entity_by_key = {}

    # ── Screens ─────────────────────────────────────────────────────────────
    for si, screen in enumerate(screens):
        name = str(screen.get("name") or f"Screen {si + 1}")
        sid = ids.make("screen", name)
        regions = [r for r in (screen.get("regions") or []) if isinstance(r, dict)]
        comps = screen.get("components") or []

        if regions:
            body = {"type": "row", "label": "", "children": [
                _normalize_node(dict(r, type="region"), ids, sid, buttons)
                for r in regions]}
        else:
            body = {"type": "column", "label": "", "children": [
                _normalize_node(c, ids, sid, buttons) for c in comps]}

        nodes.append({
            "id": sid, "kind": "screen", "label": name, "order": si, "body": body,
        })

    # ── Endpoints ───────────────────────────────────────────────────────────
    for ep in endpoints:
        method = str(ep.get("method") or "GET").upper()
        if method not in METHODS:
            method = "GET"
        path = str(ep.get("path") or "/")
        eid = ids.make("endpoint", f"{method}-{path}")
        node = {
            "id": eid, "kind": "endpoint", "method": method, "path": path,
            "label": f"{method} {path}", "desc": str(ep.get("desc") or ""),
        }
        if level >= 2 and ep.get("payload"):
            node["payload"] = _payload_text(ep["payload"])
        nodes.append(node)
        # "POST /api/tasks" is unambiguous, so it can be a direct key.
        endpoint_by_key.setdefault(_norm_key(f"{method} {path}"), eid)
        # The bare path is NOT: a REST collection is normally served by several
        # methods, so "/api/tasks" names two endpoints. Collect the candidates and
        # let _resolve_endpoint decide, instead of setdefault silently awarding the
        # path to whichever endpoint the model happened to list first.
        endpoints_by_path.setdefault(_norm_key(path), []).append((method, eid))

    # ── Entities ────────────────────────────────────────────────────────────
    if level >= 1:
        for ent in entities:
            name = str(ent.get("name") or "Entity")
            nid = ids.make("entity", name)
            fields = [str(f) for f in (ent.get("fields") or [])]
            nodes.append({"id": nid, "kind": "entity", "label": name, "fields": fields})
            entity_by_key.setdefault(_norm_key(name), nid)

    # ── Integrations ────────────────────────────────────────────────────────
    integ_ids = {}
    if level >= 2:
        for ig in integrations:
            name = str(ig.get("name") or "Service")
            nid = ids.make("integration", name)
            nodes.append({"id": nid, "kind": "integration", "label": name,
                          "service": str(ig.get("kind") or "")})
            integ_ids[nid] = ig

    # ── Edges ───────────────────────────────────────────────────────────────
    def add_edge(src, tgt, kind, label="", source_handle=None):
        if not src or not tgt or src == tgt:
            return
        eid = f"e{len(edges) + 1}:{kind}"
        e = {"id": eid, "source": src, "target": tgt, "kind": kind}
        if label:
            e["label"] = label
        if source_handle:
            e["sourceHandle"] = source_handle
        edges.append(e)

    def _resolve_endpoint(ref, prefer_write: bool = False):
        """Resolve a flow/integration target, which may or may not name a method.

        The spec schema asks for a bare `path` in flow.to, so the common CRUD case
        ("/api/tasks", served by both GET and POST) is ambiguous by construction.
        prefer_write breaks that tie toward the mutating endpoint, because the
        schema only wires a flow to a button at all when the button DOES something
        — read-only list/detail GETs are explicitly the endpoints that carry no
        flow. Without the tie-break, a "Save Task" button drew its arrow to
        GET /api/tasks purely because the model listed the read first.
        """
        key = _norm_key(ref)
        if key in endpoint_by_key:      # an explicit "post /api/tasks"
            return endpoint_by_key[key]
        candidates = endpoints_by_path.get(key) or []
        if not candidates:
            return None
        if prefer_write:
            for method, eid in candidates:
                if method != "GET":
                    return eid
        return candidates[0][1]

    # button -> endpoint
    unresolved = []
    for fl in flows:
        btn = buttons.get(_norm_key(fl.get("from")))
        tgt = _resolve_endpoint(fl.get("to"), prefer_write=True)
        if btn and tgt:
            add_edge(btn["screenId"], tgt, "flow", btn["label"], btn["handleId"])
        else:
            unresolved.append({"from": fl.get("from"), "to": fl.get("to"),
                               "reason": "unknown button" if not btn else "unknown endpoint"})

    # endpoint -> entity (reads / writes)
    if level >= 1:
        for ep, node in zip(endpoints, [n for n in nodes if n["kind"] == "endpoint"]):
            for field, kind in (("reads", "reads"), ("writes", "writes")):
                for ent_name in (ep.get(field) or []):
                    add_edge(node["id"], entity_by_key.get(_norm_key(ent_name)),
                             kind, kind)

        # entity -> entity, inferred from *_id foreign keys
        seen_rel = set()
        for ent in entities:
            src = entity_by_key.get(_norm_key(ent.get("name")))
            for f in (ent.get("fields") or []):
                fname = str(f).split(":")[0].strip().lower()
                if not (fname.endswith("_id") or fname.endswith("id")):
                    continue
                ref = fname[:-3].strip("_") if fname.endswith("_id") else fname[:-2]
                if not ref:
                    continue
                for cand in (ref, ref + "s", ref.rstrip("s")):
                    tgt = entity_by_key.get(_norm_key(cand))
                    if tgt and tgt != src:
                        key = tuple(sorted([src, tgt]))
                        if key not in seen_rel:
                            add_edge(src, tgt, "relation", fname)
                            seen_rel.add(key)
                        break

    # endpoint -> integration
    for nid, ig in integ_ids.items():
        for ep_path in (ig.get("via") or []):
            # No prefer_write here: an integration is called by whichever endpoint
            # the spec names, and a read can legitimately hit a 3rd-party service.
            add_edge(_resolve_endpoint(ep_path), nid, "integration")

    doc = {
        "type": "kenbun-wireframe",
        "version": SCHEMA_VERSION,
        "title": str(spec.get("title") or "Wireframe"),
        "detail": str(detail or "overview").lower(),
        "nodes": nodes,
        "edges": edges,
    }
    if unresolved:
        # Surfaced rather than swallowed: a flow naming a button or endpoint that
        # does not exist is a spec defect the repair round should see, and it used
        # to vanish silently as a simply-absent arrow.
        doc["warnings"] = unresolved
    return doc


def _payload_text(payload) -> str:
    """Pretty-print a payload, capped, so one verbose endpoint cannot dominate."""
    try:
        txt = payload if isinstance(payload, str) else json.dumps(payload, indent=2)
    except (TypeError, ValueError):
        txt = str(payload)
    lines = str(txt).splitlines() or [str(txt)]
    out = [ln[:60] + ("…" if len(ln) > 60 else "") for ln in lines[:14]]
    if len(lines) > 14:
        out.append(f"… (+{len(lines) - 14} more lines)")
    return "\n".join(out)


WIREFRAME_SYSTEM_PROMPT = (
    "You are a senior full-stack engineer. Given a feature request, output ONLY a JSON spec "
    "(no prose, no markdown) covering BOTH the frontend UI and the backend design. Schema:\n"
    "{\n"
    '  "title": str,\n'
    '  "screens": [ { "name": str, "components": [ { "type": <type>, "label": str, '
    '"variant": "primary"|"secondary" } ] } ],\n'
    '  "backend": {\n'
    '    "entities": [ { "name": str, "fields": ["id: uuid", "email: str", ...] } ],\n'
    '    "endpoints": [ { "method": "GET"|"POST"|"PUT"|"PATCH"|"DELETE", "path": str, "desc": str, '
    '"reads": [entityName...], "writes": [entityName...], "payload": { ...concise example JSON... } } ],\n'
    '    "flows": [ { "from": <exact button label>, "to": <endpoint path> } ],\n'
    '    "integrations": [ { "name": str, "kind": str, "via": [endpoint paths that call it] } ]\n'
    "  }\n"
    "}\n"
    "integrations = external 3rd-party services the backend depends on (e.g. ElevenLabs voice, "
    "Google/Outlook Calendar, Twilio, Stripe); 'via' lists the exact endpoint paths that call each.\n"
    "For webhook and integration-facing endpoints, include a CONCISE representative `payload` JSON "
    "object (top-level fields with example values; collapse deep nesting to {..} or [..]; keep it "
    "short — a handful of fields). Skip payload for trivial GET endpoints.\n"
    "Frontend (think like a frontend dev): logical screens, clear labels, a primary CTA per screen, "
    "realistic form fields and navigation. Allowed component types: header, subheader, text, input, "
    "textarea, button, link, nav, card, image, list, table, checkbox, radio, divider, badge, avatar.\n"
    "LAYOUT — describe the real composition, not one flat column of widgets:\n"
    "  * A screen may use `regions` instead of `components` for side-by-side areas:\n"
    '    "regions": [ {"role":"sidebar","width":0.28,"components":[...]},'
    ' {"role":"main","width":0.72,"components":[...]} ]\n'
    "    role is sidebar|main|aside; width is a RELATIVE weight, not pixels.\n"
    '  * Place components beside each other with {"type":"row","components":[{...},{...}]};'
    ' give a child {"span":2} to make it twice as wide as its siblings.\n'
    '  * Group related widgets with {"type":"section","label":"Filters","components":[...]}.\n'
    '  * A table SHOULD carry its real columns:'
    ' {"type":"table","label":"Recent Calls","columns":["Call ID","Client","Status"],"rows":5}.\n'
    '  * A card may carry body text: {"type":"card","label":"Pass rate","value":"92%"}.\n'
    "Use regions whenever the UI genuinely has a sidebar, split pane or toolbar — a flat stack "
    "for such a screen is inaccurate. Never invent x/y coordinates or pixel sizes; the renderer "
    "computes all geometry from the structure you describe.\n"
    "Backend (think like a backend dev): the data models the feature needs (typed fields), the REST "
    "endpoints powering UI actions, and flows connecting each primary button to the endpoint path it "
    "calls (use the EXACT button label in flow.from and the EXACT endpoint path in flow.to). Make "
    "endpoint reads/writes reference entity names. 1-4 screens. Keep labels short.\n"
    "COMPLETENESS: include EVERY endpoint the request names, including read endpoints "
    "that no button triggers (list/detail GETs that merely populate a table or queue). "
    "Only endpoints wired to a button get a `flow`; the rest still belong in `endpoints`. "
    "Likewise include every screen and every named UI element that was asked for — an "
    "omitted element is a wrong wireframe, not a simplified one."
)


def _parse_spec(raw: object) -> Optional[dict]:
    """Extract the spec object from a raw completion, or None if there isn't one.

    Kept separate from the retry loop so "did this endpoint answer the question"
    is one testable decision rather than control flow tangled through two loops.
    """
    txt = re.sub(r"^```(json)?", "", str(raw).strip()).strip()
    txt = re.sub(r"```$", "", txt).strip()
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    # A bare {} or a JSON object that is not a spec is a failed attempt, not a
    # successful one — without this the loop "succeeds" on garbage and the
    # caller blows up later in spec_to_graph, far from the actual cause.
    if not isinstance(obj, dict) or not obj.get("screens"):
        return None
    return obj


def _spec_endpoints():
    """The escalation ladder for spec generation, strongest rung first.

    Wireframe specs are a structured-output task, and the default gateway rung is
    whatever PRIMARY_LLM_MODEL happens to be — on lg2025 that is a local
    completion-style Ollama model (kenbun-cto) that ignores the system prompt and
    simply continues the user's sentence. Its reply is non-empty, so
    call_llm_gateway counts it a success and never advances to its own fallback;
    the caller then retried that same incapable endpoint until it gave up. So the
    ladder is owned here, where "did we get JSON" is actually known, instead of
    being delegated to a router whose only failure test is emptiness.

    Rungs that are not configured are skipped rather than attempted, so a host
    with no cloud key still degrades to the local rung instead of erroring.
    """
    from tools.infrastructure.config import settings

    # ANTHROPIC_API_KEY is a pydantic SecretStr: the object is truthy even when it
    # wraps "", so unwrap it rather than testing the wrapper.
    key = getattr(settings, "ANTHROPIC_API_KEY", None)
    key = key.get_secret_value() if hasattr(key, "get_secret_value") else key

    ladder = []
    if getattr(settings, "AUDIT_LLM_URL", "") and key:
        ladder.append((settings.AUDIT_LLM_URL, settings.AUDIT_LLM_MODEL, "audit/cloud"))

    # An EXPLICIT strong Gemini rung, rather than relying on the router's
    # last-ditch native-SDK fallback. That fallback hardcodes model_override=None,
    # which hands model choice to the cost-optimising bandit — and the bandit's
    # cheapest arm (flash-lite) answers a full-stack design brief with two screens
    # and no integrations. It is valid JSON, so nothing here would flag it; the
    # wireframe is just quietly wrong. Naming the model keeps design quality a
    # decision rather than a side effect of budget pressure.
    design_url = getattr(settings, "DESIGN_LLM_URL", "")
    design_model = getattr(settings, "DESIGN_LLM_MODEL", "")
    if design_url and design_model and getattr(settings, "GEMINI_API_KEY", None):
        ladder.append((design_url, design_model, "design/cloud"))

    # None/None = "use whatever the router is configured for", i.e. the previous
    # behaviour, retained as the last rung so this never becomes cloud-only.
    ladder.append((None, None, "default gateway"))
    return ladder


def _call_rung(url, model, sysprompt: str, msg: str) -> str:
    """Invoke ONE rung of the ladder, with no hidden substitution.

    A named rung goes straight at its endpoint. It deliberately does NOT go through
    call_llm_gateway, because that helper silently absorbs a failure and answers
    from somewhere else entirely: with the Anthropic key 401ing, a request for
    claude-sonnet-5 came back 200 OK — served by gemini-flash-lite via the router's
    last-ditch native-SDK fallback, which hardcodes model_override=None and lets
    the cost bandit choose. Nothing in the reply says so. That made escalation
    impossible to express: rung 1 "succeeded", so the ladder never advanced, and
    every wireframe was drafted by the cheapest arm no matter what was configured.
    Calling the endpoint directly means a dead rung raises, and raising is what
    lets the next rung actually get its turn.

    The final rung passes url=model=None and DOES use the gateway, on purpose —
    that is the general-purpose safety net for hosts configured differently to
    this one, and by then there is nothing left to escalate to.
    """
    if url is None and model is None:
        from tools.utils.llm_router import call_llm_gateway
        return call_llm_gateway(sysprompt, msg, max_tokens=8192)
    from tools.utils.llm_router import _make_openai_compatible_call
    return _make_openai_compatible_call(url, model, sysprompt, msg, 0.1, 8192)


def generate_spec(prompt: str, detail: str = "", prior_spec: dict = None) -> dict:
    """Produce the structured spec.

    prior_spec turns this into an AMENDMENT rather than a fresh design. Without it
    a repair round redesigns from scratch, so fixes are not cumulative — round two
    would fix what round one was told about and lose something round one had got
    right. Carrying the previous spec forward is what makes the loop converge.
    """
    from tools.utils.llm_router import call_llm_gateway
    sysprompt = WIREFRAME_SYSTEM_PROMPT
    if str(detail).lower() in ("contracts", "full"):
        sysprompt += ("\nCONTRACTS MODE: you MUST include a concise `payload` JSON object for EVERY "
                      "webhook, every integration-facing endpoint, and every POST/PUT/PATCH that "
                      "accepts a body. Do not omit payloads.")
    if prior_spec:
        sysprompt += (
            "\nAMENDMENT MODE: you are given a PREVIOUS spec that was reviewed. Return "
            "the SAME spec with ONLY the reported problems corrected. Keep every screen, "
            "component, entity, endpoint, flow and integration that was already there "
            "unless a problem says it is wrong. Do not redesign, rename or drop anything "
            "that was not complained about.")

    user_msg = f"Feature request: {prompt}"
    if prior_spec:
        user_msg += ("\n\nPREVIOUS SPEC TO AMEND:\n"
                     + json.dumps(prior_spec, indent=1)[:12000])

    failures = []
    for url, model, label in _spec_endpoints():
        raw = ""
        for attempt in range(2):
            msg = user_msg
            if attempt:
                # A repair round, not a rerun. Handing the model back its own
                # malformed output is the only thing that distinguishes attempt 2
                # from attempt 1 — an identical call to a deterministic endpoint
                # returns the identical bad answer, which is exactly how the old
                # 3-attempt loop burned every retry without learning anything.
                msg += (
                    "\n\nYour previous reply was NOT valid JSON and was rejected:\n"
                    f"<REJECTED>\n{str(raw)[:1500]}\n</REJECTED>\n"
                    "Reply with ONLY the JSON object described above — no prose, no "
                    "markdown fence, no commentary. Start with { and end with }.")
            try:
                raw = _call_rung(url, model, sysprompt, msg)
            except Exception as e:
                failures.append(f"{label} ({model}): call failed — {e}")
                break
            spec = _parse_spec(raw)
            if spec is not None:
                return spec
        failures.append(f"{label} ({model}): returned no JSON object — {str(raw)[:160]!r}")
    raise ValueError(
        "LLM failed to return a valid JSON spec on every configured endpoint.\n  "
        + "\n  ".join(failures))


def build_wireframe(prompt: str, detail: str = "", prior_spec: dict = None):
    spec = generate_spec(prompt, detail=detail, prior_spec=prior_spec)
    return spec_to_graph(spec, detail=detail), spec
