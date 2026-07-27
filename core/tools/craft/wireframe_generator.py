"""AI wireframe generator.

prompt -> LLM structured spec -> deterministic, professional Excalidraw scene -> board.

The LLM only produces a high-level spec (screens + typed components + backend); a
deterministic layout engine emits valid, cleanly-designed Excalidraw elements. Connections
between UI actions, API endpoints, and data models are drawn as ELEMENT-BOUND arrows so it's
always clear what is attached to what.
"""
import json
import re
import random

# ── Design system ───────────────────────────────────────────────────────────
INK = "#1e1e1e"        # primary text / borders
MUTED = "#868e96"      # secondary text
FAINT = "#ced4da"      # hairlines / placeholders
PRIMARY = "#4263eb"    # indigo accent / primary CTA / execution flow
PRIMARY_SOFT = "#edf2ff"
SURFACE = "#f8f9fa"    # card fills
WHITE = "#ffffff"
UI_FRAME = "#e9ecef"   # generic UI container fill (neutral gray)
ENTITY_HDR = "#d0bfff"  # data-layer accent (purple) — distinguishes storage from API
ENTITY_FILL = "#faf8ff"
FZONE_BG = "#f1f3f5"   # faint frontend-layer background band
BZONE_BG = "#f3f0fa"   # faint backend-layer background band

# 50px grid: all spacing is a multiple of 50 so elements align cleanly
GRID = 50
SCREEN_W = 350
PAD = 25
GAP = 20
ZONE_GAP = 150


def _snap(v):
    return round(v / 10) * 10

METHOD_COLOR = {"GET": "#2f9e44", "POST": "#4263eb", "PUT": "#f08c00", "PATCH": "#f08c00", "DELETE": "#e03131"}

COMP_H = {
    "header": 34, "subheader": 26, "text": 24, "input": 58, "textarea": 90,
    "button": 44, "link": 24, "card": 84, "nav": 52, "image": 120,
    "list": 130, "checkbox": 26, "radio": 26, "divider": 16, "avatar": 60,
    "badge": 26, "table": 150,
}


def _mk(eid, **kw):
    el = {
        "id": eid,
        "type": kw["type"],
        "x": kw["x"], "y": kw["y"], "width": kw["width"], "height": kw["height"],
        "angle": 0,
        "strokeColor": kw.get("strokeColor", INK),
        "backgroundColor": kw.get("backgroundColor", "transparent"),
        "fillStyle": kw.get("fillStyle", "solid"),
        "strokeWidth": kw.get("strokeWidth", 1),
        "strokeStyle": kw.get("strokeStyle", "solid"),
        "roughness": 0, "opacity": kw.get("opacity", 100),
        "roundness": kw.get("roundness"),
        "seed": random.randint(1, 2**31),
        "groupIds": [], "frameId": None, "boundElements": [], "link": None, "locked": False,
    }
    if kw["type"] == "text":
        txt = kw.get("text", "")
        el.update({
            "text": txt, "originalText": txt,
            "fontSize": kw.get("fontSize", 16), "fontFamily": kw.get("fontFamily", 2),
            "textAlign": kw.get("textAlign", "left"), "verticalAlign": kw.get("verticalAlign", "top"),
            "lineHeight": 1.25, "containerId": None,
        })
    if kw["type"] in ("line", "arrow"):
        el.update({
            "points": kw.get("points", [[0, 0], [kw["width"], kw["height"]]]),
            "lastCommittedPoint": None,
            "startBinding": kw.get("startBinding"), "endBinding": kw.get("endBinding"),
            "startArrowhead": None, "endArrowhead": "arrow" if kw["type"] == "arrow" else None,
        })
    return el


