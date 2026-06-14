# Kenbun Generalization & Optimization Plan

**Date:** 2026-06-12
**Scope:** The `Kenbun` repo only (not `kenbun-agent`). Plan only — no code changes yet.
**Goal:** Make Kenbun IDE-agnostic so any AI IDE (Claude Code, Cursor, Windsurf, VS Code/Copilot, JetBrains, Antigravity) can pick it up and use it without environment-specific setup.

---

## Test Run Results (2026-06-12)

`orchestrate` was called twice from Claude (Cowork) over MCP:

| Call | Result | Timeout? |
|---|---|---|
| `workflow: test` (invalid) | Returned workflow list instantly | No |
| `workflow: code_review` with snippet | Full pipeline ran: pre-flight audit → repo scan (1288 files) → supervisor sign-off → consensus | No |

**Verdict:** Orchestrate works from Claude with no timeout. If long pipelines time out later: Claude Code honors `MCP_TIMEOUT` / `MCP_TOOL_TIMEOUT` env vars; Claude Desktop has no user-facing MCP timeout setting, so the fix on Kenbun's side is to keep per-step responses under ~60s (stream progress, or return early and let the client poll). Kenbun already has `BASE_TIMEOUT` and `SWARM_TIMEOUT_MULTIPLIER` for its own internal calls.

---

## Audit: What Ties Kenbun to One Environment

### A. Antigravity-specific remnants
| Location | Issue |
|---|---|
| `core/tools/infrastructure/config.py:99-100` | `MASTER_KEY_PATH` defaults to `~/.gemini/antigravity/keys/` |
| `core/tools/infrastructure/config.py:289` | Legacy `antigravity_intelligence.db` migration (fine, but `core/antigravity_intelligence.db` still exists on disk) |
| `core/tools/infrastructure/config.py:334` | `AntigravitySettings = KenbunSettings` compat alias |
| `core/tools/utils/ide_context.py` | Conflates "Claude Code / Antigravity" as one IDE key; detection heuristic assumes `ANTHROPIC_API_KEY` presence = Claude |
| `docs/MCP_INTEGRATION.md` | Written primarily as an Antigravity integration guide |

### B. Machine-specific hardcoding (bigger portability blocker)
| Location | Issue |
|---|---|
| `update_claude_config.py` | **Plaintext `GEMINI_API_KEY` committed to repo — rotate this key immediately.** Also hardcodes Tailscale host `lg2025.tailbe4852.ts.net`, IP `100.104.211.61`, LM Studio port `2065`, and `/Users/carlosrivas/...` paths |
| `claude_desktop_config.json`, `test_mcp.py`, `test_mcp_tools.py` | Hardcoded `/Users/carlosrivas/...` paths and Tailscale IPs |
| `core/tests/test_speculative_decoding.py:22` | Hardcoded fallback IP `100.104.211.61` |
| `core/scratch/test_models_direct.py` | Hardcoded Tailscale URL |
| `core/NEURAL_HIERARCHY.md` | Docs reference "Remote PC (100.104.211.61)" |

### C. Naming confusion with kenbun-agent
`.env.example` is headed "KENBUN-AGENT DECOUPLED SWARM CONFIGURATION" and its `PROJECT_ROOT` example points to a cloned `kenbun-agent` directory. This is exactly the Kenbun vs. kenbun-agent mix-up to eliminate.

### D. Repo hygiene (slows down any IDE picking it up)
Root is cluttered with scratch/test/log files: `mcp_debug.log` (91 KB), `stderr.log`, `core_api.log`, `test_*.py` (9 ad-hoc files), `patch_tools.js`, `req.py`, `modify_docker_settings.py`, `.DS_Store`, plus `brain_health/live_telemetry.json` containing session history with local paths. `.claude/worktrees/` carries three stale worktree copies of the codebase.

---

## Phases

### Phase 1 — Security & Hygiene (do first, ~1 day)
1. **Rotate the exposed Gemini API key** and remove it from `update_claude_config.py` (read from `.env` instead).
2. Add to `.gitignore` and purge from repo: `*.log`, `.DS_Store`, `brain_health/` runtime artifacts, `scratch/`, `scratch_bench/`, `.claude/worktrees/`.
3. Move ad-hoc root scripts (`test_mcp*.py`, `patch_tools.js`, `req.py`, etc.) into `scripts/dev/` or delete.
4. Consider `git filter-repo` if the key was ever pushed to a remote.

### Phase 2 — Configuration Decoupling (~2-3 days)
1. Eliminate every hardcoded path/host: all of section B reads from `KenbunSettings` (which already exists and is well-built) — no literal IPs, Tailscale names, ports, or `/Users/...` paths anywhere outside `.env`.
2. Move `MASTER_KEY_PATH` default from `~/.gemini/antigravity/keys/` to `~/.kenbun/keys/` with a one-time migration (same pattern as the existing DB migration).
3. Fix `.env.example`: retitle for Kenbun, correct `PROJECT_ROOT` example, remove kenbun-agent references.
4. Replace generated config scripts (`update_claude_config.py`) with a single `kenbun setup` CLI that detects the host machine and writes configs from templates.

### Phase 3 — IDE-Agnostic Interface (~3-5 days)
1. Split `"claude"` and `"antigravity"` into separate keys in `ide_context.py`; add explicit detection for each supported IDE rather than inferring from API-key presence (e.g., check `CLAUDECODE`, MCP client info from the `initialize` handshake — the MCP protocol sends `clientInfo.name`, which is the most reliable signal and removes guessing entirely).
2. Define a capability profile per IDE (has_own_llm, supports_streaming, max_tool_timeout) instead of the binary `_SELF_SUFFICIENT_IDES` set, so pipeline steps degrade gracefully per client.
3. Ship ready-made config templates per IDE: `configs/claude-code.json`, `configs/cursor.json` (`.cursor/mcp.json` format), `configs/windsurf.json`, `configs/vscode.json` (`.vscode/mcp.json`), `configs/antigravity.md` — all generated from one source of truth by the setup CLI.
4. Optionally expose the server over HTTP/SSE (it's already Dockerized) so IDEs that prefer remote MCP can connect without local Python.

### Phase 4 — Timeout & Performance Hardening (~2-3 days)
1. Enforce a per-step time budget inside orchestrate so no single MCP response exceeds ~50s regardless of client (Claude Desktop's limit is not user-tunable).
2. For long workflows, return a job ID immediately and add a `get_orchestrate_status` tool for polling — eliminates client-timeout risk entirely.
3. Make external dependencies (ChromaDB on remote PC, LM Studio, Gemini) fail fast with clear fallbacks when unreachable, so Kenbun works on a laptop with nothing but Ollama (the `.env.example` Option A path) — this is the real "any machine" test.

### Phase 5 — Documentation & Onboarding (~1-2 days)
1. Rewrite `docs/MCP_INTEGRATION.md` as a per-IDE guide (one section per IDE, Antigravity becomes just one of them).
2. Add a "Kenbun vs. kenbun-agent" disambiguation note to `README.md` and `KENBUN.md`.
3. Quickstart goal: clone → `cp .env.example .env` → `./install.sh` → paste generated config into your IDE → working in under 10 minutes, no Tailscale, no remote PC.
4. Verification: run the Phase 3 config templates against at least Claude Code and Cursor on a clean machine before calling it done.

---

## Priority Order
Phase 1 is urgent (exposed key). Phases 2→3 are the core generalization work and should be sequential. Phase 4 can run in parallel with Phase 3. Phase 5 last.
