# DeepSeek Harness / Cordis — study & adoption plan

**Sources**
- Repo: `deepseek-ai/deepseek-harness` @ `0a53fb5` — cloned to `~/Dev/deepseek-harness`, synced to `lg2025:/repos/deepseek-harness` (scan map: 3,385 `.ts` files / 14,853 symbols; **258 packages**).
- Paper: *A Programming Paradigm for Spatiotemporal Composability* (Shi, Zhang, Cui — Peking University / DeepSeek-AI), 92 pp. `~/Downloads/2608.25512v1.pdf`.
- Docs: <https://deepseek-harness.github.io/deepseek-harness/en/guide/quickstart>, `deepseek-harness/docs/architecture.md`, `AGENTS.md`.

---

## 1. What it actually is

**Cordis** is a *meta-framework of spatiotemporal composability* — it prescribes no domain, it only supplies "load / unload / reconfigure a component at runtime, safely." Two formal mechanisms:

| Dimension | Mechanism | One-line |
|---|---|---|
| **Temporal** (revert on removal) | **revertible effects** | every context mutation goes through `ctx.effect(cb)`; the callback yields an inverse the runtime holds; `dispose()` runs all inverses **LIFO**. Unloading a parent cascades to children. |
| **Spatial** (declare/resolve deps) | **reactive coeffects** | a component declares the keys it needs (`inject`); `ctx.set(key,v)` (itself an effect) calls `notify()` → `refresh()` re-evaluates every fiber whose `inject` contains that key → activates / deactivates it. Providers appearing/disappearing drive dependents automatically. |

Unified into the **context paradigm**: one `ctx` tree mediates every effect and coeffect, so distinct components interleave without disturbing each other. Component lifecycle is an **inertial state machine** (LOADING→ACTIVE, UNLOADING→INACTIVE; a transition runs to completion before responding to a new target; FAILED carries an error and withholds retry). The **loader** adds `cordis.yml` declarative config + reconciliation + **hot module replacement** (revise a running fiber = retire → remove children-first → reinsert at same name with new config; dependents follow).

**DeepSeek Harness (`dsh`)** is an *all-plugin* agent harness on Cordis. "There is no privileged core to patch." Every part — model adapter, tool registry, session log, **the agent loop itself** — is a plugin, replaceable from config.

- **258 packages** under `packages/<group>/<pkg>`, each `@deepseek-ai/dsh-<name>`, ESM, `strict`, **per-file 100% coverage gate**.
- **Capability seam** = 3 roles, always all three: **Service Definition** (interface) / **Service Provider** (impl) / **Consumer** (usually a model-facing tool). "One provider swap changes the whole product" — point fs + subprocess at a remote sandbox and Bash + PTY + LSP move with them, no forks.
- **Profiles / bundles**: a running `dsh` is a plugin tree composed at boot from ordered layers. `web`, `headless`, `sdk`, `sdk-minimal`, `acp` profiles; `dsh-base` bundle is the shared first layer.
- **Turn flow** is an event pipeline: `turn/start → agent/pre-step (waterfall) → step/start → agent/request → llm/stream → assistant/message → tools/pre-execute → tools/execute → tools/post-execute → step/end → agent/turn-stopping → turn/end`. `turn/*`, `step/*`, `user/message`, `assistant/*`, `tool/*` are **durable session events**; the rest are live extension points.
- **Model-visible ⟺ logged**: anything reaching a model request must be reconstructable from the session log; a runtime invariant asserts it. New model-visible input ⇒ new `SessionEventMap` event.
- Notable packages: `core/{agent,agent-loop,session,system-prompt,tools,scope}`, `subagent/{subagent,subagent-claude-code,subagent-codex,subagent-dsh-sdk,subagent-fork-in-process,…}`, `hooks/{hooks-claude-code,hooks-codex,hook-protocol}`, `self-modification` (agent inspects/mounts its own plugins), `sandbox/*` + native landlock addon, `session/*` (jsonl + sqlite persistence, projection, otel telemetry, LLM titles), `workflow/*`, `mcp/mcp-client`, `typert/*` (type-graph generator + runtime registry).