class Scene:
    """Element factory with auto ids + binding support."""
    def __init__(self):
        self.els = []
        self._n = 0

    def _id(self, t):
        self._n += 1
        return f"{t}-{self._n}"

    def rect(self, x, y, w, h, **kw):
        e = _mk(self._id("r"), type="rectangle", x=x, y=y, width=w, height=h, **kw)
        self.els.append(e)
        return e

    def text(self, x, y, w, s, size=15, color=INK, align="left"):
        e = _mk(self._id("t"), type="text", x=x, y=y, width=w, height=int(size * 1.3),
                text=s, fontSize=size, strokeColor=color, textAlign=align)
        self.els.append(e)
        return e

    def _linear(self, kind, a, b, pts, color, sw, arrowhead):
        e = _mk(self._id("a" if kind == "arrow" else "ln"), type=kind,
                x=pts[0][0], y=pts[0][1],
                width=pts[-1][0] - pts[0][0], height=pts[-1][1] - pts[0][1],
                strokeColor=color, strokeWidth=sw,
                points=[[p[0] - pts[0][0], p[1] - pts[0][1]] for p in pts],
                startBinding={"elementId": a["id"], "focus": 0, "gap": 6},
                endBinding={"elementId": b["id"], "focus": 0, "gap": 6})
        e["roundness"] = None            # crisp right-angle corners
        e["endArrowhead"] = "arrow" if arrowhead else None
        a["boundElements"].append({"id": e["id"], "type": kind})
        b["boundElements"].append({"id": e["id"], "type": kind})
        self.els.append(e)
        return e

    def connect_v(self, a, b, color=MUTED, lane=0):
        """Vertical-first orthogonal arrow (a.bottom -> b.top), each in its own lane."""
        ax, ay = a["x"] + a["width"] / 2, a["y"] + a["height"]
        bx, by = b["x"] + b["width"] / 2, b["y"]
        ly = ay + 26 + lane * 16      # dedicated horizontal channel in the gap
        return self._linear("arrow", a, b, [[ax, ay], [ax, ly], [bx, ly], [bx, by]], color, 2, True)

    def connect_h(self, a, b, color=MUTED, lane=0):
        """Horizontal-first orthogonal arrow (a.right -> b.left), each in its own lane."""
        ax, ay = a["x"] + a["width"], a["y"] + a["height"] / 2
        bx, by = b["x"], b["y"] + b["height"] / 2
        lx = ax + 24 + lane * 16      # dedicated vertical channel between the columns
        return self._linear("arrow", a, b, [[ax, ay], [lx, ay], [lx, by], [bx, by]], color, 2, True)

    def relate(self, a, b, lane=0):
        """Orthogonal LINE (no arrowhead) for a data-model relationship, routed on the
        right side of the data column so it never crosses the model boxes."""
        ax, ay = a["x"] + a["width"], a["y"] + a["height"] / 2
        bx, by = b["x"] + b["width"], b["y"] + b["height"] / 2
        lx = max(a["x"] + a["width"], b["x"] + b["width"]) + 30 + lane * 18
        return self._linear("line", a, b, [[ax, ay], [lx, ay], [lx, by], [bx, by]], "#9775fa", 1.5, False)


