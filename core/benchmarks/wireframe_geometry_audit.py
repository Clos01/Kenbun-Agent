"""Geometry audit of a generated Excalidraw scene: does anything clash?"""
import json
import sys

scene = json.load(open(sys.argv[1]))
els = scene.get("elements", [])

CW = {"narrow": 0.28, "wide": 0.90, "upper": 0.68, "digit": 0.55, "space": 0.26}
NARROW = "ijlIt.,:;'\"|!`()[]{}"
WIDE = "mwMW@%"
UPPER = "ABCDEFGHKLNOPQRSTUVXYZ"
FAMILY_K = {1: 1.08, 2: 1.0, 3: 1.15}


def gw(c):
    if c in NARROW: return 0.28
    if c in WIDE: return 0.90
    if c in UPPER: return 0.68
    if c.isdigit(): return 0.55
    if c == " ": return 0.26
    return 0.52


def tw(s, size, fam=2):
    return sum(gw(c) for c in s) * size * FAMILY_K.get(fam, 1.0)


texts = [e for e in els if e.get("type") == "text"]
rects = [e for e in els if e.get("type") == "rectangle"]

# 1. text overflow
over = []
for e in texts:
    for line in str(e.get("text", "")).split("\n"):
        w = tw(line, e.get("fontSize", 16), e.get("fontFamily", 2))
        if w > e.get("width", 0) + 1.5:
            over.append((line[:36], round(w), e.get("width")))

# 2. big UI frames (the grey screen containers) must contain their content
frames = [r for r in rects if r.get("width") == 350 and r.get("height", 0) > 100]
escaped = []
for f in frames:
    fx, fy, fw, fh = f["x"], f["y"], f["width"], f["height"]
    for e in els:
        if e is f or e.get("type") in ("line", "arrow"):
            continue
        ex, ey = e.get("x", 0), e.get("y", 0)
        ew, eh = e.get("width", 0), e.get("height", 0)
        # only consider elements that START inside this frame horizontally+vertically
        if fx <= ex < fx + fw and fy <= ey < fy + fh:
            if ey + eh > fy + fh + 2:
                escaped.append((e.get("type"), str(e.get("text", ""))[:26],
                                round(ey + eh), round(fy + fh)))

# 3. dead space: how much of each frame is below its lowest content?
dead = []
for f in frames:
    fx, fy, fw, fh = f["x"], f["y"], f["width"], f["height"]
    # Exclude connectors: an arrow from a button down to its endpoint is SUPPOSED
    # to leave the frame, and counting it made dead space come out negative.
    bottoms = [e.get("y", 0) + e.get("height", 0) for e in els
               if e is not f and e.get("type") not in ("line", "arrow")
               and fx <= e.get("x", 0) < fx + fw
               and fy <= e.get("y", 0) < fy + fh]
    if bottoms:
        dead.append(round(fy + fh - max(bottoms)))

print("=== GEOMETRY AUDIT ===")
print(f"elements={len(els)} texts={len(texts)} screen-frames={len(frames)}")
print(f"text overflowing its width : {len(over)}")
for o in over[:4]:
    print("   OVERFLOW", o)
print(f"content escaping its frame : {len(escaped)}")
for e in escaped[:4]:
    print("   ESCAPED", e)
print(f"dead space below content, per frame (px): {dead}")
print("VERDICT:", "CLEAN" if not over and not escaped and all(d <= 60 for d in dead)
      else "ISSUES REMAIN")