---

## 2. Kenbun today vs. this

| Concern | DeepSeek Harness / Cordis | Kenbun (current) |
|---|---|---|
| Language / module system | TypeScript, ESM, `strict` | Python |
| Composition | Cordis plugins; `ctx.effect` revertible; reactive coeffects; HMR; `cordis.yml` | static imports; `@sovereign_tool` decorator; `SovereignRegistry` = global dict, `register_tool()` overwrites, **no disposer, no unload** — restart to change anything |
| Capability structure | Definition / Provider / Consumer seam × 258 pkgs | monolithic `core/tools/<group>/*.py` modules |
| Agent loop | a plugin (`core/agent-loop`), replaceable | `orchestrator.py` + `agent-loop` code path; pipelines registered in a dict |
| Sessions | append-only `SessionEvent` log = single source of model context; `deriveMessages()`; projection seam; versioned | `sessions_db.py`, `chat_history_manager.py`; no "logged ⟺ model-visible" invariant |
| Subagents | one `subagent` seam, pluggable drivers (claude-code / codex / dsh-sdk / in-process / fork) | **3 overlapping paths**: `claude_code_agent.py`, `delegate_task`, orchestrator pipelines |
| Sandbox / exec | fs + subprocess providers share one execution world; `ctx.sandbox` seam; native landlock | ad-hoc: `safe_exec`, `e2b_runner`, `run_code_safely`, `shell_sentinel`, `wasm_interpreter` |
| Hooks | `hooks-claude-code` / `hooks-codex` wire-protocol **bridges** (bidirectional) | Claude Code hooks (advisory, one-way) + `sovereign_decorators` |
| Config | declarative `cordis.yml`, reconciled + hot-reloaded | `.env`, `config.py`, hardcoded pipeline registry |
| Tests | per-file 100% coverage, keyless recorded-session snapshots, dual-SDK projection | pytest + benchmarks |

**Verdict:** Kenbun is exactly the "coarse-grained workaround" the paper critiques — self-modification / new tools require a process restart, and dependencies between subsystems are implicit. DSH is the principled version of what Kenbun's `agent_self_improve` + `awareness_engine` are reaching for.

---

## 3. Phased adoption plan

Ordered so each phase ships value on its own and de-risks the next. Phases 1–4 stay in **Python** (no framework switch); Phase 5 is the optional endgame. Tracked on Planka Main Board as `[DSH-00]`…`[DSH-06]`.

### Progress (2026-08-30 — all on Gitea `main`, deployed to lg2025)

| Phase | State | Landed as |
|---|---|---|
| DSH-01 revertible registry | ✅ done | `8297614` |
| DSH-02 shell seam | ✅ slice 1 (`26fa15d`); slice 2 (17 `safe_run` callers) open |
| DSH-03 session log | ✅ slice 1 (`59f5449`); slice 2 (wire into the *live* LLM path) open — riskiest |
| DSH-04 subagent seam | ✅ slices 1+2 (`0df52e6`, `00e8cfa`) — 429 fallback live in `delegate_task` |
| DSH-05 hot mount | ✅ slice 1 (`ca6858f`) + follow-up (`ad68569`); slice 2 (source→callable sandbox) open |
| **DSH-06 no-SPOF resolvers** | 🔄 slices 1-4 + Observatory panel + `CapabilityResolver` extraction | `f292e09` `6cd3785` `15ec53f` `54a19f9` `becfe22` `99eb154` `96debee` |

**DSH-06** = "compose with configuration" from the DSH dev-preview blurb, applied
to provider choice: `core/tools/strategy/{resolver,capability_resolver,decomposition,
senior_reviewer,reasoning}.py`. Each capability gets a health-aware Resolver
(demote-on-fail + cooldown + auto-recover), an ordered `KENBUN_<CAP>_PROVIDERS`
allowlist, and a cross-process failover trail the Observatory "Resilience" tab
renders. Remaining s3b (audit-pass endpoint), s5 (memory / vector store).

