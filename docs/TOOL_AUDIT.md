# 🕵️ Kenbun Tool-Rot Audit

**Date:** 2026-06-12 · **Method:** exercise every tool with a cheap smoke input, classify the response.

## Top finding — kenbun's single-root architecture is a multi-project hazard

There are two distinct kenbun installations on disk by design:

```
/Users/carlosrivas/Dev/Kenbun         ← personal day-to-day install (MCP server rooted here)
/Users/carlosrivas/Dev/kenbun-agent   ← the open-source release (this checkout)
```

The MCP server can only have ONE workspace root at a time, and it's locked to the personal install. Any time you collaborate on the open-source `kenbun-agent` from a session connected to the personal MCP server:

- File-operating tools (`save_checkpoint`, `restore_checkpoint`, `autofix_linter`) reject paths in this tree as "outside secure workspace" — the security guard is doing its job; the boundary just doesn't extend here.
- `save_to_hivemind` / `recall_fix` / `search_hivemind_concepts` write to the **personal** ChromaDB, mixing project memories silently.
- `orchestrate`'s earlier `KeyError: 'autofix_linter'` was running the personal install's stale registry — the fix shipped in this tree was invisible to the MCP server.

This isn't tool rot. It's a real product gap: **kenbun has no concept of "current project."** Either run a separate MCP server per project (heavy), or `settings.PROJECT_ROOT` needs to become dynamic — derived from the calling client's cwd or set per-call. Until then, the workflow is:

1. For OSS work: run the OSS install's MCP server (`cd kenbun-agent && uv tool run kenbun-mcp`) and connect Claude to *that*, not the personal one.
2. For personal work: connect to the personal MCP server.
3. Never both at once — the hivemind cross-pollination is a feature for one user, a leak for a release.

---

## MCP tool scorecard (26 of 26 probed)

✅ **Works (15)** — orchestrate · scan_repo · search_codebase · think_about_tools · audit_guardrail · save_to_hivemind · recall_fix · prune_hivemind · search_hivemind_concepts · ingest_url_to_hivemind · delete_from_hivemind · review_code_with_gemini · research_with_gemini · ask_architect · ask_ui_expert · list_checkpoints

⚠️ **Cross-project scope mismatch** (3) — `save_checkpoint`, `restore_checkpoint`, `autofix_linter`: reject paths here because they're outside the personal install's `PROJECT_ROOT`. Source code is fine; this is the single-root architecture issue above.

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

1. **Per-project MCP scope** (architectural) — `settings.PROJECT_ROOT` becomes either dynamic (resolved per call from the connecting client's cwd) or there's an explicit `/switch-project` slash command. Without this, every user with more than one project runs into the same wall.
2. **`get_intelligence_stats` local-DB fallback** — already pinned by the new regression test. The local SQLite is populated; the read path just ignores it.
3. **`audit_package_safety`: ship pip support or stop advertising it** — also pinned by the regression test.
4. **Wire failure reporting into the Bayesian governor** — every tool call site that catches an exception needs to call `track_failure(tool_id)`. Currently 0 failures logged across 45 tools, so the self-tuning intelligence has nothing to tune on.
5. **`get_brain_health` parser** — extend to read `type=hallucination_bench` rows so today's benchmark counts toward health (verify via the MCP wrapper, not in-process; the in-process source is healthy).

---

## How this audit stays honest

The probe set is now a regression test at [core/tests/test_tool_surface.py](../core/tests/test_tool_surface.py). It exercises every MCP tool with the same cheap smoke input as this audit and asserts the response is non-empty and non-error. Any future rot trips it in CI, before a user runs into it.
