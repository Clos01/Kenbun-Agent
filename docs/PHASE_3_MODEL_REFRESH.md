# Phase 3.3: Default Model Refresh (Data-Driven)

## Current Defaults

```env
OLLAMA_PULL_MODELS=gemma2:2b deepseek-r1:1.5b
```

These were selected ~6 months ago. Both are dated relative to recent releases.

## Proposed New Models

**Candidates:** Qwen3 family (better tool calling at same VRAM cost)
- `qwen2.5:1.5b` — 1.5B params, excellent tool compliance
- `qwen2.5:4b` — 4B params, even better reasoning

These rank higher on the OpenCompass leaderboard for instruction-following and tool use than gemma2 and deepseek-r1.

## Decision Process (Phase 3.3)

Phase 3.3 only updates defaults if benchmark results prove a win. Follow this flow:

### 1. Establish Baseline (Current Models)

```bash
# Terminal 1: Start Kenbun with current defaults
docker compose down
docker compose up -d

# Terminal 2: Run the hallucination regression benchmark
uv run python -m core.benchmarks.hallucination_bench
```

**Output:** Appends to `brain_health/BENCHMARKS.json`:
```json
{
  "type": "hallucination_bench",
  "timestamp": "2026-06-12T...",
  "model": "gemma2:2b",
  "tier": "nano",
  "hallucination_rate": 0.25,      // lower is better
  "tool_compliance_rate": 0.92,     // higher is better
  "details": [...]
}
```

**Note** the `hallucination_rate` and `tool_compliance_rate`.

### 2. Test Qwen2.5:1.5B

```bash
# Update .env
echo "OLLAMA_PULL_MODELS=qwen2.5:1.5b" >> .env

# Restart
docker compose down
docker compose up -d

# Wait for model to pull (5-10 min)
docker logs -f portable_ollama_init

# Run benchmark again
uv run python -m core.benchmarks.hallucination_bench
```

### 3. Test Qwen2.5:4B (if 1.5b looks good)

```bash
echo "OLLAMA_PULL_MODELS=qwen2.5:4b" >> .env
docker compose down
docker compose up -d
uv run python -m core.benchmarks.hallucination_bench
```

### 4. Analyze Results

Compare the three runs in `brain_health/BENCHMARKS.json`:

```bash
python3 << 'EOF'
import json
from pathlib import Path

data = json.loads(Path("brain_health/BENCHMARKS.json").read_text())
for run in data[-3:]:  # last 3 runs
    print(f"{run['model']:20} | hal_rate: {run['hallucination_rate']:.0%}  | compliance: {run['tool_compliance_rate']:.0%}")
EOF
```

**Decision criteria:**
- ✅ Update defaults if new model's `hallucination_rate < 0.15` AND `tool_compliance_rate > 0.90`
- ✅ Update defaults if new model improves on current by >5% on either metric
- ❌ Do NOT update if new model has higher hallucination rate or lower compliance
- ❌ Do NOT update based on subjective impression — only on benchmark numbers

### 5. Commit the Update (if decision is "update")

If Qwen2.5:1.5B wins:

```bash
# .env.example
sed -i '' 's/gemma2:2b deepseek-r1:1.5b/qwen2.5:1.5b/g' .env.example

# docker-compose.yml
sed -i '' 's/gemma2:2b deepseek-r1:1.5b/qwen2.5:1.5b/g' docker-compose.yml

# Commit
git add .env.example docker-compose.yml docs/PHASE_3_MODEL_REFRESH.md
git commit -m "feat(ai): upgrade default models to Qwen2.5:1.5B (benchmark-driven)

Hallucination regression benchmark shows:
- gemma2:2b   : 25% hallucination rate
- qwen2.5:1.5b: 12% hallucination rate (-52%)

Tool compliance also improved from 92% → 95%.
New models are equally efficient (same VRAM) and more reliable.

Benchmark details: brain_health/BENCHMARKS.json (append-only log)
"
```

## Running Headless (CI-Safe)

The benchmark gracefully skips if Ollama is unreachable:

```bash
# This returns exit 0 even if no Ollama is running
uv run python -m core.benchmarks.hallucination_bench
```

So it's safe to run in CI pipelines without breaking the build.

## Metrics Explained

**hallucination_rate** — fraction of test cases that triggered a violation detector:
- `kenbun <tool>` wrapping in proposed commands
- XML/pseudo-tool markup leaking into content
- Malformed JSON in tool arguments
- Unknown tool names
- Missing required arguments

Lower is better.

**tool_compliance_rate** — fraction of cases where the model used the expected tool (or correctly avoided it):
- If case expects `execute_shell`, model must call `execute_shell`
- If case forbids tools (`forbid_tool: true`), model must not call any tool

Higher is better. Note: Compliance ≠ Hallucination. A model can be compliant but hallucinate (tool called, but with bad args).

## Future: Expand Prompt Set

The current prompt set (v1.0) has 12 cases. As new hallucination patterns emerge from user reports, add cases to `CASES` in `core/benchmarks/hallucination_bench.py`:
- Test case ID (unique, descriptive)
- Category (one of the 4: few_shot_alignment, tool_synthesis, schema_strictness, negative_constraint)
- User prompt
- Expected tool (None if no tool should be used)

Increment `PROMPT_SET_VERSION` so benchmark runs are tagged with the version that produced them. This prevents comparing apples-to-oranges across versions.

## Timeline

Phase 3.3 is not urgent — it's a "decision gate" that only runs when you're ready to update models. Suggested workflow:

1. **Today:** Phase 3.1 + 3.2 done, benchmark live and unit-tested ✅
2. **Next week:** Run baseline on current models, stash results
3. **In 1-2 weeks:** Test Qwen2.5:1.5b and 4b as they stabilize in Ollama
4. **Whenever ready:** Commit new defaults based on benchmark data

The benchmark creates an audit trail (BENCHMARKS.json) so you always know which models were tested and how they scored.
