# Kenbun Ghost-Bug Hunting Plan

A sectioning of the codebase into zones where latent (ghost) bugs are most likely to live, plus the patterns to look for and the probes that surface them.

A "ghost bug" here = a defect that doesn't raise at import or unit-test time, but only fires under a specific workflow, message size, retry path, or environment. They tend to cluster around contract boundaries: kwarg signatures, registry lookups, dispatch fallbacks, transport timeouts, async state, and persistence migrations.

---

## Zone 1 — Pipeline ↔ Tool contract surface (HIGHEST PRIORITY)

**Scope:** `core/tools/infrastructure/pipelines/*.py` + `core/tools/infrastructure/server.py::_build_orchestrate_registry` + the underlying tool functions (`tools/infrastructure/orchestrator.py`, `tools/audit/*.py`).

**Why ghosts live here:** Pipelines build a list of steps where each step has an `input` lambda that constructs a dict, and the step's `tool` is looked up by string key from the registry. Python keyword-arg mismatches between what the lambda passes and what the tool function actually accepts are silent until the step runs.

**Confirmed ghost (caught during this audit):**
- `pipelines/code_review.py:56` passes `tech_key=` into the `analyze_bug` slot, but the registry maps `analyze_bug` to `_analyze_bug(task, file_path, code_snippet, project_path, past_fixes)` (`orchestrator.py:762`). There is no `tech_key` parameter — so the `analyze_review_request` step crashes every time it isn't skipped. The current `skip_if` (`bool(s.get("code_snippet") or s.get("repo_map"))`) hides it for most calls.

**Classes to hunt:**
1. **Signature drift** — lambda passes a kwarg the tool doesn't accept (the bug above).
2. **Silent skip masking** — `skip_if` returns true in the happy path, so the broken step looks "fine" until someone calls without `code_snippet` / `repo_map`.
3. **Stale registry mapping** — `_build_orchestrate_registry` aliases `analyze_bug → _analyze_bug` even where pipelines expect a richer "analyze_review_request" tool. Same key, divergent semantics.
4. **Lambda capture footguns** — `lambda s: {...}` inside a for-loop captures the loop variable by reference (none today, but the pattern is fragile).

**Probes:**
- Static: for every pipeline step, diff the kwargs in `input(s)` against `inspect.signature(tool)`. Already a 10-line script — run it against all 5 pipelines.
- Dynamic: call each `workflow` with `code_snippet=""` and `repo_map=""` so every step actually executes; surface every TypeError.
- Add a registry conformance test: `test_pipeline_kwargs_match_registry()` in `core/tests/`.

---

## Zone 2 — Dispatch / inline-fallback transport

**Scope:** `core/tools/infrastructure/server.py::orchestrate` + `_dispatch_orchestrate_http` + `_execute_orchestration` + `api_server.py`.

**Why ghosts live here:** The `orchestrate` MCP tool has a *transparent fallback*: if the FastAPI dispatch fails (auth, network, 401/403, timeout), it silently re-runs inline and just prefixes a notice. That hides three things at once: the dispatch failure, the original token state, and any state difference between async-server execution and in-process execution.

**Classes to hunt:**
1. **Token-cache desync** — `_get_config_token()` caches the FastAPI server's token; if the server rotates and the MCP doesn't refresh, callers see "inline fallback" forever and never realize async dispatch is dead. (The code has retry logic for 401/403, but other failure modes degrade silently.)
2. **MCP request timeout vs. workflow duration** — heavy workflows must dispatch async; if a workflow not in `HEAVY_WORKFLOWS` slips through, it'll hit the 60s MCP timeout (already happened in this session with `research_implement` + `fast=true`).
3. **Inline path drift** — the inline execution path and the FastAPI path may have different working dirs, env vars, or imports, so a workflow that "works inline" can fail on the real server.
4. **Result shape divergence** — inline returns a string; async returns a job ID. Anything downstream parsing the result must handle both. (Note the prepended "Persistent-server dispatch unavailable" string changes structure.)

**Probes:**
- Force a token mismatch (rotate the secret file mid-test) and check that the retry actually succeeds.
- Run each workflow twice: once async, once `wait=True`; diff the results — any divergence is a ghost.
- Audit `HEAVY_WORKFLOWS` membership against actual avg runtime.
- Surface fallback events to the dashboard so the user notices regression instead of getting "successful inline" output.

---

## Zone 3 — LLM router & token governor

