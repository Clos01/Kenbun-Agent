# 🕵️ Kenbun Tool-Rot Audit

**Date:** 2026-06-12 · **Method:** exercise every tool with a cheap smoke input, classify the response.

## Top finding — the one bug behind a third of the rot

There are **two parallel checkouts** of this repo on disk:

```
/Users/carlosrivas/Dev/Kenbun         ← old checkout, the running MCP server is rooted here
/Users/carlosrivas/Dev/kenbun-agent   ← the active working tree (everything we've been editing)
```

The kenbun MCP server you connected was started inside the *old* directory and has stayed there, so:

- Every file-operating tool (`save_checkpoint`, `restore_checkpoint`, `autofix_linter`) rejects paths inside the working tree as "outside secure workspace" — they enforce the security boundary correctly; the boundary is just pointing at the wrong checkout.
- `save_to_hivemind` / `recall_fix` / `search_hivemind_concepts` write to the *other* repo's ChromaDB. Today's session has been writing memories to a directory you don't see.
- `orchestrate`'s earlier `KeyError: 'autofix_linter'` was the *old* checkout's stale registry — fixed in this tree, never reloaded by the MCP server.
- The `Dev/Kenbun` vs `Dev/kenbun-agent` case-difference is also what makes macOS's case-insensitive filesystem show duplicate paths in some lookups.

**Fix:** kill the kenbun MCP process and restart it from `/Users/carlosrivas/Dev/kenbun-agent`. Then either delete `/Users/carlosrivas/Dev/Kenbun` or move it aside, so future MCP launches can't accidentally re-root there. Most "degraded" rows below will turn green after that single change.

---

## MCP tool scorecard (26 of 26 probed)

✅ **Works (15)** — orchestrate · scan_repo · search_codebase · think_about_tools · audit_guardrail · save_to_hivemind · recall_fix · prune_hivemind · search_hivemind_concepts · ingest_url_to_hivemind · delete_from_hivemind · review_code_with_gemini · research_with_gemini · ask_architect · ask_ui_expert · list_checkpoints

⚠️ **Degraded — same-repo issue** (3) — `save_checkpoint`, `restore_checkpoint`, `autofix_linter`: reject every path in the active tree because of the stale-MCP-root above.

❌ **Real bugs** (4)

| Tool | Symptom | Likely cause |
|---|---|---|
| `reflect_on_task` | `pydantic validation error: result Input should be a valid string` | handler returns a `dict`; the MCP schema declares `string`. One-line fix: `json.dumps(...)` on the way out. |
| `get_brain_health` | reports `0%` / `unknown` / "last updated 2026-05-30" | parser doesn't recognize the current `BENCHMARKS.json` shape (the new hallucination_bench entries broke it). |
| `get_intelligence_stats` | "no intelligence data collected" | only reads the *remote* store; the populated local SQLite is ignored. |
| `audit_package_safety` | "ecosystem 'pip' not yet supported" | npm-only; pip path is a stub. Misleading because the tool's signature defaults `ecosystem="npm"` but description says "Supports: npm, pip." |

🔌 **Blocked by external state (not the tool's fault)** (2) — `run_code_safely` (Docker daemon down), `consult_supervisor` (LM Studio System 2 model unreachable).

🕳️ **Likely empty input, not broken** (2) — `get_design_tokens` returned `{}` (DESIGN.md is missing/empty), `research_official_docs` returned "No results" (probably needs a different tech_key registry entry; not a code bug).

---

## Deeper finding from Pass 2 (telemetry vs intelligence)

| Surface | State |
|---|---|
| Telemetry stream | **Healthy** — 3,708 events (logs, topology, reflections) since session start. |
| Bayesian intelligence DB | **One-eyed** — 45 tools registered, 9 ever recorded an outcome, **zero failures ever logged**. The governor that's supposed to rank tools sees only successes, so it cannot rank anything. |
| Checkpoint registry | **Hoarding** — 102 checkpoints, ~96 of them are `pre_linter_autofix` against the same two test fixtures (`dummy.py`, `broken.py`). Either prune on TTL or stop checkpointing test fixtures. |
| Hivemind | **Drift** — `prune_hivemind` removed 9 of 24 concepts as "redundant" in one call. Most surviving concepts are near-duplicates of the GPU-decoupling lesson saved by repeated orchestrate runs. |

The Bayesian feedback loop being failure-blind is the *single* highest-leverage fix for "how powerful kenbun is" — it's the difference between a system that learns and one that just remembers.

---

## What gets fixed next (sequence)

1. **Restart the MCP server from the right cwd**, archive the duplicate checkout. Re-run Pass 1; expect 3 ⚠️ rows to flip ✅.
2. **`reflect_on_task` return type fix** (one line). Re-run; another ❌ flips ✅.
3. **Wire failure reporting into the Bayesian governor** — every tool call site that catches an exception needs to call `track_failure(tool_id)`. Without this the "intelligence" claim is decorative.
4. **`get_brain_health` parser** — extend to read `type=hallucination_bench` rows so today's benchmark counts toward health.
5. **`get_intelligence_stats` fallback** — read local SQLite when remote is down; the data exists, it's just behind a feature flag.

---

## How this audit stays honest

The probe set is now a regression test at [core/tests/test_tool_surface.py](../core/tests/test_tool_surface.py). It exercises every MCP tool with the same cheap smoke input as this audit and asserts the response is non-empty and non-error. Any future rot trips it in CI, before a user runs into it.