### DSH-00 — Study & decision spike *(1 wk, no code)*
Read the paper's §3–5 formal model + `cordis-primer.md` + capability-seam docs. Run `dsh --profile headless "task"` locally (needs `DEEPSEEK_API_KEY`), `dsh --profile web --dump-config`, trace one turn through the event flow with `--dump-config` + session log. **Deliverable:** decision memo — (a) selective pattern adoption in Python, (b) TS rewrite of `core/` only, or (c) full Cordis rebuild — with a recommendation and a cut line.

### DSH-01 — Revertible-effect registry *(2 wk, Python)*
Make `SovereignRegistry.register_tool()` / `register_pipeline()` return a disposer; track a per-scope inverse stack; add `registry.unload(scope)` running inverses LIFO. `@sovereign_tool` participates. **DoD:** a tool can be registered and fully unregistered at runtime (schema drops from prompt assembly, MCP list updates) with no restart; a test proves the inverse restores exact prior state. Target: `core/tools/registry.py`, `core/tools/infrastructure/sovereign_decorators.py`, `core/tools/infrastructure/server.py`.

### DSH-02 — First capability seams *(2–3 wk, Python)*
Refactor `shell`/execution, `fs`, and `web` into Definition / Provider / Consumer. Providers: `shell` → {local `safe_exec`, `e2b`, sandbox}; `fs` → {local, e2b}; `web` → {existing `web_tools` search/fetch}. Consumers are the model-facing tools, unchanged externally. **DoD:** swapping the `shell` provider to `e2b` moves every shell tool with zero tool-code changes; documented in `docs/`. Target: `core/tools/execution/*`, `core/tools/sensory/web_tools.py`, `core/tools/utils/safe_exec.py`.

### DSH-03 — Session log as source of truth *(2 wk, Python)*
Introduce an append-only `SessionEvent` log; `derive_messages()` projects model history from it; add the **"model-visible ⟺ logged"** runtime assert (any string reaching an LLM call must trace to a logged event). Migrate `chat_history_manager` + `sessions_db` to read from the log. **DoD:** fork / resume / transcript all derive from one stream; the assert fires in tests on an un-logged injection. Target: `core/tools/utils/sessions_db.py`, `core/tools/utils/chat_history_manager.py`, `core/tools/memory/*`.

### DSH-04 — Unified subagent seam *(2 wk, Python)*
One `Subagent` interface; drivers: `claude-code` (the new `scripts/kenbun` CLI / `claude_code_agent.py`), `codex`, `in-process` (current orchestrator), `dsh-sdk` (stretch). `delegate_task` + `orchestrate` become consumers of it. **DoD:** the 3 current delegation paths collapse to one interface + N providers; picking a driver is one config field. Fixes the `delegate_task` 429 fallback story. Target: `core/tools/execution/claude_code_agent.py`, `core/tools/strategy/delegation_tool.py`, `core/tools/infrastructure/orchestrator.py`.

### DSH-05 — Hooks bridge + self-modification loop *(1–2 wk, Python)*
Port `hooks/hook-protocol` wire format; make Kenbun a structured hook target for Claude Code **and** expose its own hook events. Wire `agent_self_improve` / `awareness_engine` to use the DSH-01 unload/reload path instead of a restart. **DoD:** the swarm can mount a freshly-generated tool plugin into a *running* process and revert it if a guard fails. Target: `core/dev/self_evolution/awareness_engine.py`, `core/tools/infrastructure/pipelines/self_improve.py`, `.claude/hooks/`.

### DSH-05b *(optional / large)* — TS core on Cordis
Only if DSH-00 picks (b) or (c). Rebuild `core/` (agent, agent-loop, session, system-prompt, tools) as Cordis plugins in TypeScript; keep Python tools reachable via an MCP or subprocess provider during migration. This is "build kenbun on Cordis" for real — scope it as its own project after 00–05 land.

---

## 4. External-name caution

`deepseek-harness` legitimately contains "deepseek" everywhere (`@deepseek-ai/dsh-*`, `llm-deepseek`, `DEEPSEEK_API_KEY`). When porting patterns, do **not** carry DeepSeek branding into Kenbun; adopt the *mechanism*, rename to Kenbun's vocabulary.