def _render_component(sc, cp, cx, cy, inner_w):
    """Render one UI component; return (height_used, button_element_or_None)."""
    t = cp.get("type", "text")
    label = cp.get("label", "")
    h = COMP_H.get(t, 24)
    btn = None
    if t == "header":
        sc.text(cx, cy, inner_w, label, size=22, color=INK)
    elif t == "subheader":
        sc.text(cx, cy, inner_w, label, size=15, color=MUTED)
    elif t == "text":
        sc.text(cx, cy, inner_w, label, size=14, color="#495057")
    elif t in ("input", "textarea"):
        fh = 40 if t == "input" else 72
        sc.text(cx, cy, inner_w, label, size=12, color=MUTED)          # label above
        # off-white field (pure white is reserved for the main canvas)
        sc.rect(cx, cy + 18, inner_w, fh, backgroundColor="#fdfdfd", strokeColor=FAINT, roundness={"type": 3})
        h = 18 + fh + 4
    elif t == "button":
        variant = (cp.get("variant") or "primary").lower()
        bg = PRIMARY if variant == "primary" else "#e9ecef"
        fg = WHITE if variant == "primary" else INK
        bw = min(inner_w, max(140, len(label) * 10 + 44))
        btn = sc.rect(cx, cy, bw, 44, backgroundColor=bg, strokeColor=bg if variant == "primary" else FAINT, roundness={"type": 3})
        sc.text(cx, cy + 13, bw, label, size=14, color=fg, align="center")
        h = 44
    elif t == "link":
        sc.text(cx, cy, inner_w, label, size=13, color=PRIMARY)
    elif t == "nav":
        sc.rect(cx, cy, inner_w, 48, backgroundColor=WHITE, strokeColor=FAINT, roundness={"type": 3})
        sc.text(cx + 14, cy + 16, inner_w - 24, label or "Navigation", size=14, color=INK)
        h = 48
    elif t in ("card", "avatar"):
        sc.rect(cx, cy, inner_w, 80, backgroundColor=SURFACE, strokeColor=FAINT, roundness={"type": 3})
        sc.text(cx + 14, cy + 12, inner_w - 24, label or "Card", size=12, color=MUTED)
        sc.text(cx + 14, cy + 38, inner_w - 24, "—", size=22, color=INK)
        h = 80
    elif t == "image":
        sc.rect(cx, cy, inner_w, 110, backgroundColor=SURFACE, strokeColor=FAINT, fillStyle="hachure", roundness={"type": 3})
        sc.text(cx + inner_w / 2 - 30, cy + 48, 80, label or "image", size=12, color=MUTED, align="center")
        h = 110
    elif t in ("list", "table"):
        rows = 4
        sc.rect(cx, cy, inner_w, 30 + rows * 26, backgroundColor=WHITE, strokeColor=FAINT, roundness={"type": 3})
        sc.rect(cx, cy, inner_w, 30, backgroundColor=SURFACE, strokeColor=FAINT)
        sc.text(cx + 12, cy + 8, inner_w - 20, label or ("Table" if t == "table" else "List"), size=12, color=INK)
        for i in range(rows):
            sc.text(cx + 12, cy + 40 + i * 26, inner_w - 24, "· ————————", size=12, color=FAINT)
        h = 30 + rows * 26
    elif t in ("checkbox", "radio"):
        sc.rect(cx, cy, 18, 18, strokeColor=INK, backgroundColor=WHITE,
                roundness={"type": 3} if t == "radio" else None)
        sc.text(cx + 26, cy, inner_w - 26, label, size=13, color=INK)
    elif t == "divider":
        sc.rect(cx, cy + 6, inner_w, 1, backgroundColor=FAINT, strokeColor=FAINT)
        h = 14
    elif t == "badge":
        bw = max(60, len(label) * 8 + 22)
        sc.rect(cx, cy, bw, 24, backgroundColor=PRIMARY_SOFT, strokeColor=PRIMARY, roundness={"type": 3})
        sc.text(cx + 10, cy + 5, bw, label, size=11, color=PRIMARY)
    else:
        sc.text(cx, cy, inner_w, label or t, size=14)
    return h, btn


