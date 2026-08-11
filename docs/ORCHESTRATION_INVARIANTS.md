# Orchestration Invariants

Rules the orchestration layer must hold, and the incident behind each one.

These are not style preferences. Every rule here was broken in production, and in
every case the system reported success while doing the wrong thing. That is the
common thread: **Kenbun's characteristic failure is silent degradation, not
crashing.** A crash is cheap. An answer that is confidently about the wrong thing
costs hours and can reach a client.

Enforced by `core/tests/test_pipeline_contracts.py`, which runs in CI.

---

## 1. One tool registry

**`build_pipeline_tools()` in `orchestrator.py` is the single source of truth for
what a pipeline can call.** `orchestrate()` and `swarm()` must call it, never
build their own dict.

> **Incident (2026-08-11).** Four registries had drifted apart:
> `build_pipeline_tools` 35 tools, `orchestrate()` 24, `swarm()` 19,
> `server.py` inline-fallback 26. Every `kanban_*` tool was missing from the
> orchestrate path. A workflow step calling one received nothing and raised
> nothing — the step reported success having done no work.
>
> Root cause: `orchestrate` was **defined twice** in `orchestrator.py`. Python
> binds the later definition, so the earlier one — the one that had been
> correctly refactored to use `build_pipeline_tools` — was dead code. The
> refactor had been done properly and simply never took effect.

The `server.py` inline-fallback registry is allowed to *wrap* tools (injecting
the docs registry, Chroma host/port), so the callables differ by design. The
**names** must match, or a workflow behaves differently depending on whether
HTTP dispatch happened to succeed — the one difference you are least likely to
be watching for.

## 2. A function is defined once per module

A second `def` of the same name silently replaces the first. Ruff's `F811` does
**not** catch this when the earlier definition is referenced in between, which is
exactly the case that bit us twice (`orchestrate`, `_analyze_bug`). The AST check
in the contract tests covers what the linter cannot.

When two copies exist, expect the dead one to be the better implementation —
improvements land on whichever copy the author happened to open.

## 3. An unreachable `project_path` is an error, never a substitution

`POST /api/v1/orchestrate` returns **400 `project_path_unreachable`** and does
not dispatch.

> **Incident (2026-08-11).** The endpoint rewrote an absolute host path that
> doesn't exist in the container (e.g. a Mac path like
> `/Users/.../eko-veritas-prod`) to `"."` — which resolves to `/app`, Kenbun's
> **own repo**. Two jobs against a paid client repository came back as confident
> reviews of Kenbun itself. One produced a patch for `webhook/handler.py`, a
> Flask file present in neither project, inventing a `db.telemetry` table.

Reviewing the wrong codebase is strictly worse than reviewing none: the output is
indistinguishable from a real result.

To target a host path, make it visible to the container (mount or copy), pass the
source via `code_snippet`, or omit `project_path` to target the container's own
`PROJECT_ROOT` deliberately.

## 4. Loaders raise; they never return error strings

`scan_repo()` raises `FileNotFoundError` / `NotADirectoryError`. It used to
return `"❌ Path not found: ..."` as a normal return value.

Callers store a step's return value in pipeline state and hand it to a reviewer
as the repo map. **A model cannot distinguish an error message from content.** An
audit inspected the sentence describing the failure, found nothing objectionable
in it, and returned APPROVED.

Raising means the pipeline marks the step failed, never populates `repo_map`, and
downstream steps guarded by `skip_if: not s.get("repo_map")` correctly decline to
run. The guard rails already existed — they just needed a real failure to fire on.

Applies to any tool whose output becomes LLM input. If a failure can be rendered
as prose, it will eventually be read as data.

## 5. No verdict without evidence

`run_supervisor_audit()` returns **`INCONCLUSIVE`** when the proposal concerns
code but no reviewable source was supplied. It must never return `APPROVED`.

> **Incident (2026-08-11).** Handed an empty snippet, the adversarial court
> reported *"the prosecution identified no concrete flaws"* — true, because there
> was no code — and that rendered as **APPROVED**. Both the guardrail and the
> court signed off on a patch for a file that does not exist.
>
> Note the same root cause produced a correct **REJECTED** in the `code_review`
> pipeline, because that pipeline noticed the source was missing. Same bug,
> opposite verdicts. The approving one is the dangerous failure mode.

"No flaws found" and "nothing was inspected" must never collapse into the same
verdict. An approval nobody earned is worse than a crash.

The gate is deliberately conservative: a false negative costs one extra
`INCONCLUSIVE`; a false positive is an unearned approval. `_MIN_REVIEWABLE_CHARS`
is low (12) because `def hello(): print('world')` is 27 characters and is
perfectly valid code to audit — the gate detects *absence* of evidence, not
insufficiency of it.

## 6. One runtime for every client

**All MCP clients should use the same transport:**

```
ssh lg2025 docker exec -i portable_fastmcp python -m tools.infrastructure.server
```

> **Incident (2026-08-11).** Claude Code used the container; Antigravity's
> `~/.gemini/*/mcp_config.json` ran `core/tools/infrastructure/server.py`
> directly on the Mac. They were not the same system:
>
> | | Claude (container) | Antigravity (Mac) |
> |---|---|---|
> | Code | deployed build | uncommitted working tree |
> | Primary LLM | `100.91.110.91:11434` — **dead** | LM Studio, `qwen2.5-coder-14b` |
> | Host paths | invisible | resolve normally |
>
> Antigravity was pinned to a small local model; Claude's dead primary made it
> fall back to a much stronger one. **Neither was configured on purpose** — one
> was accidentally weak, the other accidentally good. That was the entire
> perceived quality gap.
>
> Running the Mac working tree also means Antigravity executes whatever is
> half-edited. An uncommitted `settings.audit` typo — an attribute that does not
> exist on `KenbunSettings` — crashed `consult_supervisor` for Antigravity while
> Claude, on the container, never saw it.

Keep the local path as an explicit dev mode you opt into. Never as a silent
fallback.

## 7. Config is validated where it is used

`PRIMARY_LLM_URL` pointed at a dead IP (`100.91.110.91`) for weeks while a
working Ollama sat at `localhost:11434` in the same container. Nothing checked,
so nothing reported it; the system silently fell back and kept answering.

A startup probe of the LLM endpoint, internal API and Chroma — logging at ERROR
when unreachable — would have caught it the same day.

---

## The pattern to watch for

Every incident above has the same shape:

| Trigger | What it silently did instead |
|---|---|
| `project_path` unreachable | reviewed Kenbun's own repo |
| HTTP dispatch failed | ran inline with a smaller toolset |
| `scan_repo` path missing | returned an error string as content |
| duplicate `orchestrate` | bound the worse implementation |
| audit given no source | returned APPROVED |
| primary LLM dead | fell back, never said so |

**When adding a fallback, ask what it will look like when it fires and nobody is
watching.** If the answer is "the same as success," it is not a fallback — it is
a silent failure with extra steps. Make it loud, or make it an error.