**Scope:** `core/tools/utils/llm_router.py`, `tools/utils/llm_utils.py`, `tools/strategy/token_governor.py`, `tools/strategy/hme_router.py`, `tools/strategy/decision_logic.py`.

**Why ghosts live here:** Routing logic with budget gates and model fallbacks tends to have asymmetric retry paths. Bugs hide where the "happy" branch is well-exercised but the "exhausted budget", "model 503", or "JSON parse failed" branches are not.

**Classes to hunt:**
1. **Budget off-by-one** — token governor decrements before the call but the call may charge more (thinking tokens, tool tokens). Net effect: budget reports drift over a session.
2. **Default-model fall-through** — when the router gets an unrecognized `tech_key`, does it raise, default to a free model, or silently route to the most expensive model?
3. **JSON parse silent skips** — `_clean_json_response` followed by `json.loads` inside a try/except that returns `""` or `{}` means the caller gets a "success" with empty data and proceeds.
4. **Concurrent governor state** — if the governor uses a module-level dict and pipelines run in parallel (`parallel_manager.py`), counters race.

**Probes:**
- Replay a session's tool log against the governor and assert reported budget matches actual API spend.
- Mock each LLM client to raise for one call and check that retries vs. fallbacks behave as documented.
- Stress the governor with `pytest -p no:cacheprovider -k token_governor` while spawning 10 parallel `orchestrate` calls.

---

## Zone 4 — Memory / persistence layer (Honcho, Chroma, Postgres, sqlite)

**Scope:** `core/tools/memory/*.py`, `core/brain_health/antigravity_intelligence.db`, `core/tools/utils/error_memory.py`, `core/external/honcho/`.

**Why ghosts live here:** Migrations are noted in `POST_MORTEM.md` and `scripts/migrate_to_*.py`; sqlite + chroma + honcho + postgres all coexist. The bridge code that decides which backend to use is a classic ghost-bug habitat.

**Classes to hunt:**
1. **Dual-write / dual-read drift** — `knowledge_manager` reads from honcho and chromadb; if writes go to only one, queries miss.
2. **Schema drift across `weights.json` / `weights.json.migrated`** — two artifacts coexisting at `core/` is a tell that a migration may be half-applied.
3. **Connection pooling under fork** — `postgres_client.py` constructs a conn string per call; long-running daemon (`services/swarm_daemon.py`) can leak.
4. **Embedding dimension drift** — different models produce different vector sizes; old vectors in the collection break similarity search silently (queries return junk, not errors).

**Probes:**
- Diff `weights.json` vs `weights.json.migrated` — anything still referencing the old file?
- Boot the daemon with no honcho and confirm degraded mode is announced, not silent.
- Run `scratch_check_chroma.py` and `core/tests/test_brain_health.py` against a fresh and a stale store.
- Compare embedding dimensions across `ingest_*` callers.

---

## Zone 5 — Async / background daemon state

**Scope:** `core/services/swarm_daemon.py`, `core/tools/infrastructure/orchestrator.py` (job runner), `tools/infrastructure/parallel_manager.py`, `tools/infrastructure/topology_manager.py`, `tools/utils/io_lock.py`.

**Why ghosts live here:** Long-running daemons + job IDs + on-disk locks. The `brain_health/locks/` directory exists, which means the system already takes file locks — and stale locks are a perennial ghost.

**Classes to hunt:**
1. **Stale lock files** — process killed mid-job leaves a lock; next run blocks forever or, worse, ignores the lock and double-writes.
2. **Job ID leakage** — `orchestrate_status` returns "still running" — confirm there's a sweeper for orphaned jobs and a TTL.
3. **`_run_async_safely` thread vs. event-loop issues** — wrapping `asyncio.run` from inside an already-running loop (FastAPI) is a known footgun; check the implementation.
4. **Logging interleaving** — `core_api.log`, `dashboard.log`, `mcp_debug.log`, `brain_health/swarm_live.log` — concurrent writers, no rotation → silent log truncation.

**Probes:**
- Kill the daemon mid-orchestrate and inspect lock files in `brain_health/locks/`.
- List all jobs older than the longest expected workflow runtime; if any exist, sweeper is broken.
- Grep for `asyncio.run(` inside any function called from async context.

---

## Zone 6 — MCP tool surface (the public API)

**Scope:** `core/tools/infrastructure/server.py` (everything decorated `@sovereign_tool`), plus how the dashboard consumes them.

