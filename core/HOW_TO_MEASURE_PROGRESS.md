# 📊 How to Know Kenbun/core Is Actually Getting Better

**Question:** "I can't tell how good my program is, if it actually works, and if it's getting better at coding and logic."

**Answer:** You don't *feel* improvement. You **measure** it. Right now you have telemetry pieces (`brain_health/BENCHMARKS.json`, `routing_history.jsonl`, `usage_stats.json`, `live_telemetry.json`) but no single dashboard that says **"yesterday I was 73% accurate, today I'm 81%."** That's the gap.

This doc gives you a concrete plan to close it.

---

## 🎯 The 3 Questions You Need a Number For

| Question | Metric | Where it lives today | Status |
|---|---|---|---|
| **"Does it work?"** | Smoke-test pass rate | nowhere | ❌ build it |
| **"Is it correct?"** | Benchmark accuracy on a fixed test set | `brain_health/BENCHMARKS.json` | ⚠️ partial |
| **"Is it getting better?"** | Day-over-day delta on the same benchmarks | nowhere | ❌ build it |

If you don't have all three, you're flying blind. Period.

---

## 📐 What "Better" Actually Means (define it once)

Pick **5 measurable axes** and grade every release on all 5. Suggested for an AI coding assistant:

1. **Routing accuracy** — % of tasks the `DecisionRouter` sends to the right pipeline. You already log to `routing_history.jsonl` and `routing_failures.jsonl`. → just need a script to compute the ratio.
2. **Bug-fix success rate** — % of bug-fix swarms where the sandbox test passes after the fix. Already partially tracked in `usage_stats.json` per-tool.
3. **Hallucination rate** — % of `consult_supervisor` answers that fail backward verification (`maze_protocol.py`). You have `HALLUCINATION_TEST.py` — turn its output into a number.
4. **Latency budget** — median seconds per orchestrate(); fail-budget if > X. Already in `telemetry.py:log_tool_performance`.
5. **Cost discipline** — $ per swarm vs. budget. Already in `token_governor.py` + `usage_stats.json`.

Each axis becomes a column in `BENCHMARKS.json`, scored every night.

---

## 🧪 The 4-Layer Testing Pyramid You're Missing

You have pieces of every layer but no continuous runner. Build them in this order:

### Layer 1 — Smoke tests (5 min to add, pays off forever)

Create `tests/test_smoke.py`:
```python
import importlib, pytest

CRITICAL_MODULES = [
    "tools.core.orchestrator", "tools.core.server", "tools.core.api_server",
    "tools.memory.knowledge_manager", "tools.memory.code_indexer",
    "tools.utils.error_memory", "tools.audit.gemini_reviewer",
    "tools.audit.supervisor_agent", "tools.audit.guardrail_agent",
    "tools.strategy.decision_logic", "tools.strategy.token_governor",
    "tools.execution.sandbox_runner",
]

@pytest.mark.parametrize("mod", CRITICAL_MODULES)
def test_module_imports(mod):
    importlib.import_module(mod)
```

This single file would have caught the import drift we just fixed. Run it on every commit.

### Layer 2 — Unit tests for pure logic

`tools/strategy/decision_logic.py`, `tools/utils/maze_protocol.py`, `tools/utils/backtracker.py` are all deterministic — they should have 100% line coverage. Use `pytest --cov=tools` and refuse to merge anything below 80%.

### Layer 3 — Golden-set integration tests (the most important layer)

Take `brain_health/generated_cases.json` (you already have 150 of them!) and run them every night:

```python
# brain_health/nightly_eval.py  (sketch)
from tools.strategy.decision_logic import router
import json, time, datetime

cases = json.load(open("brain_health/generated_cases.json"))
correct = 0
for c in cases:
    pred = router.get_strategy_path(c["task"])
    if pred == c["expected_path"]:
        correct += 1

score = correct / len(cases)
record = {"date": str(datetime.date.today()), "routing_accuracy": score}

with open("brain_health/BENCHMARKS.json", "r+") as f:
    data = json.load(f)
    data.setdefault("history", []).append(record)
    f.seek(0); json.dump(data, f, indent=2)

print(f"Routing accuracy: {score:.1%} ({correct}/{len(cases)})")
```

