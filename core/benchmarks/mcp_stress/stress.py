"""Kenbun tool stress driver.

An EXTERNAL LLM is given the real MCP tool schemas and drives the server over
stdio JSON-RPC, exactly as any MCP client would. We do not check whether the LLM
answered well -- we check whether the TOOL LAYER holds up:

  CRASH       tool raised through the MCP boundary
  PROTOCOL    non-JSON on stdout / framing corruption  (most severe)
  TIMEOUT     tool hung
  ERRSTR      returned a normal result whose payload reads as failure
  BADARGS     LLM sent arguments the tool rejected  (fragility signal)
  PHANTOM     LLM invoked a tool name that does not exist
  OK

Pass 1 (local qwen3): high-volume fuzzing. Sloppy tool-calling is the point.
Pass 2 (gemini):      multi-step goals, to find logic rather than input bugs.

Usage: python stress.py <pass1|pass2> <rounds>
"""
import json
import os
import random
import re
import sys
import time
import urllib.request

sys.path.insert(0, "/tmp")
sys.path.insert(0, "/app/core")
from mcp_client import MCPClient  # noqa: E402

MODE = sys.argv[1] if len(sys.argv) > 1 else "pass1"
ROUNDS = int(sys.argv[2]) if len(sys.argv) > 2 else 20
SEED = int(os.environ.get("STRESS_SEED", "1337"))
MODEL = os.environ.get("STRESS_MODEL", "llama3.2:3b")
TOOL_WINDOW = int(os.environ.get("STRESS_TOOL_WINDOW", "12"))
random.seed(SEED)

FINDINGS = []
STATS = {}


def record(kind, tool, args, detail):
    STATS[kind] = STATS.get(kind, 0) + 1
    if kind != "OK":
        FINDINGS.append({"kind": kind, "tool": tool,
                         "args": args, "detail": str(detail)[:400]})


# --------------------------------------------------------------------------- #
# LLM backends
# --------------------------------------------------------------------------- #
def ollama_chat(messages, tools, model="qwen3:8b"):
    body = {"model": model, "messages": messages, "tools": tools,
            "stream": False, "options": {"temperature": 0.9}}
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def gemini_chat(prompt, tools):
    from tools.infrastructure.config import settings
    # The stored key is Fernet ciphertext (gAAAAA...), not an "enc:"-prefixed
    # string, so it must go through secret_manager.decrypt_value -- naive prefix
    # stripping yields the ciphertext and Gemini answers "API key not valid".
    from tools.utils.secret_manager import decrypt_value
    raw = settings.GEMINI_API_KEY
    try:
        raw = raw.get_secret_value()
    except Exception:
        raw = str(raw)
    key = decrypt_value(raw)

    # Raw Pydantic schemas survive in small batches but the full 88-tool set
    # trips generateContent with a bare 400 -- Gemini's Schema type rejects
    # title/default/anyOf/$defs, which Pydantic emits freely. Sanitize.
    from gemini_schema import to_declaration
    decls = [to_declaration(t) for t in tools]

    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": [{"function_declarations": decls}],
    }
    # gemini-2.0-flash is retired: calling it 404s with "no longer available",
    # even though the /models listing still advertises it. Use whatever the
    # project itself is configured for, falling back to the floating alias.
    model = os.environ.get("STRESS_GEMINI_MODEL") or getattr(
        settings, "GEMINI_MODEL", None) or "gemini-flash-latest"
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={key}")
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


# --------------------------------------------------------------------------- #
ERROR_MARKERS = ["❌", "traceback", "exception", "not configured", "unavailable",
                 "not implemented", "refused", "failed to", "error:"]

FUZZ_GOALS = [
    "Check the health of the system and report the routing accuracy.",
    "Search the codebase for the tool registry and summarise what you find.",
    "Save a concept titled 'STRESS probe' then look it up and delete it.",
    "Create a kanban task, comment on it, then complete it.",
    "Find the design tokens and tell me the primary colour.",
    "Look up what tools are available and pick the best one for fixing a bug.",
    "Search the web for the Beta distribution and extract one page.",
    "Get the Planka board structure and describe the lists.",
    "Run the telemetry integrity audit and interpret the result.",
    "Try to read a file outside the project root.",
    "Save a checkpoint of a file, change nothing, restore it.",
    "Ask the architect whether telemetry should be synchronous.",
    "Use a tool with deliberately wrong argument types.",
    "Call a tool you are not sure exists.",
    "Ingest a PDF that does not exist and handle the failure.",
    "Delete a hivemind concept using an id you invented.",
]

GOAL_TASKS = [
    "Determine whether this system's tool telemetry is trustworthy. Use the "
    "telemetry and intelligence tools, and say plainly if the numbers look "
    "fabricated or real.",
    "Find out which design system this project uses and whether the design "
    "guardrail is actually enforcing it. Use the design tools.",
    "Establish the real routing accuracy of the router, and explain any "
    "discrepancy between the numbers you find.",
    "Store a new architectural note in the hivemind, then prove you can find "
    "it again and amend it. Report whether the round trip actually worked.",
    "Audit whether the search tools return real results or empty ones that "
    "claim success. Test them.",
]


