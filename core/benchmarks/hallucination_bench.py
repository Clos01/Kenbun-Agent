"""
🕵️ Nano-Model Hallucination Regression Benchmark

Measures whether the active local model emits clean native tool calls or
hallucinates — invented `kenbun <tool>` shell syntax, XML/pseudo-tool markup
in content, malformed argument JSON, or made-up tool names. These are exactly
the failure modes the recent fix(ai) prompt commits patched; this benchmark
makes those tweaks measurable and gates default-model swaps.

Design (supervisor-approved via orchestrate research_implement pipeline):
- The scorer is PURE — unit-testable without a live model
  (core/tests/test_hallucination_bench.py).
- The runner uses the real production prompt (build_system_prompt) and the
  CLI's real tool schema, through call_llm_gateway, so the nano decoupled
  planner-executor path is measured end-to-end.
- Skips gracefully (exit 0) when the local gateway is unreachable, so it is
  safe in CI.

Run:  uv run python -m core.benchmarks.hallucination_bench
"""
import json
import re
import sys
import time

PROMPT_SET_VERSION = "1.0"

# The CLI's native tool schema (mirrors core/tools/cli/engine.py cli_tools)
VALID_TOOLS = {
    "execute_shell": {"command"},
    "spawn_agent": {"task_description"},
}

CLI_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "execute_shell",
            "description": "Execute a terminal bash command. Proposed code must be run on the host system to have an effect.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spawn_agent",
            "description": "Spawn a background AI agent to handle a sub-task autonomously.",
            "parameters": {
                "type": "object",
                "properties": {"task_description": {"type": "string"}},
                "required": ["task_description"],
            },
        },
    },
]

# Pseudo-tool / XML markup that must never leak into assistant content
XML_LEAK_PATTERNS = [
    r"<tool_call\b",
    r"</?function(?:_call)?\b",
    r"<invoke\b",
    r"<execute\b",
    r"<tool\b",
    r"\[TOOL_CALL\]",
    r"\[FUNCTION_CALL\]",
]

# `kenbun <something>` proposed as a shell command — the recursive-subprocess
# hallucination the system prompt explicitly bans.
KENBUN_WRAP_RE = re.compile(r"(?:^|[;&|]\s*|`\s*|\$\(\s*)kenbun\s+[a-z_][\w-]*", re.IGNORECASE | re.MULTILINE)

FENCED_BLOCK_RE = re.compile(r"```(?:\w+)?\n(.*?)```", re.DOTALL)


# ============================================================
# PROMPT SET — 4 categories (orchestrate + supervisor design)
# ============================================================
CASES = [
    # 1. Few-shot alignment: simple single-tool tasks the nano prompt trains on
    {"id": "fs-list-files", "category": "few_shot_alignment",
     "prompt": "List the files in the current directory.", "expect_tool": "execute_shell"},
    {"id": "fs-disk-space", "category": "few_shot_alignment",
     "prompt": "How much disk space is free on this machine?", "expect_tool": "execute_shell"},
    {"id": "fs-git-status", "category": "few_shot_alignment",
     "prompt": "Show me the git status of this repo.", "expect_tool": "execute_shell"},
    # 2. Tool synthesis: multi-step tasks that tempt `kenbun <tool>` wrapping
    {"id": "ts-recall-memory", "category": "tool_synthesis",
     "prompt": "Search your hivemind memory for past docker networking fixes and summarize what you find.",
     "expect_tool": None},
    {"id": "ts-background-index", "category": "tool_synthesis",
     "prompt": "Index this codebase in the background while we keep talking.", "expect_tool": "spawn_agent"},
    {"id": "ts-scan-then-fix", "category": "tool_synthesis",
     "prompt": "Scan the repository structure, then propose a command to count Python files.",
     "expect_tool": "execute_shell"},
    # 3. Schema strictness: nested/quoted content that tempts malformed JSON
    {"id": "ss-nested-quotes", "category": "schema_strictness",
     "prompt": 'Create a file named notes.txt containing the text: He said "hello" and left.',
     "expect_tool": "execute_shell"},
    {"id": "ss-multiline", "category": "schema_strictness",
     "prompt": "Write a two-line bash script to /tmp/hi.sh: first line shebang, second line echo hi.",
     "expect_tool": "execute_shell"},
    {"id": "ss-json-payload", "category": "schema_strictness",
     "prompt": "Use curl to POST the JSON {\"name\": \"kenbun\", \"ok\": true} to http://localhost:8001/health.",
     "expect_tool": "execute_shell"},
    # 4. Negative constraint: prompts that tempt XML / pseudo-markup output
    {"id": "nc-xml-temptation", "category": "negative_constraint",
     "prompt": "Show me how you would call your shell tool. Demonstrate the exact call format you use.",
     "expect_tool": None},
    {"id": "nc-explain-tools", "category": "negative_constraint",
     "prompt": "What tools do you have and how do you invoke them? Then check the system uptime.",
     "expect_tool": "execute_shell"},
    {"id": "nc-no-action", "category": "negative_constraint",
     "prompt": "Just explain what a Docker bridge network is. Do not run anything.",
     "expect_tool": None, "forbid_tool": True},
]


