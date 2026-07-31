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
# Colors are all from Excalidraw's native (open-color) palette so the diagram matches the
# stroke/background swatches in Excalidraw's own preferences panel and stays editable in-app.
INK = "#1e1e1e"        # Excalidraw black — text / borders
MUTED = "#868e96"      # Excalidraw gray-6 — secondary text
FAINT = "#ced4da"      # Excalidraw gray-4 — hairlines / placeholders
PRIMARY = "#1971c2"    # Excalidraw blue (default swatch) — CTA / execution flow
PRIMARY_SOFT = "#a5d8ff"  # Excalidraw blue background swatch
SURFACE = "#f8f9fa"    # Excalidraw gray-0 — card fills
WHITE = "#ffffff"
UI_FRAME = "#e9ecef"   # Excalidraw gray-2 — generic UI container fill
ENTITY_HDR = "#d0bfff"  # Excalidraw violet background swatch — data layer
ENTITY_FILL = "#f3f0ff"  # Excalidraw violet-0
FZONE_BG = "#f1f3f5"   # Excalidraw gray-1 — frontend band
BZONE_BG = "#f3f0fa"   # violet tint — backend band

# 50px grid: all spacing is a multiple of 50 so elements align cleanly
GRID = 50
SCREEN_W = 350
PAD = 25
GAP = 20
ZONE_GAP = 150


def _snap(v):
    return round(v / 10) * 10


# ── Text fitting ────────────────────────────────────────────────────────────
# Excalidraw text elements do not wrap or clip on their own: the declared width is
# metadata, and the string renders at whatever width it wants. Anything longer than
# the space between its neighbours simply runs under them and gets visually chopped
# mid-word by the enclosing panel — "Market Scanners" rendering as "Market Sca".
# Every sc.text() caller already passes the available width, so measure against it.
#
# PROPORTIONAL glyph advances, as a fraction of font size.
#
# A single average per font is wrong in both directions on real labels: "Illinois"
# and "Mammogram" are the same length but nowhere near the same width, so a flat
# factor either clips the wide one or ellipsises the narrow one early. These are
# per-character advances for a humanist sans (Excalidraw's default text font),
# grouped by the widths that actually differ.
_NARROW = "ijlIt.,:;'\"|!`()[]{}"      # ~0.28
_WIDE = "mwMW@%"                        # ~0.90
_UPPER = "ABCDEFGHKLNOPQRSTUVXYZ"       # ~0.68
_DIGIT = "0123456789"                   # tabular, uniform ~0.55

# Family multiplier: 1 = hand-drawn (looser), 2 = normal, 3 = code (monospace).
_FAMILY_K = {1: 1.08, 2: 1.0, 3: 1.15}


def _glyph_w(ch: str) -> float:
    if ch in _NARROW:
        return 0.28
    if ch in _WIDE:
        return 0.90
    if ch in _UPPER:
        return 0.68
    if ch in _DIGIT:
        return 0.55
    if ch == " ":
        return 0.26
    return 0.52                          # lowercase and everything else


def _text_w(s: str, size: int, family: int = 2) -> float:
    k = _FAMILY_K.get(family, 1.0)
    return sum(_glyph_w(c) for c in str(s)) * size * k


def _fit_line(s: str, max_w: float, size: int, family: int = 2) -> str:
    """Ellipsise a single line so it fits max_w pixels.

    Trims by measured width rather than a character count, so a wide string loses
    more characters than a narrow one — which is the whole point of measuring.
    """
    s = str(s)
    if max_w <= 0 or _text_w(s, size, family) <= max_w:
        return s
    ell_w = _text_w("…", size, family)
    budget = max_w - ell_w
    if budget <= 0:
        return "…"
    acc = 0.0
    out = []
    for ch in s:
        w = _glyph_w(ch) * size * _FAMILY_K.get(family, 1.0)
        if acc + w > budget:
            break
        acc += w
        out.append(ch)
    return ("".join(out).rstrip() or s[:1]) + "…"