**Why ghosts live here:** The MCP `@sovereign_tool` decorator registers handlers that go through FastMCP. The decorator order, the docstring (which becomes the tool description shown to clients), and the parameter defaults are all part of the public contract.

**Classes to hunt:**
1. **Docstring vs. signature drift** — the docstring promises behavior the implementation doesn't deliver. Already visible in `orchestrate`'s very long docstring.
2. **`None`-default mutable args** — common Python footgun; grep for `def foo(x={})`.
3. **`mcp_safe_print` not used consistently** — anything that `print`s to stdout corrupts the MCP stdio channel and crashes the client. Grep every module imported by `server.py`.
4. **Tools without input validation** — any tool taking a path and `open()`ing it without the `_local_view_file` traversal guard is a security ghost.

**Probes:**
- Generate a tool manifest from `inspect.signature` and diff against the JSON-Schema served by FastMCP.
- `grep -rn 'print(' core/tools/` and ensure every one is `mcp_safe_print` or behind a logger.
- Path-traversal fuzz: feed `../../../etc/passwd` to every tool taking a path arg.

---

## Zone 7 — Dashboard ↔ backend wire

**Scope:** `dashboard/src/app/api_proxy/`, `dashboard/src/lib/config.ts`, `dashboard/src/lib/tools.ts`, the routers in `core/tools/infrastructure/routers/*.py`.

**Why ghosts live here:** TypeScript types declared in `lib/tools.ts` are not actually checked against the Python router responses. The contract is implicit.

**Classes to hunt:**
1. **TS type vs. router payload mismatch** — `routers/legacy.py` is 519 lines named "legacy" — exactly the file that drifts from the dashboard's current expectations.
2. **CORS / auth header forwarding** — the `api_proxy` middleware likely strips or fails to forward something.
3. **Loading-state ghosts** — async UI that shows "loading" forever when the backend returns 4xx; check error boundaries on every fetch.
4. **WebSocket reconnect** — telemetry/observatory pages probably stream; reconnect logic is classic ghost territory.

**Probes:**
- Boot dashboard pointed at a backend with one router intentionally broken; record which pages spin forever vs. show an error.
- Generate an OpenAPI schema from FastAPI and run a TS codegen against it — any diff is a ghost.

---

## Zone 8 — Scripts / one-off migrations

**Scope:** `scripts/fix_all*.py`, `scripts/audit_*.py`, `scripts/migrate_to_*.py`, `scripts/patch_boot*.py`, root-level `scratch_check_chroma.py`, `show_active_settings.py`.

**Why ghosts live here:** "fix_all", "fix_all_v2", "fix_clean" — three near-duplicate scripts is a code smell. Migration scripts that "ran once" often leave the codebase referencing the post-migration shape while one forgotten branch still imports the pre-migration name.

**Classes to hunt:**
1. **Dead imports in `__init__.py`** — easy to find with `python -c "import core.tools"` and watching for warnings.
2. **Migration idempotency** — does `migrate_to_postgres.py` no-op cleanly if rerun, or duplicate rows?
3. **`patch_tools.js` + `check_tools.js`** at repo root — JS in a Python project is suspicious. Confirm they're still wired to anything.

**Probes:**
- `python -W error -c "import core; import dashboard"` from a clean venv.
- Grep root for `.js` files and trace who calls them.
- Run each migration twice in a row and diff the DB.

---

## Zone 9 — Test gaps

**Scope:** `core/tests/`.

There are ~30 test files, but no `test_pipelines.py`, no `test_orchestrate_dispatch.py`, no `test_registry_consistency.py`. The exact zones with the most ghosts are the least tested.

**Action:** add three small test modules:
- `test_pipeline_contracts.py` — for every pipeline, for every step, assert kwargs ⊆ `inspect.signature(tool).parameters`.
- `test_orchestrate_dispatch.py` — token rotation, server-down, timeout each force the documented path.
- `test_registry_consistency.py` — every pipeline references only registered tools; every registered tool is reachable.

---

## Quick-win checklist (do these first)

1. Fix `pipelines/code_review.py:56` — drop `tech_key` or change `_analyze_bug` to accept `**kwargs` (the registry already does this for `review_code_with_gemini`).
2. Add the pipeline-contract test (zone 9) — would have caught #1 at CI time.
3. Surface the "inline fallback" event to the dashboard so silent transport failures stop hiding.
4. Audit `weights.json` vs `weights.json.migrated` and remove the loser.
5. Replace any non-`mcp_safe_print` `print()` in modules loaded by `server.py`.
