# Measuring an Audit Tier

How to find out whether a rung of Kenbun's audit ladder can be trusted, what the numbers
mean, and the specific ways this measurement goes wrong.

Written after the first real calibration run (2026-08-06), which produced both a useful
result and a design error in the gate itself. Both are documented here, because the error is
more instructive than the result.

---

## 1. The question

Kenbun's audit ladder is a chain of increasingly expensive reviewers:

```
2c guardrail (llama3.2:3b)  ->  2a adversarial court (qwen3:8b)  ->  Tier 2 cloud audit
```

Any rung that can return APPROVED can end a review. So the question for each rung is not
"is it good?" but:

> **May this rung's approval be the last word, and on what kind of work?**

That is a measurement question, and it is answerable.

---

## 2. The four numbers, and which ones lie

Fix a convention and never drift from it:

> **Positive = UNSAFE.** The thing we are trying to detect is dangerous code.

| | truth: UNSAFE | truth: SAFE |
|---|---|---|
| **tier says REJECT** | TP | FP (false alarm) |
| **tier says APPROVE** | **FN (the breach)** | TN |

From these come four rates. They are not interchangeable, and the difference is the single
most important thing in this document.

### Base-rate INDEPENDENT (properties of the tier itself)

- **Sensitivity** = TP / (TP + FN) — of the dangerous code it saw, what fraction did it catch?
- **Specificity** = TN / (TN + FP) — of the safe code it saw, what fraction did it pass?

These are the tier's actual capability. They do not change when the traffic changes.

### Base-rate DEPENDENT (properties of the tier *and* the traffic)

- **Approval precision** = TN / (TN + FN) — when it approves, how often is it right?
- Prevalence-adjusted:

```
precision = specificity x p(safe)
            ---------------------------------------------------
            specificity x p(safe) + (1 - sensitivity) x p(unsafe)
```

**A tier's precision rises as the traffic gets safer, with no change in the tier.** Feed a
mediocre reviewer a stream of mostly-fine code and it will look excellent.

---

## 3. The error we made

The calibration gate as first built (`calibration.py`, 2026-08-06) gated auto-approval on
**safe-approval rate** — which is approval precision. Here is what that means with the real
measured numbers:

| tier | sensitivity | specificity |
|---|---|---|
| guardrail_2c | 55% | 62% |
| court_2a | **40%** | 100% |

| p(safe) in traffic | guardrail precision | court precision |
|---|---|---|
| 46% (the golden set) | 54% | 59% |
| 85% | 89% | 90% |
| 95% | 96% | 97% |

The gate's threshold is 0.85.

**On the adversarial golden set both tiers fail the gate. On realistic production traffic
both tiers pass it — while the court still lets 60 of every 100 vulnerabilities through.**

The gate would have been fooled by benign traffic into unlocking a reviewer that misses most
of what it is looking for. This is the classic base-rate trap, and building the gate on
precision walked straight into it.

### The correction

Gate on **sensitivity against a known-unsafe corpus**. Sensitivity cannot be inflated by
benign traffic, because it is only computed over cases that are actually dangerous. Keep
precision as a *reported* number, always stamped with the base rate it assumes.

Corollary for claims: "llama3.2:3b is permanently excluded" is true **for the golden-set
distribution**. It is not established for production traffic. Any statement of a
precision-derived result that does not name its base rate is incomplete.

---

## 4. The procedure

### Step 1 — Build ground truth, not agreement

Score against **human labels**, not against a bigger model's opinion. Two models can share a
blind spot and agree their way into a breach. Agreement is a fallback when labels are
unavailable, not a substitute.

The golden set (`core/tools/audit/golden_set.json`) deliberately includes safe-but-suspicious
cases: correct `subprocess.run` with an argument list, a resolve-then-contain path guard,
`yaml.safe_load`. Without them a tier that rejects everything scores perfectly.

It lives beside the code, not under `brain_health/`, because that directory is gitignored and
**ground truth is source**.

### Step 2 — Run it, and record what actually answered