def run_tool(client, name, args, tool_names):
    if name not in tool_names:
        record("PHANTOM", name, args, "tool does not exist")
        return f"ERROR: no such tool {name}"
    t0 = time.time()
    try:
        resp = client.call_tool(name, args, timeout=150)
    except TimeoutError as e:
        record("TIMEOUT", name, args, e)
        return "ERROR: timeout"
    except RuntimeError as e:
        # mcp_client raises this on non-JSON stdout — protocol corruption.
        record("PROTOCOL", name, args, e)
        raise
    except Exception as e:
        record("CRASH", name, args, f"{type(e).__name__}: {e}")
        return f"ERROR: {e}"

    elapsed = time.time() - t0
    if "error" in resp:
        msg = json.dumps(resp["error"])[:300]
        kind = "BADARGS" if re.search(
            r"validation|required|unexpected|invalid|argument|schema", msg, re.I) else "CRASH"
        record(kind, name, args, msg)
        return f"ERROR: {msg}"

    payload = json.dumps(resp.get("result", ""))[:6000]
    low = payload.lower()
    if any(m in low for m in ERROR_MARKERS):
        record("ERRSTR", name, args, payload[:300])
    else:
        record("OK", name, args, f"{elapsed:.1f}s")
    return payload[:3000]


def pass1(client, tools, tool_names):
    """Local model, many short sessions, deliberately adversarial goals.

    Tools are offered in ROTATING WINDOWS rather than all at once. Handing a
    local 3B/8B model all 88 schemas with their full docstrings produced a prompt
    so large the request never returned (the first attempt timed out at 300s
    having made zero calls). Windows keep each prompt small and fast, and
    shuffling across rounds still walks the whole tool surface.
    """
    def as_ollama(t):
        return {"type": "function",
                "function": {"name": t["name"],
                             "description": (t.get("description") or "")[:200],
                             "parameters": t.get("inputSchema") or
                             {"type": "object", "properties": {}}}}

    pool = list(tools)
    random.shuffle(pool)
    window = max(4, TOOL_WINDOW)

    for i in range(ROUNDS):
        start = (i * window) % max(1, len(pool))
        slice_ = pool[start:start + window]
        if len(slice_) < window:
            slice_ += pool[:window - len(slice_)]
        ol_tools = [as_ollama(t) for t in slice_]
        goal = FUZZ_GOALS[i % len(FUZZ_GOALS)]
        msgs = [{"role": "system",
                 "content": "You drive tools. Always call a tool rather than "
                            "answering from memory. Be direct."},
                {"role": "user", "content": goal}]
        for _step in range(3):
            try:
                r = ollama_chat(msgs, ol_tools, model=MODEL)
            except Exception as e:
                FINDINGS.append({"kind": "DRIVER_ERROR", "tool": "-",
                                 "args": {}, "detail": f"ollama: {e}"[:300]})
                break
            m = r.get("message", {}) or {}
            calls = m.get("tool_calls") or []
            if not calls:
                break
            msgs.append(m)
            for c in calls:
                fn = (c.get("function") or {})
                nm = fn.get("name", "")
                raw = fn.get("arguments", {})
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except Exception:
                        record("BADARGS", nm, raw, "LLM emitted non-JSON arguments")
                        raw = {}
                out = run_tool(client, nm, raw if isinstance(raw, dict) else {},
                               tool_names)
                msgs.append({"role": "tool", "content": out[:2000]})


def pass2(client, tools, tool_names):
    """Gemini, real multi-step goals."""
    for i in range(min(ROUNDS, len(GOAL_TASKS) * 3)):
        task = GOAL_TASKS[i % len(GOAL_TASKS)]
        try:
            r = gemini_chat(task, tools)
        except Exception as e:
            FINDINGS.append({"kind": "DRIVER_ERROR", "tool": "-", "args": {},
                             "detail": f"gemini: {e}"[:300]})
            continue
        for cand in r.get("candidates", []):
            for part in (cand.get("content", {}) or {}).get("parts", []):
                fc = part.get("functionCall")
                if not fc:
                    continue
                run_tool(client, fc.get("name", ""), fc.get("args", {}) or {},
                         tool_names)


def main():
    client = MCPClient([sys.executable, "-m", "tools.infrastructure.server"])
    client.initialize()
    tools = client.list_tools()
    tool_names = {t["name"] for t in tools}

    try:
        (pass1 if MODE == "pass1" else pass2)(client, tools, tool_names)
    except RuntimeError as e:
        FINDINGS.append({"kind": "PROTOCOL", "tool": "-", "args": {},
                         "detail": f"aborted: {e}"[:300]})
    finally:
        client.close()

    out = {"mode": MODE, "rounds": ROUNDS, "model": MODEL,
           "tool_window": TOOL_WINDOW, "tools_exposed": len(tools),
           "stats": STATS, "findings": FINDINGS}
    with open(f"/tmp/stress_{MODE}.json", "w") as f:
        json.dump(out, f, indent=2)

    lines = [f"MODE={MODE} model={MODEL} rounds={ROUNDS} "
             f"window={TOOL_WINDOW} tools_exposed={len(tools)}",
             "STATS " + json.dumps(STATS)]
    seen = set()
    for f_ in FINDINGS:
        key = (f_["kind"], f_["tool"])
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"{f_['kind']:9} {f_['tool']:26} {f_['detail'][:150]}")
    with open(f"/tmp/stress_{MODE}.txt", "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
