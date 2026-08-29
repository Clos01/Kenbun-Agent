"""
UI-TARS functional test for Eko Veritas. Runs ON p330 (needs DISPLAY=:0).

Each UI-TARS look costs ~40s and is prompt/vision-bound, not generation-bound
(measured: 183 prompt tok -> 7.1s, 959 prompt tok -> 41.8s, output length
barely moves it). So the polling loop is pure local pixel math, and the model
is called exactly once per page -- for the verdict a human would give.

Asserts two things per page:
  1. time-to-content  -- deterministic, from dark-pixel ratio in the content area
  2. DATA vs SKELETON -- UI-TARS, forced to a one-word answer

The second exists because the earlier at-rest audit had UI-TARS confidently
describe skeleton bars as "a list of items with checkboxes". A closed question
it can actually answer is worth more than a paragraph it invents.
"""
import io, os, sys, json, time, base64, subprocess
import requests
from PIL import ImageGrab

os.environ["DISPLAY"] = ":0"

BASE     = os.environ.get("EKO_BASE", "http://100.79.106.48:3001")
ENDPOINT = "http://127.0.0.1:8090/v1/chat/completions"
MODEL    = "/models/UI-TARS-2B-SFT-Q4_K_M.gguf"
OUT      = "/tmp/eko_test"
RES      = (1120, 630)          # below this UI-TARS-2B cannot read UI text
SIDEBAR_PX = 200                # left nav renders instantly; exclude it
TIMEOUT_S  = 30.0
DARK_RATIO_CONTENT = 0.002       # calibrated on known frames: skeleton 0.00000, real content 0.00745

PAGES = [
    ("Agent Fleet",      "/fleet-overview"),
    ("Voice Agents",     "/voice-agents"),
    ("Calls & Feedback", "/call-telemetry"),
    ("Settings",         "/settings"),
]

VERDICT_PROMPT = (
    "Look only at the large content area to the right of the left sidebar.\n"
    "If it shows real readable text, numbers or labels, answer DATA.\n"
    "If it shows only blank grey rounded placeholder bars with no readable text, "
    "answer SKELETON.\n"
    "Answer with exactly one word: DATA or SKELETON."
)


def dark_ratio(img):
    """Fraction of near-black pixels in the content area. Text is dark; skeleton bars are not."""
    content = img.crop((SIDEBAR_PX, 0, img.width, img.height)).convert("L").resize((800, 450))
    px = content.getdata()
    return sum(1 for p in px if p < 160) / float(len(px))


def ask_verdict(img):
    small = img.resize(RES)
    buf = io.BytesIO()
    small.convert("RGB").save(buf, format="JPEG", quality=80)
    b64 = base64.b64encode(buf.getvalue()).decode()
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": VERDICT_PROMPT},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
        ]}],
        "temperature": 0.0, "max_tokens": 8,
    }
    t0 = time.time()
    r = requests.post(ENDPOINT, json=payload, timeout=300)
    r.raise_for_status()
    raw = r.json()["choices"][0]["message"]["content"].strip()
    up = raw.upper()
    verdict = "DATA" if "DATA" in up else ("SKELETON" if "SKELETON" in up else "UNCLEAR")
    return verdict, raw, round(time.time() - t0, 1)


def run_page(idx, name, route):
    """
    One fresh firefox per page. `firefox --new-tab <url>` against a running
    instance does not raise or repaint the visible window here: three
    consecutive pages produced byte-identical dark frames (mean luminance 44.1),
    and an earlier --kiosk run had UI-TARS confidently answer SKELETON to one of
    them. Relaunching costs ~14s a page and is the only navigation that was
    reproducibly observed to actually change the screen.

    Because cold start dominates, this does NOT time the app. Server-side
    numbers (TTFB / full render) are the honest latency measurement; this
    asserts only what a human would see once the page has settled.
    """
    url = BASE + route
    subprocess.run(["pkill", "-f", "firefox"], check=False)
    time.sleep(3)
    subprocess.Popen(["firefox", "--new-window", url],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    time.sleep(14)   # firefox cold start, not the app's latency

    time_to_content, samples = None, []
    while time.time() - t0 < TIMEOUT_S:
        img = ImageGrab.grab()
        dr = dark_ratio(img)
        samples.append({"t": round(time.time() - t0, 1), "dark_ratio": round(dr, 5)})
        if dr >= DARK_RATIO_CONTENT and dr < 0.9:
            time_to_content = round(time.time() - t0, 1)
            break
        time.sleep(0.5)

    final = ImageGrab.grab()
    shot = "%s/%d_%s.png" % (OUT, idx, route.strip("/"))
    final.save(shot)
    verdict, raw, lat = ask_verdict(final)

    fdr = dark_ratio(final)
    if fdr > 0.9:
        # Screen blanked / screensaver: the frame is not the app at all.
        return {"page": name, "route": route, "result": "INVALID",
                "error": "screen blank (dark_ratio=%.3f) -- not an app frame" % fdr,
                "screenshot": shot}
    # The pixel check is the assertion; UI-TARS is recorded alongside it.
    # On a verified-good frame (fleet-overview, full of real numbers and a
    # populated table) UI-TARS answered SKELETON, so its verdict is a secondary
    # signal, not the gate. Disagreement is surfaced rather than averaged away.
    passed = time_to_content is not None
    return {
        "page": name, "route": route,
        "time_to_content_s": time_to_content,
        "timed_out": time_to_content is None,
        "tars_verdict": verdict, "tars_raw": raw, "tars_latency_s": lat,
        "tars_agrees": (verdict == "DATA") == passed,
        "final_dark_ratio": round(fdr, 5),
        "screenshot": shot,
        "result": "PASS" if passed else "FAIL",
        "samples": samples,
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    for a in (["xset", "s", "off"], ["xset", "-dpms"], ["xset", "s", "noblank"]):
        subprocess.run(a, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("target: %s\n" % BASE, flush=True)
    results = []
    for i, (name, route) in enumerate(PAGES):
        print("[%d/%d] %s %s" % (i + 1, len(PAGES), name, route), flush=True)
        try:
            rec = run_page(i + 1, name, route)
        except Exception as e:
            rec = {"page": name, "route": route, "result": "ERROR", "error": str(e)}
        ttc = rec.get("time_to_content_s")
        print("    %-7s content=%-6s ui-tars=%-8s agree=%s" % (
            rec["result"],
            "no" if ttc is None else "yes",
            rec.get("tars_verdict"), rec.get("tars_agrees")), flush=True)
        results.append(rec)

    npass = sum(1 for r in results if r["result"] == "PASS")
    print("\n%d/%d pages PASS" % (npass, len(results)), flush=True)
    print("\n===TEST_JSON===")
    print(json.dumps(results, indent=2))
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