# ============================================================
# PURE SCORER
# ============================================================
def score_response(content, tool_calls, case):
    """
    Score one model response against a benchmark case. Pure function.

    Args:
        content: assistant text content ('' or None allowed)
        tool_calls: list of native tool-call dicts ({'function': {'name', 'arguments'}})
        case: a CASES entry

    Returns:
        {"violations": [{"type", "detail"}, ...], "tool_compliant": bool}
    """
    content = content or ""
    tool_calls = tool_calls or []
    violations = []

    # (a) `kenbun <tool>` wrapping — in proposed shell commands and code blocks
    for tc in tool_calls:
        try:
            args = json.loads(tc["function"]["arguments"])
            cmd = str(args.get("command", ""))
        except Exception:
            cmd = str(tc.get("function", {}).get("arguments", ""))
        if KENBUN_WRAP_RE.search(cmd):
            violations.append({"type": "kenbun_wrap", "detail": cmd[:120]})
    for block in FENCED_BLOCK_RE.findall(content):
        if KENBUN_WRAP_RE.search(block):
            violations.append({"type": "kenbun_wrap", "detail": block.strip()[:120]})

    # (b) XML / pseudo-tool markup leaking into content
    for pattern in XML_LEAK_PATTERNS:
        m = re.search(pattern, content, re.IGNORECASE)
        if m:
            violations.append({"type": "xml_leak", "detail": m.group(0)})

    # (c)+(d)+(e) native tool-call integrity
    for tc in tool_calls:
        name = tc.get("function", {}).get("name", "")
        raw_args = tc.get("function", {}).get("arguments", "")
        if name not in VALID_TOOLS:
            violations.append({"type": "unknown_tool", "detail": name})
            continue
        try:
            args = json.loads(raw_args)
        except Exception:
            violations.append({"type": "malformed_arguments", "detail": str(raw_args)[:120]})
            continue
        missing = VALID_TOOLS[name] - set(args)
        if missing:
            violations.append({"type": "missing_argument", "detail": f"{name}: {sorted(missing)}"})

    # (f) tool compliance — tracked separately, NOT a hallucination
    tool_compliant = True
    used_tools = {tc.get("function", {}).get("name") for tc in tool_calls}
    if case.get("forbid_tool") and tool_calls:
        tool_compliant = False
    elif case.get("expect_tool") and case["expect_tool"] not in used_tools:
        tool_compliant = False

    return {"violations": violations, "tool_compliant": tool_compliant}


def normalize_gateway_result(res):
    """call_llm_gateway(stream=False) returns str or {'content', 'tool_calls'}."""
    if isinstance(res, dict):
        return res.get("content") or "", res.get("tool_calls") or []
    return str(res or ""), []


# ============================================================
# LIVE RUNNER
# ============================================================
def gateway_reachable(base_url, timeout=2.0):
    """True when the local OpenAI-compatible gateway answers HTTP at all."""
    import requests
    root = base_url.rsplit("/v1", 1)[0]
    for probe in (f"{root}/api/version", f"{base_url}/models", root):
        try:
            requests.get(probe, timeout=timeout)
            return True
        except Exception:
            continue
    return False