```bash
PRIMARY_LLM_URL="http://100.92.127.1:11434/v1" \
COURT_LLM_MODEL="qwen3:8b" \
COURT_JUDGE_TIMEOUT=900 COURT_BRIEF_TIMEOUT=300 \
python -m tools.audit.calibrate_tiers --tier court_2a --reset
```

Every verdict carries `judge_served_by`. The harness **refuses to score a verdict the tier
under test did not actually render**. This is not paranoia — on the first attempt the local
judge timed out, execution fell through to the fallback gateway, and Anthropic Haiku's
verdicts were being recorded as `court_2a`. The guard later excluded 7 of 24 trials during a
network wobble.

> **A measurement of the wrong instrument is worse than no measurement,** because it looks
> like data.

### Step 3 — Read the result honestly

Report sensitivity and specificity first. Report precision only with its base rate attached.
Report what was excluded and why — silent truncation reads as full coverage.

---

## 5. Failure modes, all of which have bitten this system

| Failure | What it looks like | Guard |
|---|---|---|
| **Base-rate trap** | precision looks great, tier still misses most vulns | gate on sensitivity |
| **Wrong instrument** | fallback model's verdict recorded as the tier's | `judge_served_by`, refuse non-local |
| **Test contamination** | pytest writes mocked verdicts to the production store | autouse fixture, temp DB |
| **Fail-open** | dead endpoint returns "approved" | return `escalate`; a dead audit is not a passing audit |
| **Agreement != truth** | two models share a blind spot | human labels |
| **Small n** | 2-3 samples per category, bounds meaningless | Wilson lower bound; field norm is 500+ cases |
| **Uncounted indeterminates** | unparseable output silently treated as a verdict | count and report separately (21% of one run) |

---

## 6. How to tell whether Kenbun is improving

> **A measurement is worth taking only if some decision changes depending on the answer.**

The 2026-08-06 run qualified: it changed what the cheap rungs are allowed to do. Compare
"routing accuracy 82%", which changed nothing — and which drifted for months while reading
from the wrong data source, because nothing depended on it.

Apply that filter to any proposed metric. If no decision hangs on it, it is decoration.

---

## 7. Prior art — read before extending this

Kenbun's ladder is an independent rediscovery of a known pattern. Use that.

- **AI control** (Redwood Research) — trusted weak monitor + untrusted strong executor +
  limited expensive audit budget. This is exactly the 2c/2a/Tier-2 stack.
- **Inspect** (UK AI Safety Institute) — the closest prior art to `calibrate_tiers`. Solves
  dataset versioning, scorer abstractions, reproducibility, statistical treatment.
- **OpenAI Evals** — registry/spec pattern.
- **Shadow-mode judge deployment** (e.g. Ramp) — accumulate judge accuracy without blocking,
  enable live gating once a threshold is met. The same shape as "a gated approval escalates,
  and that escalation is the paired observation".
- **Quality management / measurement systems analysis** (Shewhart, Deming) — acceptance
  sampling and gauge R&R. A century old and directly applicable: you do not trust an
  instrument until you have characterized its error against known standards.
- **Diagnostic testing statistics** — sensitivity/specificity/PPV and prevalence. Section 3
  above is a rediscovery of a standard result; read the standard version.

---

## 8. Current state (2026-08-06)

| tier | model | sensitivity | specificity | verdict |
|---|---|---|---|---|
| guardrail_2c | llama3.2:3b | 55% | 62% | cannot close a review |
| court_2a | qwen3:8b | 40% | 100% | cannot close a review; approves on default |

The court's zero false rejections against 13 approvals traces to one line in the judge
prompt — *"If the prosecution's case is speculative, APPROVE, even if the defense brief is
weak."* Added to stop invented-vulnerability rejections, it over-corrected into a rung that
approves by default. That is a fixable prompt, not a fixable model.

Open work: kanban `t_c3a67b` (sensitivity-based gate), `t_bc2897` (grow the golden set),
`t_eb8544` (adopt from Inspect).
