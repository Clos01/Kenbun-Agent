# Kenbun-Agent Engineering Roadmap — Server Reliability & Local Model Quality

> Created 2026-06-12. Phasing validated by the `orchestrate("research_implement")`
> pipeline (Gemini research + Executive Supervisor sign-off: APPROVED).
> Ordering principle: secure what exists → make boot bulletproof → verify and
> harden LAN access → make model quality measurable before changing models.

---

## Phase 0 — Secure In-Flight Work *(do first; everything else builds on it)*

The working tree carries ~700 uncommitted lines plus new networking fixes.
Nothing else should land on top of unprotected work.

| # | Task | Notes |
|---|------|-------|
| 0.1 | **Import smoke test** — pytest that imports every module under `core/` | Catches circular imports (like the `orchestrator` ↔ `router_logic` cycle fixed 2026-06-12) before they reach a running server. Land this *before* 0.2 — it is the safety net for the big diff. |
| 0.2 | **Commit in-flight changes in logical chunks** | `core/tools/cli/engine.py` + `core/tools/utils/llm_router.py` (streaming + native tool-calls), the Docker/LAN networking fixes (`docker-compose.yml`, `.env.example`, `scripts/setup_lan.sh`, docs), the orchestrator circular-import fix, and a decision on untracked `AI_POLICY.md` / `DILIGENCE.md` / `core/tools/memory/schemas.py`. |

**Exit criteria:** `pytest` green including the import test; `git status` clean.

---

## Phase 1 — Server Boot Reliability *(finishes the "works on servers" story)*

| # | Task | Notes |
|---|------|-------|
| 1.1 | **Decouple GPU reservation** | `docker-compose.override.yml` unconditionally reserves an NVIDIA GPU and Compose auto-merges it, so CPU-only servers fail with "could not select device driver nvidia". Move the reservation into `docker-compose.gpu.yml` (opt-in via `-f` or a `gpu` profile) and update README/install scripts. |
| 1.2 | **Healthchecks + startup ordering** | Add `healthcheck:` to chromadb, ollama_server, fastmcp_server, dashboard; convert `depends_on` to `condition: service_healthy`. Consider `restart: unless-stopped` instead of `always`. |

**Exit criteria:** cold `docker compose up -d` succeeds on a CPU-only host; after
a host reboot all services come up healthy with no manual intervention.

**Risk:** healthcheck commands must exist inside the images (chroma image is
minimal — may need `wget`-based or TCP checks).

---

## Phase 2 — LAN Access Verified & Hardened

| # | Task | Notes |
|---|------|-------|
| 2.1 | **End-to-end test of `scripts/setup_lan.sh` on a real Linux server** | Verify LAN-IP detection, subnet-collision detection, `.env` rewrite, stack recreation, UFW hint, and dashboard/API reachability from a second device. |
| 2.2 | **PowerShell twin (`setup_lan.ps1`)** | Windows parity (`install.ps1` implies Windows users). Same flow: detect IP, write `.env`, recreate stack, print URLs + firewall hint. |
| 2.3 | **LAN security hardening** | With `BIND_IP=0.0.0.0` the FastMCP API and Dozzle (Docker-socket access) are open to the whole LAN unauthenticated. Add a bearer/API token to FastMCP (generated into `.env` by setup_lan), enable Dozzle basic auth, and document the threat model in `docs/SECURITY.md`. |

**Exit criteria:** a second LAN device can use the dashboard + API with the
token; unauthenticated requests are rejected; documented in `VM_NETWORKING.md`.

**Dependency:** builds on Phase 1 (no point testing LAN boot flows that race).

---

## Phase 3 — Local Model Quality *(measure first, then change)*

Strict internal ordering: 3.1 → 3.2 → 3.3.

| # | Task | Notes |
|---|------|-------|
| 3.1 | **Fix `detect_model_tier`** (`core/tools/infrastructure/ai_gateway.py`) | String patterns miss `:1.7b`, `:0.6b`, `:3b`, so those models skip the decoupled planner-executor anti-hallucination path. Parse the parameter count numerically (`<value>b` suffix → float; tier nano if ≤ 3). Prerequisite for 3.2 — the benchmark must route models to the correct pipeline. |
| 3.2 | **Nano-model hallucination regression benchmark** (`core/benchmarks/`) | Fixed prompt set run against the local model, scored for invented CLI syntax, malformed/XML-hallucinated tool calls, and schema violations. Output a score per model+prompt-version so prompt tweaks (cf. the last five `fix(ai)` commits) become measurable instead of whack-a-mole. |
| 3.3 | **Refresh default `ollama_init` models** | `gemma2:2b` + `deepseek-r1:1.5b` are dated; candidates: Qwen3 1.7b/4b (better tool calling, similar VRAM). Switch defaults **only after** 3.2 shows a measured win; keep old defaults overridable via `OLLAMA_PULL_MODELS`. |

**Exit criteria:** benchmark runs in CI/manually with a single command; new
default models beat old defaults on the benchmark; tier detection covered by
unit tests.

**Risk:** benchmark needs a running Ollama — make it skippable when the
service is absent so it doesn't break CI.

---

## Suggested execution order (flat)

1. 0.1 import smoke test
2. 0.2 commit in-flight work
3. 1.1 GPU override decoupling
4. 1.2 healthchecks
5. 3.1 tier detection fix *(small, independent — can interleave anytime after 0.2)*
6. 2.1 / 2.2 LAN e2e + PowerShell twin
7. 2.3 LAN security hardening
8. 3.2 hallucination benchmark
9. 3.3 default model refresh
