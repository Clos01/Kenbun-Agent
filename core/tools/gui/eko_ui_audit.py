"""Short UI-TARS usability audit. Runs ON p330 (needs DISPLAY=:0). Emits JSON."""
import io, os, sys, json, time, base64, subprocess
import requests
from PIL import ImageGrab

os.environ["DISPLAY"] = ":0"

BASE     = os.environ.get("EKO_BASE", "http://100.79.106.48:3000")
ENDPOINT = "http://127.0.0.1:8090/v1/chat/completions"
MODEL    = "/models/UI-TARS-2B-SFT-Q4_K_M.gguf"
OUT      = "/tmp/eko_audit"
RES      = (1120, 630)   # below this UI-TARS-2B cannot read UI text at all

PAGES = [
    ("Agent Fleet",      "/fleet-overview"),
    ("Voice Agents",     "/voice-agents"),
    ("Calls & Feedback", "/call-telemetry"),
    ("Settings",         "/settings"),
]

PROMPT = ("List every heading, button, link and form field you can read on this screen. "
          "Then say in one sentence what this screen is for.")


def look(img, path):
    img.save(path)                                   # full-res for the human/Claude
    small = img.resize(RES)
    buf = io.BytesIO()
    small.convert("RGB").save(buf, format="JPEG", quality=80)
    b64 = base64.b64encode(buf.getvalue()).decode()
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
        ]}],
        "temperature": 0.0, "max_tokens": 180,
    }
    t0 = time.time()
    r = requests.post(ENDPOINT, json=payload, timeout=300)
    r.raise_for_status()
    j = r.json()
    return {
        "observation": j["choices"][0]["message"]["content"].strip(),
        "latency_s": round(time.time() - t0, 1),
        "prompt_tokens": j.get("usage", {}).get("prompt_tokens"),
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    subprocess.run(["pkill", "-f", "firefox"], check=False)
    time.sleep(2)
    subprocess.Popen(["firefox", "--kiosk", BASE + PAGES[0][1]],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(15)

    steps = []
    for i, (name, route) in enumerate(PAGES):
        if i:
            subprocess.run(["firefox", "--new-tab", BASE + route], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(9)
        shot = f"{OUT}/{i+1}_{route.strip('/')}.png"
        print(f"[{i+1}/{len(PAGES)}] {name} ({route}) ...", flush=True)
        try:
            rec = look(ImageGrab.grab(), shot)
        except Exception as e:
            rec = {"observation": None, "error": str(e)}
        rec.update(page=name, route=route, screenshot=shot)
        print(f"    {rec['latency_s']}s :: {(rec['observation'] or rec.get('error'))[:150]}", flush=True)
        steps.append(rec)

    print("\n===AUDIT_JSON===")
    print(json.dumps(steps, indent=2))


if __name__ == "__main__":
    main()