Add the same for: hallucination rate (use `HALLUCINATION_TEST.py`), bug-fix success (a synthetic bug bank), supervisor agreement-with-Gemini rate.

### Layer 4 — Adversarial / chaos

You already have `CHAOS_TEST.py` and `chaos_orchestrator.py`. Schedule them weekly. They're worthless if they don't run automatically.

---

## 📈 The "Am I Improving?" Dashboard

You have `tools/observatory/` (Next.js). Three charts will tell you everything:

1. **Time series of all 5 axes** (lines on one graph, last 30 days). Are they trending up?
2. **Top 5 failing test cases** from the golden set. These are your debugging targets for the week.
3. **Cost per successful swarm** (`total_cost / successful_swarms`). This should *fall* over time as caching/recall improves.

If you can't tell from a glance whether the system is improving, the dashboard is wrong. Iterate until it's a glance-able answer.

---

## 🤖 Make the System Audit Itself (you almost have this)

You already have:
- `brain_health/AUTONOMOUS_LEARNING.py`
- `tools/audit/reflection_agent.py` (`reflect_and_distill`)
- `dev/self_evolution/awareness_engine.py`

What's missing: a **scheduled cron** that runs nightly, executes the golden-set, diffs today vs yesterday, and writes a **daily report** like:

```
=== Kenbun Daily Report — 2026-05-05 ===
Routing accuracy:       81% (▲ +3% vs yesterday)
Bug-fix success:        67% (▼ -2%)
Hallucination rate:      9% (▲ better, was 12%)
Median orchestrate():  14.2s (flat)
Cost per swarm:        $0.034 (▼ better, was $0.041)

🆕 New regression: pipeline `code_review` started failing on Python 3.11 type-hint cases.
🏆 Win: error-recall hit rate up to 41% — the Hivemind is paying off.
```

Pipe it to a Telegram message via your existing `swarm_voice.py` infrastructure → you get a daily verdict on your phone.

---

## 🚦 Concrete 1-Week Plan to Get You "Working & Improving" Visibility

| Day | Action | Outcome |
|---|---|---|
| **Mon** | Add `tests/test_smoke.py` + `pyproject.toml` w/ pytest config. Hook into a `make test` target. | You can prove the system *imports*. |
| **Tue** | Move `brain_health/test_*.py` into `tests/` and make them pass headlessly (no API keys needed for unit-level). | You can prove the *logic* works. |
| **Wed** | Write `brain_health/nightly_eval.py` to score all 150 cases against `routing_history.jsonl`. Append to `BENCHMARKS.json`. | You have **today's number**. |
| **Thu** | Run yesterday's snapshot vs today's; compute deltas per axis; write `daily_report.md`. | You can answer "is it improving today?" |
| **Fri** | Add a cron / launchd job to run Wed+Thu pipelines at 03:00. Pipe report to Telegram. | The system grades itself every night. |
| **Sat** | Add the 3 charts to `tools/observatory/` reading `BENCHMARKS.json`. | You can see the trend at a glance. |
| **Sun** | Pick the worst-scoring axis. Spend the week improving *only that one*. Re-measure Sunday. | First proof of improvement. |

**Total effort: ~1 week. Total payoff: you stop guessing whether your AI is getting smarter.**

---

## 🔥 The Brutal Truth

Right now you have:
- ✅ Excellent architecture & docs
- ✅ Telemetry primitives (logs, benchmarks, weights, usage stats)
- ✅ A self-reflection loop (`reflection_agent`)
- ❌ No automatic test runner
- ❌ No nightly benchmark execution
- ❌ No day-over-day delta report
- ❌ No "is it better than yesterday?" dashboard

You built the speedometer parts. You haven't wired them into the dashboard yet. Doing so will **change how you feel about this project in 7 days** — because feelings will become numbers.

Once you have the daily report, every architectural choice becomes obvious: "did this improve the score? keep it. did it not? revert it."

That's how you go from "hoping it's getting better" to **knowing**.

---

*This document is a companion to `ARCHITECTURE_AUDIT.md`. Architecture is the foundation; measurement is how you know the foundation holds.*