def spec_to_excalidraw(spec: dict) -> dict:
    sc = Scene()
    screens = spec.get("screens", []) or []
    backend = spec.get("backend") or {}
    endpoints = backend.get("endpoints", []) or []
    entities = backend.get("entities", []) or []

    # Title
    sc.text(80, 30, 900, str(spec.get("title", "Wireframe")), size=30, color=INK)

    # ── FRONTEND ZONE ───────────────────────────────────────────────────────
    SLOT = SCREEN_W + GRID           # 50px gutter between screens
    fz_x, fz_y = 50, 90
    n_screens = max(len(screens), 1)
    fz_w = n_screens * SLOT + 50
    button_els = {}                  # label(lower) -> button rect element
    button_order = {}                # label(lower) -> center x (for endpoint ordering)
    screen_bottoms = []

    inner_x = fz_x + 40
    for si, screen in enumerate(screens):
        comps = screen.get("components", []) or []
        sx = inner_x + si * SLOT
        inner_w = SCREEN_W - 2 * PAD
        body_h = PAD
        for cp in comps:
            body_h += COMP_H.get(cp.get("type", "text"), 24) + GAP
        frame_h = max(body_h + PAD, 220)
        sc.text(sx, fz_y + 46, SCREEN_W, screen.get("name", f"Screen {si+1}"), size=17, color=INK)
        # generic UI container = neutral gray
        sc.rect(sx, fz_y + 76, SCREEN_W, frame_h, backgroundColor=UI_FRAME, strokeColor=INK, strokeWidth=2, roundness={"type": 3})
        cy = fz_y + 76 + PAD
        for cp in comps:
            used, btn = _render_component(sc, cp, sx + PAD, cy, inner_w)
            if btn is not None:
                lbl = str(cp.get("label", "")).strip().lower()
                button_els[lbl] = btn
                button_order[lbl] = sx + SCREEN_W / 2
            cy += used + GAP
        screen_bottoms.append(fz_y + 76 + frame_h)

    fz_h = (max(screen_bottoms) if screen_bottoms else fz_y + 300) - fz_y + 30
    # faint frontend-layer band behind the screens (inserted after title so it's in back)
    sc.els.insert(1, _mk("zone-frontend", type="rectangle", x=fz_x, y=fz_y, width=fz_w, height=fz_h,
                         backgroundColor=FZONE_BG, strokeColor="#dee2e6", roundness={"type": 3}))
    sc.els.insert(2, _mk("lbl-frontend", type="text", x=fz_x + 18, y=fz_y + 14, width=400, height=18,
                         text="FRONTEND · UI SCREENS", fontSize=12, strokeColor=MUTED))

    # ── BACKEND ZONE ────────────────────────────────────────────────────────
    endpoint_els = {}
    entity_els = {}
    if endpoints or entities:
        bz_y = fz_y + fz_h + ZONE_GAP

        # Order endpoints by the x-position of the UI button that calls them, so the
        # UI->API arrows run roughly parallel and don't cross each other.
        flows = backend.get("flows", []) or []
        to_srcx = {}
        for fl in flows:
            b = button_order.get(str(fl.get("from", "")).strip().lower())
            if b is not None:
                to_srcx[str(fl.get("to", "")).strip().lower()] = b
        endpoints = sorted(
            endpoints,
            key=lambda ep: to_srcx.get(str(ep.get("path", "")).strip().lower(),
                                       to_srcx.get(f"{str(ep.get('method','GET')).upper()} {ep.get('path','/')}".lower(), 9e9)),
        )

        ep_x = fz_x + 40
        ep_y = bz_y + 60
        ep_w = 320
        ent_x = ep_x + ep_w + 250
        col_gap = 78
        for ep in endpoints:
            method = str(ep.get("method", "GET")).upper()
            path = ep.get("path", "/")
            desc = ep.get("desc", "")
            col = METHOD_COLOR.get(method, MUTED)
            card = sc.rect(ep_x, ep_y, ep_w, 60, backgroundColor=WHITE, strokeColor=col, strokeWidth=2, roundness={"type": 3})
            sc.rect(ep_x, ep_y, 58, 60, backgroundColor=col, strokeColor=col)
            sc.text(ep_x, ep_y + 22, 58, method[:4], size=11, color=WHITE, align="center")
            sc.text(ep_x + 70, ep_y + 12, ep_w - 80, path, size=14, color=INK)
            if desc:
                sc.text(ep_x + 70, ep_y + 34, ep_w - 80, desc, size=11, color=MUTED)
            endpoint_els[f"{method} {path}".lower()] = card
            endpoint_els[path.lower()] = card
            ep_y += col_gap

        ent_y = bz_y + 60
        for ent in entities:
            name = ent.get("name", "Entity")
            fields = ent.get("fields", []) or []
            ew = 260
            eh = 42 + len(fields) * 24 + 12
            # data-layer accent (purple) distinguishes storage from the API layer
            ent_card = sc.rect(ent_x, ent_y, ew, eh, backgroundColor=ENTITY_FILL, strokeColor="#7048e8", strokeWidth=2, roundness={"type": 3})
            sc.rect(ent_x, ent_y, ew, 36, backgroundColor=ENTITY_HDR, strokeColor="#7048e8")
            sc.text(ent_x + 12, ent_y + 9, ew - 20, name, size=14, color=INK)
            fy = ent_y + 48
            for f in fields:
                sc.text(ent_x + 12, fy, ew - 20, str(f), size=12, color="#495057")
                fy += 24
            entity_els[name.lower()] = ent_card
            ent_y += eh + 40

        # faint backend-layer band behind the backend elements (~18% opacity: subtle)
        bz_w = (ent_x + 260) - fz_x + 120
        bz_h = max(ep_y, ent_y) - bz_y + 30
        sc.els.insert(1, _mk("zone-backend", type="rectangle", x=fz_x, y=bz_y, width=bz_w, height=bz_h,
                             backgroundColor="#b197fc", strokeColor="#e5dbff", opacity=18, roundness={"type": 3}))
        sc.els.insert(2, _mk("lbl-backend", type="text", x=fz_x + 18, y=bz_y + 16, width=400, height=18,
                             text="BACKEND · API & DATA MODELS", fontSize=12, strokeColor=MUTED))

        # Execution flow (arrowheads), each in its own lane so lines never overlap:
        # UI button -> endpoint (indigo, vertical) ; endpoint -> data model (grey, left->right)
        for i, flow in enumerate(flows):
            a = button_els.get(str(flow.get("from", "")).strip().lower())
            b = endpoint_els.get(str(flow.get("to", "")).strip().lower())
            if a is not None and b is not None:
                sc.connect_v(a, b, color=PRIMARY, lane=i)
        j = 0
        for ep in endpoints:
            method = str(ep.get("method", "GET")).upper()
            eb = endpoint_els.get(f"{method} {ep.get('path','/')}".lower())
            if eb is None:
                continue
            for ent_name in (ep.get("writes", []) or []) + (ep.get("reads", []) or []):
                tb = entity_els.get(str(ent_name).lower())
                if tb is not None:
                    sc.connect_h(eb, tb, color=MUTED, lane=j)
                    j += 1

        # Data-model RELATIONSHIPS (no arrowheads, orthogonal, right-side lanes):
        # infer FKs like "<name>_id" -> entity
        drawn = set()
        k = 0
        for ent in entities:
            src = entity_els.get(ent.get("name", "").lower())
            for f in (ent.get("fields", []) or []):
                fname = str(f).split(":")[0].strip().lower()
                if fname.endswith("_id") or fname.endswith("id"):
                    ref = fname[:-3].strip("_") if fname.endswith("_id") else fname[:-2]
                    for cand in (ref, ref + "s", ref.rstrip("s")):
                        tgt = entity_els.get(cand)
                        if tgt is not None and tgt is not src:
                            key = tuple(sorted([id(src), id(tgt)]))
                            if key not in drawn:
                                sc.relate(src, tgt, lane=k)
                                drawn.add(key)
                                k += 1
                            break

        # ── EXTERNAL INTEGRATIONS ZONE (third layer, below backend) ─────────
        integrations = backend.get("integrations", []) or []
        if integrations:
            iz_y = bz_y + bz_h + 100
            ix = fz_x + 40
            iw, ih = 240, 78
            integ_els = {}
            for ig in integrations:
                name = ig.get("name", "Service")
                kind = ig.get("kind", "")
                card = sc.rect(ix, iz_y + 52, iw, ih, backgroundColor="#e6fcf5", strokeColor="#0ca678", strokeWidth=2, roundness={"type": 3})
                sc.rect(ix, iz_y + 52, iw, 34, backgroundColor="#c3fae8", strokeColor="#0ca678")
                sc.text(ix + 14, iz_y + 61, iw - 24, name, size=14, color=INK)
                if kind:
                    sc.text(ix + 14, iz_y + 98, iw - 24, kind, size=11, color="#0b7285")
                integ_els[name.lower()] = card
                ix += iw + 50
            iz_w = (ix - 50) - fz_x + 40
            iz_h = ih + 90
            sc.els.insert(1, _mk("zone-integ", type="rectangle", x=fz_x, y=iz_y, width=max(iz_w, 400), height=iz_h,
                                 backgroundColor="#63e6be", strokeColor="#c3fae8", opacity=15, roundness={"type": 3}))
            sc.els.insert(2, _mk("lbl-integ", type="text", x=fz_x + 18, y=iz_y + 16, width=460, height=18,
                                 text="EXTERNAL INTEGRATIONS · 3RD-PARTY SERVICES", fontSize=12, strokeColor="#0b7285"))
            # endpoint -> external service (teal, downward, lane-routed)
            lane = 0
            for ig in integrations:
                ib = integ_els.get(ig.get("name", "").lower())
                for ep_path in (ig.get("via", []) or []):
                    eb = endpoint_els.get(str(ep_path).strip().lower())
                    if eb is not None and ib is not None:
                        sc.connect_v(eb, ib, color="#0ca678", lane=lane)
                        lane += 1

    return {
        "type": "excalidraw", "version": 2, "source": "kenbun-ai-wireframe",
        "elements": sc.els,
        "appState": {"viewBackgroundColor": WHITE, "gridSize": None},
    }


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
    '"reads": [entityName...], "writes": [entityName...] } ],\n'
    '    "flows": [ { "from": <exact button label>, "to": <endpoint path> } ],\n'
    '    "integrations": [ { "name": str, "kind": str, "via": [endpoint paths that call it] } ]\n'
    "  }\n"
    "}\n"
    "integrations = external 3rd-party services the backend depends on (e.g. ElevenLabs voice, "
    "Google/Outlook Calendar, Twilio, Stripe); 'via' lists the exact endpoint paths that call each.\n"
    "Frontend (think like a frontend dev): logical screens, clear labels, a primary CTA per screen, "
    "realistic form fields and navigation. Allowed component types: header, subheader, text, input, "
    "textarea, button, link, nav, card, image, list, table, checkbox, radio, divider, badge, avatar.\n"
    "Backend (think like a backend dev): the data models the feature needs (typed fields), the REST "
    "endpoints powering UI actions, and flows connecting each primary button to the endpoint path it "
    "calls (use the EXACT button label in flow.from and the EXACT endpoint path in flow.to). Make "
    "endpoint reads/writes reference entity names. 1-4 screens. Keep labels short."
)


def generate_spec(prompt: str) -> dict:
    from tools.utils.llm_router import call_llm_gateway
    raw = call_llm_gateway(WIREFRAME_SYSTEM_PROMPT, f"Feature request: {prompt}", max_tokens=3000)
    txt = re.sub(r"^```(json)?", "", raw.strip()).strip()
    txt = re.sub(r"```$", "", txt).strip()
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if not m:
        raise ValueError(f"LLM did not return JSON spec. Got: {raw[:200]}")
    return json.loads(m.group(0))


def build_wireframe(prompt: str):
    spec = generate_spec(prompt)
    scene = spec_to_excalidraw(spec)
    return scene, spec