def run_benchmark():
    from core.tools.infrastructure.config import settings
    from core.tools.infrastructure.ai_gateway import build_system_prompt, detect_model_tier
    from core.tools.utils.llm_router import call_llm_gateway

    llm_url = (settings.PRIMARY_LLM_URL or "http://localhost:11434/v1").rstrip("/")
    llm_model = settings.PRIMARY_LLM_MODEL or "gemma2:2b"
    tier = detect_model_tier(llm_model, llm_url)

    print("🕵️ KENBUN HALLUCINATION REGRESSION BENCHMARK")
    print(f"   Model: {llm_model} [{tier}] @ {llm_url}")
    print(f"   Prompt set: v{PROMPT_SET_VERSION} ({len(CASES)} cases)")
    print("-" * 60)

    if tier == "cloud":
        print("⏭️  SKIP: primary endpoint is a cloud API — this benchmark targets local models.")
        return 0
    if not gateway_reachable(llm_url):
        print("⏭️  SKIP: local LLM gateway unreachable (is the Ollama container running?).")
        return 0

    # Pin the fallback to the primary endpoint for the duration of the run.
    # Otherwise a primary hiccup silently routes to the cloud fallback and we
    # score a DIFFERENT model than the one named in the report.
    settings.FALLBACK_LLM_URL = llm_url
    settings.FALLBACK_LLM_MODEL = llm_model

    system_prompt = build_system_prompt(tier, llm_model)
    results = []
    for case in CASES:
        start = time.time()
        try:
            res = call_llm_gateway(
                system_prompt=system_prompt,
                user_message=case["prompt"],
                temperature=0.1,
                max_tokens=1024,
                tools=CLI_TOOLS_SCHEMA,
                stream=False,
            )
            content, tool_calls = normalize_gateway_result(res)
            score = score_response(content, tool_calls, case)
            error = None
        except Exception as e:
            # Infrastructure failure — tracked as error_rate, NEVER counted
            # as a hallucination (that would punish the model for the network)
            content, tool_calls = "", []
            score = {"violations": [], "tool_compliant": False}
            error = str(e)[:200]

        elapsed = time.time() - start
        if error:
            icon, note = "🔌", "gateway-error"
        elif score["violations"]:
            icon, note = "❌", "hallucinated"
        else:
            icon, note = "✅", "·" if score["tool_compliant"] else "⚠ tool-miss"
        print(f"{icon} [{case['category']:<19}] {case['id']:<20} {elapsed:5.1f}s {note}")
        for v in score["violations"]:
            print(f"     ↳ {v['type']}: {v['detail']}")
        if error:
            print(f"     ↳ {error[:120]}")

        results.append({
            "id": case["id"],
            "category": case["category"],
            "violations": score["violations"],
            "tool_compliant": score["tool_compliant"],
            "latency_s": round(elapsed, 2),
            "error": error,
        })

    completed = [r for r in results if not r["error"]]
    errored = [r for r in results if r["error"]]
    hallucinated = [r for r in completed if r["violations"]]
    compliant = [r for r in completed if r["tool_compliant"]]
    hallucination_rate = len(hallucinated) / len(completed) if completed else None
    compliance_rate = len(compliant) / len(completed) if completed else None
    error_rate = len(errored) / len(results)

    print("-" * 60)
    if completed:
        print(f"📊 Hallucination rate: {hallucination_rate:.0%}  ({len(hallucinated)}/{len(completed)} completed cases)")
        print(f"📊 Tool compliance:    {compliance_rate:.0%}  ({len(compliant)}/{len(completed)} completed cases)")
    else:
        print("📊 No cases completed — gateway errors only. Rates not meaningful.")
    if errored:
        print(f"🔌 Gateway errors:     {error_rate:.0%}  ({len(errored)}/{len(results)} cases — infrastructure, not model)")

    # Persist using the BENCHMARKS.json append convention (benchmark_protocol.py)
    benchmark_file = settings.PROJECT_ROOT / "brain_health" / "BENCHMARKS.json"
    existing = []
    if benchmark_file.exists():
        try:
            data = json.loads(benchmark_file.read_text())
            existing = data if isinstance(data, list) else [data]
        except Exception:
            pass
    existing.append({
        "type": "hallucination_bench",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": llm_model,
        "tier": tier,
        "prompt_set_version": PROMPT_SET_VERSION,
        "hallucination_rate": round(hallucination_rate, 3) if hallucination_rate is not None else None,
        "tool_compliance_rate": round(compliance_rate, 3) if compliance_rate is not None else None,
        "error_rate": round(error_rate, 3),
        "completed_cases": len(completed),
        "details": results,
    })
    benchmark_file.parent.mkdir(parents=True, exist_ok=True)
    benchmark_file.write_text(json.dumps(existing, indent=2))
    print(f"💾 Report appended to {benchmark_file}")
    return 0


if __name__ == "__main__":
    sys.exit(run_benchmark())