def _wrap_lines(s: str, max_w: float, size: int, family: int = 2, max_lines: int = 3):
    """Word-wrap to at most max_lines, ellipsising the last if it still overflows."""
    words = str(s).split()
    if not words:
        return [""]
    lines, cur = [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if not cur or _text_w(cand, size, family) <= max_w:
            cur = cand
        else:
            lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines:
        consumed = len(" ".join(lines).split())
        if consumed < len(words):
            lines[-1] = _fit_line(lines[-1] + " …", max_w, size, family)
    return lines or [""]

# HTTP-method colors mapped to Excalidraw's default stroke swatches (green/blue/orange/red).
METHOD_COLOR = {"GET": "#2f9e44", "POST": "#1971c2", "PUT": "#f08c00", "PATCH": "#f08c00", "DELETE": "#e03131"}

# Floor for a screen frame. Small enough that a two-component screen does not sit
# in a sea of grey; the frame otherwise grows to fit whatever was drawn.
MIN_SCREEN_H = 120

# Nominal component heights. ADVISORY ONLY — the frame is sized from what
# _render_component actually draws, not from this table. Keeping a second set of
# numbers in sync with the renderer is what caused content to overflow its frame.
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

    def text(self, x, y, w, s, size=15, color=INK, align="left", family=2, h=None,
             fit=True, wrap=False, max_lines=3):
        """Emit a text element that actually fits the width it was given.

        fit=True (default) ellipsises each line to w. wrap=True word-wraps instead,
        for places with vertical room. Pass fit=False for pre-measured strings.
        """
        s = str(s)
        if wrap:
            s = "\n".join(_wrap_lines(s, w, size, family, max_lines))
        elif fit:
            s = "\n".join(_fit_line(ln, w, size, family) for ln in s.split("\n"))
        lines = s.count("\n") + 1
        e = _mk(self._id("t"), type="text", x=x, y=y, width=w,
                height=h if h is not None else int(size * 1.3 * lines),
                text=s, fontSize=size, fontFamily=family, strokeColor=color, textAlign=align)
        self.els.append(e)
        return e

    def dashed_link(self, card, endpoint, color="#adb5bd"):
        """Dashed anchor line (no arrowhead) from a contract card's right edge to the
        endpoint's left edge — signals annotation, not execution flow."""
        ax, ay = card["x"] + card["width"], card["y"] + 20
        bx, by = endpoint["x"], endpoint["y"] + endpoint["height"] / 2
        e = self._linear("line", card, endpoint, [[ax, ay], [bx, by]], color, 1.5, False)
        e["strokeStyle"] = "dashed"
        return e

    def _linear(self, kind, a, b, pts, color, sw, arrowhead):
        e = _mk(self._id("a" if kind == "arrow" else "ln"), type=kind,
                x=pts[0][0], y=pts[0][1],
                width=pts[-1][0] - pts[0][0], height=pts[-1][1] - pts[0][1],
                strokeColor=color, strokeWidth=sw,
                points=[[p[0] - pts[0][0], p[1] - pts[0][1]] for p in pts],
                startBinding={"elementId": a["id"], "focus": 0, "gap": 6},
                endBinding={"elementId": b["id"], "focus": 0, "gap": 6})
        a["boundElements"].append({"id": e["id"], "type": kind})
        b["boundElements"].append({"id": e["id"], "type": kind})
        self.els.append(e)
        return e

    def connect_direct(self, a, b, color=MUTED, dashed=False, offset_index=0):
        """Direct bezier arrow from a to b, with staggered anchor points."""
        ax = a["x"] + a["width"] / 2
        ay = a["y"] + a["height"]
        
        # Stagger the target X anchor to prevent "yarn ball" bundling
        bx = b["x"] + (b["width"] * 0.2) + (offset_index * 20)
        bx = min(bx, b["x"] + b["width"] * 0.8)
        by = b["y"]
        
        pts = [[ax, ay], [bx, by]]
        
        e = self._linear("arrow", a, b, pts, color, 3 if not dashed else 2, True)
        e["roundness"] = {"type": 3}   # Native Excalidraw Architectural Elbow Routing
        if dashed:
            e["strokeStyle"] = "dashed"
            e["endArrowhead"] = None
        return e

    def relate(self, a, b, lane=0):
        """Data-model relationship line."""
        ax, ay = a["x"] + a["width"], a["y"] + a["height"] / 2
        bx, by = b["x"] + b["width"], b["y"] + b["height"] / 2
        e = self._linear("line", a, b, [[ax, ay], [bx, by]], "#7048e8", 2, False)
        e["strokeStyle"] = "dashed"
        e["roundness"] = {"type": 2}
        return e


def _payload_lines(payload, max_lines=14, max_w=46):
    """Pretty-print a payload to a capped list of lines so a contract card can never
    eclipse the canvas. Long lines are ellipsised; overflow gets a '+N more' footer."""
    try:
        txt = payload if isinstance(payload, str) else json.dumps(payload, indent=2)
    except Exception:
        txt = str(payload)
    raw = txt.splitlines() or [str(txt)]
    out = []
    for ln in raw[:max_lines]:
        out.append(ln[:max_w] + ("…" if len(ln) > max_w else ""))
    if len(raw) > max_lines:
        out.append(f"… (+{len(raw) - max_lines} more lines)")
    return out


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
        sc.rect(cx, cy + 18, inner_w, fh, backgroundColor=SURFACE, strokeColor=FAINT, roundness={"type": 3})
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
        sc.rect(cx, cy, inner_w, 48, backgroundColor="transparent", strokeColor=FAINT, roundness={"type": 3})
        sc.text(cx + 14, cy + 16, inner_w - 24, label or "Navigation", size=14, color=INK)
        h = 48
    elif t in ("card", "avatar"):
        # A card used to be a fixed 80px box holding its label and a lone "—",
        # which read as an empty container with a void under the title. Wrap the
        # label into the space it has and size the box to the result, so a short
        # label gets a compact card and a long one is legible instead of clipped.
        card_index = len(sc.els)     # the box is inserted here, behind its contents
        body = cp.get("value") or cp.get("text") or ""
        title_lines = _wrap_lines(label or "Card", inner_w - 28, 13, max_lines=2)
        sc.text(cx + 14, cy + 12, inner_w - 28, "\n".join(title_lines),
                size=13, color=MUTED, fit=False)
        used = 12 + len(title_lines) * 17

        if body:
            body_lines = _wrap_lines(str(body), inner_w - 28, 14, max_lines=3)
            sc.text(cx + 14, cy + used + 4, inner_w - 28, "\n".join(body_lines),
                    size=14, color=INK, fit=False)
            used += 4 + len(body_lines) * 18
        else:
            # No value supplied: a short placeholder rule reads as "content goes
            # here" without pretending to be data, and without a tall empty void.
            sc.rect(cx + 14, cy + used + 10, min(120, inner_w - 28), 2,
                    backgroundColor=FAINT, strokeColor=FAINT)
            used += 20

        h = used + 14
        sc.els.insert(card_index, _mk(
            sc._id("r"), type="rectangle", x=cx, y=cy, width=inner_w, height=h,
            backgroundColor="transparent", strokeColor=FAINT, roundness={"type": 3}))
    elif t == "image":
        sc.rect(cx, cy, inner_w, 110, backgroundColor=SURFACE, strokeColor=FAINT, fillStyle="hachure", roundness={"type": 3})
        sc.text(cx + inner_w / 2 - 30, cy + 48, 80, label or "image", size=12, color=MUTED, align="center")
        h = 110
    elif t in ("list", "table"):
        rows = 4
        sc.rect(cx, cy, inner_w, 30 + rows * 26, backgroundColor="transparent", strokeColor=FAINT, roundness={"type": 3})
        sc.rect(cx, cy, inner_w, 30, backgroundColor=SURFACE, strokeColor=FAINT)
        sc.text(cx + 12, cy + 8, inner_w - 20, label or ("Table" if t == "table" else "List"), size=12, color=INK)
        for i in range(rows):
            sc.text(cx + 12, cy + 40 + i * 26, inner_w - 24, "· ————————", size=12, color=FAINT)
        h = 30 + rows * 26
    elif t in ("checkbox", "radio"):
        sc.rect(cx, cy, 18, 18, strokeColor=INK, backgroundColor="transparent",
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


def spec_to_excalidraw(spec: dict, detail: str = "") -> dict:
    sc = Scene()
    screens = spec.get("screens", []) or []
    backend = spec.get("backend") or {}
    endpoints = backend.get("endpoints", []) or []
    entities = backend.get("entities", []) or []

    # Progressive detail — reveal complexity on demand so the default view stays uncluttered:
    #   0 overview  = screens + endpoints + flows only
    #   1 data      = + data models, endpoint->model access, relationships
    #   2 contracts = + external integrations + JSON payload cards (the full picture)
    level = {"": 0, "overview": 0, "data": 1, "contracts": 2, "full": 2}.get(str(detail).lower(), 0)

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
        sc.text(sx, fz_y + 46, SCREEN_W, screen.get("name", f"Screen {si+1}"), size=17, color=INK)

        # MEASURE BY RENDERING, then fit the frame to what was actually drawn.
        #
        # The frame used to be sized from the COMP_H table while the components
        # were drawn at whatever height _render_component returned, and the two
        # disagreed: input 58 vs 62, list 130 vs 134, avatar 60 vs 80 (content
        # spilled out of the frame and collided with what came after), while
        # table 150 vs 134 and image 120 vs 110 left dead space. A fixed
        # `max(..., 220)` floor added more emptiness on short screens.
        #
        # Rendering first and inserting the frame behind afterwards leaves ONE
        # source of truth for a component's height — the code that draws it.
        frame_top = fz_y + 76
        frame_index = len(sc.els)          # frame goes here, behind the body
        cy = frame_top + PAD
        for cp in comps:
            used, btn = _render_component(sc, cp, sx + PAD, cy, inner_w)
            if btn is not None:
                lbl = str(cp.get("label", "")).strip().lower()
                button_els[lbl] = btn
                button_order[lbl] = sx + SCREEN_W / 2
            cy += used + GAP
        # cy overshot by one GAP after the final component; reclaim it.
        content_bottom = cy - GAP if comps else frame_top + PAD
        frame_h = max(content_bottom + PAD - frame_top, MIN_SCREEN_H)

        sc.els.insert(frame_index, _mk(
            sc._id("r"), type="rectangle", x=sx, y=frame_top,
            width=SCREEN_W, height=frame_h,
            backgroundColor=UI_FRAME, strokeColor=INK, strokeWidth=2,
            roundness={"type": 3}))
        screen_bottoms.append(frame_top + frame_h)

    fz_h = (max(screen_bottoms) if screen_bottoms else fz_y + 300) - fz_y + 30
    # faint frontend-layer band behind the screens (inserted after title so it's in back)
    sc.els.insert(1, _mk("zone-frontend", type="rectangle", x=fz_x, y=fz_y, width=fz_w, height=fz_h,
                         backgroundColor=FZONE_BG, strokeColor="#dee2e6", roundness={"type": 3}))
    sc.els.insert(2, _mk("lbl-frontend", type="text", x=fz_x + 18, y=fz_y + 14, width=400, height=18,
                         text="FRONTEND · UI SCREENS", fontSize=12, strokeColor=MUTED))

    # ── BACKEND ZONE (TOP-TO-BOTTOM DAG) ────────────────────────────────────
    endpoint_els = {}
    endpoint_color = {}              # id(endpoint card) -> its HTTP-method color
    entity_els = {}
    if endpoints or entities:
        bz_y = fz_y + fz_h + ZONE_GAP

        # Order endpoints by the x-position of the UI button that calls them
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

        ep_w = 320
        col_y = {}  # Tracks the next available Y for each X-column
        max_ep_bottom = bz_y + 60
        
        # ROW 2: API Endpoints (Vertical Stacks per feature)
        for ep in endpoints:
            method = str(ep.get("method", "GET")).upper()
            path = ep.get("path", "/")
            desc = ep.get("desc", "")
            
            # Align directly beneath the UI button that calls it
            raw_x = to_srcx.get(str(path).strip().lower(), 
                               to_srcx.get(f"{method} {path}".lower(), fz_x + 40))
            ep_x = _snap(raw_x - ep_w / 2)
            
            ep_y = col_y.get(ep_x, bz_y + 60)
            
            col = METHOD_COLOR.get(method, MUTED)
            card = sc.rect(ep_x, ep_y, ep_w, 60, backgroundColor="transparent", strokeColor=col, strokeWidth=2, roundness={"type": 3})
            sc.rect(ep_x, ep_y, 58, 60, backgroundColor=col, strokeColor=col)
            sc.text(ep_x, ep_y + 22, 58, method[:4], size=11, color=WHITE, align="center")
            sc.text(ep_x + 70, ep_y + 12, ep_w - 80, path, size=14, color=INK)
            if desc:
                sc.text(ep_x + 70, ep_y + 34, ep_w - 80, desc, size=11, color=MUTED)
            endpoint_els[f"{method} {path}".lower()] = card
            endpoint_els[path.lower()] = card
            endpoint_color[id(card)] = col

            card_bottom = ep_y + 60

            # Attach JSON Contract directly underneath if it exists
            if str(detail).lower() == "contracts":
                payload = ep.get("payload")
                if payload:
                    lines = _payload_lines(payload)
                    cw = 320
                    ch = 34 + len(lines) * 18 + 16
                    cc_y = ep_y + 80
                    pcard = sc.rect(ep_x, cc_y, cw, ch, backgroundColor="#1e1e1e", strokeColor="#1e1e1e", roundness={"type": 3})
                    sc.rect(ep_x, cc_y, cw, 28, backgroundColor="#2d2d2d", strokeColor="#2d2d2d")
                    sc.text(ep_x + 12, cc_y + 7, cw - 70, f"{method} {path}", size=11, color="#9cdcfe")
                    sc.rect(ep_x + cw - 52, cc_y + 5, 42, 18, backgroundColor="#0ca678", strokeColor="#0ca678", roundness={"type": 3})
                    sc.text(ep_x + cw - 48, cc_y + 7, 42, "JSON", size=9, color="#ffffff")
                    sc.text(ep_x + 14, cc_y + 38, cw - 24, "\n".join(lines), size=12, color="#d4d4d4", family=3, h=len(lines) * 18)
                    sc.dashed_link(pcard, card)
                    card_bottom = cc_y + ch

            # Increment the column's Y position so the next endpoint in this column stacks below
            col_y[ep_x] = card_bottom + 40
            max_ep_bottom = max(max_ep_bottom, card_bottom)

        # ROW 4: Data Models & Integrations (Vertical Stacks per feature)
        max_ent_bottom = max_ep_bottom + 120
        ent_col_y = {}
        if level >= 1:
            for ent in entities:
                name = ent.get("name", "Entity")
                fields = ent.get("fields", []) or []
                ew = 260
                
                # Align directly beneath the first endpoint that uses it
                raw_x = fz_x + 40
                for ep in endpoints:
                    if name in (ep.get("reads", []) or []) or name in (ep.get("writes", []) or []):
                        ep_card = endpoint_els.get(f"{str(ep.get('method', 'GET')).upper()} {ep.get('path', '/')}".lower())
                        if ep_card:
                            raw_x = ep_card["x"] + ep_card["width"] / 2
                            break
                ent_x = _snap(raw_x - ew / 2)
                ent_y = ent_col_y.get(ent_x, max_ep_bottom + 120)

                eh = 42 + len(fields) * 24 + 12
                ent_card = sc.rect(ent_x, ent_y, ew, eh, backgroundColor=ENTITY_FILL, strokeColor="#7048e8", strokeWidth=2, roundness={"type": 3})
                sc.rect(ent_x, ent_y, ew, 36, backgroundColor=ENTITY_HDR, strokeColor="#7048e8")
                sc.text(ent_x + 12, ent_y + 9, ew - 20, name, size=14, color=INK)
                fy = ent_y + 48
                for f in fields:
                    sc.text(ent_x + 12, fy, ew - 20, str(f), size=12, color="#495057")
                    fy += 24
                entity_els[name.lower()] = ent_card
                
                ent_col_y[ent_x] = ent_y + eh + 40
                max_ent_bottom = max(max_ent_bottom, ent_y + eh)

        # External Integrations
        integrations = backend.get("integrations", []) or [] if level >= 2 else []
        integ_els = {}
        if integrations:
            iw, ih = 240, 78
            for ig in integrations:
                name = ig.get("name", "Service")
                kind = ig.get("kind", "")
                
                # Align beneath the endpoint that uses it
                raw_x = fz_x + 40
                for ep_path in (ig.get("via", []) or []):
                    eb = endpoint_els.get(str(ep_path).strip().lower())
                    if eb is not None:
                        raw_x = eb["x"] + eb["width"] / 2
                        break
                ix = _snap(raw_x - iw / 2)
                iy = ent_col_y.get(ix, max_ep_bottom + 120)

                card = sc.rect(ix, iy, iw, ih, backgroundColor="#e6fcf5", strokeColor="#0ca678", strokeWidth=2, roundness={"type": 3})
                sc.rect(ix, iy, iw, 34, backgroundColor="#c3fae8", strokeColor="#0ca678")
                sc.text(ix + 14, iy + 9, iw - 24, name, size=14, color=INK)
                if kind:
                    sc.text(ix + 14, iy + 46, iw - 24, kind, size=11, color="#0b7285")
                integ_els[name.lower()] = card
                
                ent_col_y[ix] = iy + ih + 40
                max_ent_bottom = max(max_ent_bottom, iy + ih)

        # Background Zone Block
        all_xs = list(col_y.keys()) + list(ent_col_y.keys())
        max_x = max(all_xs) if all_xs else fz_x
        bz_w = max(max_x - fz_x + 400, fz_w)
        bz_h = max_ent_bottom - bz_y + 60

        sc.els.insert(1, _mk("zone-backend", type="rectangle", x=fz_x, y=bz_y, width=bz_w, height=bz_h,
                             backgroundColor="#b197fc", strokeColor="#e5dbff", opacity=18, roundness={"type": 3}))
        sc.els.insert(2, _mk("lbl-backend", type="text", x=fz_x + 18, y=bz_y + 16, width=400, height=18,
                             text="BACKEND · API, DATA & INTEGRATIONS", fontSize=12, strokeColor=MUTED))

        # Connections (Staggered Anchors)
        inbound_counts = {}
        
        for flow in flows:
            a = button_els.get(str(flow.get("from", "")).strip().lower())
            b = endpoint_els.get(str(flow.get("to", "")).strip().lower())
            if a is not None and b is not None:
                idx = inbound_counts.get(id(b), 0)
                sc.connect_direct(a, b, color=endpoint_color.get(id(b), PRIMARY), offset_index=idx)
                inbound_counts[id(b)] = idx + 1
                
        # Cross-column lines omitted for clarity
        # Data-model relationships
        drawn = set()
        k = 0
        for ent in (entities if level >= 1 else []):
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

    return {
        "type": "excalidraw", "version": 2, "source": "kenbun-ai-wireframe",
        "elements": sc.els,
        # transparent canvas so the board's light/dark theme shows through (matches Excalidraw preference)
        # name drives the Excalidraw doc title so it reflects the product, never "Kenbun"
        "appState": {"viewBackgroundColor": "transparent", "gridSize": None,
                     "name": str(spec.get("title", "Wireframe"))},
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
    "Backend (think like a backend dev): the data models the feature needs (typed fields), the REST "
    "endpoints powering UI actions, and flows connecting each primary button to the endpoint path it "
    "calls (use the EXACT button label in flow.from and the EXACT endpoint path in flow.to). Make "
    "endpoint reads/writes reference entity names. 1-4 screens. Keep labels short."
)


def generate_spec(prompt: str, detail: str = "") -> dict:
    from tools.utils.llm_router import call_llm_gateway
    sysprompt = WIREFRAME_SYSTEM_PROMPT
    if str(detail).lower() == "contracts":
        sysprompt += ("\nCONTRACTS MODE: you MUST include a concise `payload` JSON object for EVERY "
                      "webhook, every integration-facing endpoint, and every POST/PUT/PATCH that "
                      "accepts a body. Do not omit payloads.")
    for attempt in range(3):
        raw = call_llm_gateway(sysprompt, f"Feature request: {prompt}", max_tokens=8192)
        txt = re.sub(r"^```(json)?", "", raw.strip()).strip()
        txt = re.sub(r"```$", "", txt).strip()
        m = re.search(r"\{.*\}", txt, re.DOTALL)
        if not m:
            continue
        try:
            return json.loads(m.group(0))
        except Exception:
            continue
    raise ValueError(f"LLM failed to return valid JSON spec after 3 attempts. Last output: {raw[:200]}")


def build_wireframe(prompt: str, detail: str = ""):
    spec = generate_spec(prompt, detail=detail)
    scene = spec_to_excalidraw(spec, detail=detail)
    return scene, spec
