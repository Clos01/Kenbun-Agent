# Composability — the software-engineering ideas behind the DeepSeek-Harness work

> Written to be read in small pieces. Each part is one idea. Stop whenever, pick up
> at the next `##`. The **bold line** in each part is the whole point of that part.

---

## Part 0 — What DeepSeek Harness actually is (the north star)

DeepSeek Harness (dev preview, source-included) has one design rule:

> **Everything is a plugin.** Models, tools, skills, sessions, sandboxes,
> storage, loops, scheduling, and even the UI are all plugins. You select, swap,
> or extend any capability **in configuration**, without touching the source.

It runs on the **Cordis kernel**, whose whole job is "mount this plugin,
unmount that one, keep their dependencies straight" — at runtime.

Two consequences worth copying:

1. **Compose with configuration.** A capability's provider is a config choice,
   re-read at runtime — not a hardcoded `import`.
2. **Every run is traceable.** One append-only session log holds *everything the
   model saw*: system prompts, reasoning, tool calls + results, subagent
   scheduling, every context injection. Resume / fork / search / replay all read
   that one event stream.

Kenbun can't switch to Cordis (it's Python, DSH is TypeScript). The DSH-01…06
work is **the same ideas, rebuilt in Kenbun's own vocabulary** — see the
scoreboard in Part 7 for how each DSH slice maps to a DeepSeek-Harness idea.

---

## TL;DR

- **Composition** = how the parts of software connect.
- Old way (**static**): connections are fixed. Change one part → restart everything.
- New way (**dynamic**): swap parts while it runs, and undo the swap if it breaks.
- DeepSeek Harness's version: **everything is a plugin**, composed by
  configuration, on the Cordis kernel (Part 0).
- Two hard problems: **clean removal** (undo everything a part did) and
  **who-needs-whom** (parts that depend on each other).
- What Kenbun now has: **the undo button** (DSH‑01), **the 3‑piece capability**
  (DSH‑02/04), **live mount + lifecycle hooks** (DSH‑05), **one honest record of
  what the model saw** (DSH‑03), and **health-aware provider resolution**
  (DSH‑06 — no single point of failure). DSH‑01…06 are all landed and deployed.
- **Your insight:** relying on *one* Gemini key / *one* LLM / *one* of anything is
  the **same mistake** as static composition — a single fixed choice in a
  load‑bearing spot. Part 6 develops it; DSH‑06 (Part 7) is the fix, now landed.

---

## Part 1 — The one idea: composition

Software is parts connected into a bigger thing. **"Composition" is just the word
for how the parts connect.**

```python
from tools.utils.safe_exec import safe_run   # a connection, decided now
```

That import is a *static* connection — frozen when you write the code.

---

## Part 2 — Static vs dynamic

| | Static composition | Dynamic composition |
|---|---|---|
| When it's decided | you write / compile the code | while the program runs |
| Change a part | edit code, **restart** | swap it live |
| Example | `import`, function calls | browser extensions, VS Code plugins, **an agent editing its own tools** |
| State when you change | **lost** (restart) | kept |

**Kenbun this morning was 100% static: to add a tool, you restarted the swarm and
lost everything in memory.**

---

## Part 3 — The two hard problems of dynamic composition

### 3a. Clean removal ("temporal")

A part, while it ran, *grabbed things*: opened a Honcho connection, started a
sync timer, put itself in a registry. **Deleting its code doesn't release any of
that** — the timer still fires, the connection stays open, pointing at dead code.

Analogy: the **undo button**, or a database `ROLLBACK`. Put the world back exactly
how it was.

### 3b. Who-needs-whom ("spatial")

`hivemind_tools` needs Honcho. If Honcho blips for 20 seconds, `hivemind_tools`
should switch **off** cleanly and switch **on** when it's back — not throw an
exception mid-task.

Analogy: a **light switch wired to the mains**. Power cut → lights off, no sparks.

**Effects are what a part *changes*. Coeffects are what a part *needs*. Problem 3a
is about effects; problem 3b is about coeffects.**

---

## Part 4 — The undo button (DSH‑01, shipped)

New rule: **whenever a part grabs something, it hands back a tiny function that
lets go of that exact thing.** The runtime keeps a stack of them. Remove the part
→ run the stack backwards (newest undone first).

In Kenbun now:

```python
disposer = registry.register_tool(entry)   # returns an undo
disposer()                                  # tool gone — from the registry AND the live MCP list, no restart
```

That one change is what everything else is built on.

---

## Part 5 — The 3‑piece capability ("seam") (DSH‑02, DSH‑04, shipped)

Every capability is split into three parts that can change independently:

| Piece | Job | Shell example | Subagent example |
|---|---|---|---|
| **Definition** | the interface | "a shell runs a command → output + exit code" | "run a task → result" |
| **Provider** | one implementation | `local` / `e2b` / sandbox | in‑process swarm / `claude` CLI / Codex |
| **Consumer** | uses it | the `bash` tool | `delegate_task` |

**Swap the Provider and everything downstream moves for free.** Point the shell +
filesystem providers at a sandbox → every shell/file/LSP tool is sandboxed, zero
tool changes.

---

## Part 6 — YOUR INSIGHT (this is the important part)

You said it about the Gemini 429, but it's bigger than Gemini:

> "we shouldn't have to rely on one api key or llm router or one single thing"

**Naming it: a capability with exactly one provider is *static composition wearing
a different hat*.** It's a single fixed choice welded into a load‑bearing spot.
When it fails, you don't restart — you're just *down*, with no move.

The fix is the **same shape** as the fix for static composition:

| | The trap | The fix |
|---|---|---|
| Static composition | one fixed *wiring*; change = restart | runtime‑swappable components (DSH‑01) |
| Single provider | one fixed *provider*; failure = dead | many providers + a resolver that **demotes** a failed one instead of stopping |

In the Cordis paper's words, this is **reactive coeffects applied to provider
choice**. "I need an LLM" is a *coeffect* (a requirement). Right now Kenbun
answers it at **code‑write time**: the answer is hardcoded "Gemini". It should be
answered at **call time**, against *the set of providers that are healthy right
now*, and re‑answered the moment that set changes.

**The pattern already exists in Kenbun — DSH‑04's `subagent.run(..., fallback=True)`.**
When the in‑process swarm 429s, the seam walks to the next provider. That is the
template. It needs to be true of *every* capability, not just subagents.

### The rule to carry forward

> **No capability Kenbun depends on gets exactly one provider.** Each is a seam
> with 2+ providers and a health‑aware resolver. A provider going down *demotes*
> it; the capability keeps working on the next one. Single points of failure are
> a design bug, the same class of bug as "restart to change anything".

---

## Part 7 — What we actually built (scoreboard)

| | What it is | DeepSeek-Harness idea it mirrors | Status |
|---|---|---|---|
| **DSH‑01** | `register_tool` returns an undo; add/remove a tool live | Cordis plugin **unmount** | ✅ `main` |
| **DSH‑02** | shell capability seam (local / e2b providers) | tools + sandboxes **as plugins** | ✅ `main` |
| **DSH‑03** | session event log + "model‑visible ⟺ logged" check | **"every run is traceable"** — one append-only stream | ✅ slice 1 |
| **DSH‑04** | subagent seam + **fallback** (429 → next provider) | subagent scheduling **as a plugin** | ✅ slice 1 + 2 |
| **DSH‑05** | mount a self‑generated tool live (revert if a guard fails) **+ lifecycle hooks** (operator shell command runs before a tool, can block / rewrite / annotate) | Cordis plugin **mount** at runtime + the **hook wire‑protocol** | ✅ s1 + s2 + hooks |
| **DSH‑06** | **health-aware multi-provider resolver** — no single point of failure | **"compose with configuration"** — provider is a runtime choice, not an `import` | ✅ s1‑5 + panel |

`main` chain: `…00e8cfa` (DSH‑04 s2) → `ad68569` (DSH‑05fu) → `f292e09` (DSH‑06 s1)
→ `6cd3785` (s2) → `15ec53f`/`54a19f9` (Observatory panel) → `becfe22` (s3) →
`99eb154` (extract `CapabilityResolver`) → `96debee` (s4) → `578632d` (s5, memory)
→ `e8b9f7f` (DSH‑02 s2) → `e2b1702` (DSH‑05 s2) → `23b3f55` (DSH‑03 s2) →
`e680f35` (DSH‑05 hooks). ~300 tests, zero regressions. Deployed to lg2025.

### DSH‑06 in detail

| Slice | What it wires onto a `Resolver` | Default order |
|---|---|---|
| s1 | `Resolver` primitive: demote-on-fail, cooldown, auto-recover | — |
| s2 | **Queen task decomposition** (`spawn_swarm`) — the 429 we hit | gemini → deepseek → local |
| s3 | **supervisor's local senior reviewer** (the commit gate) | lmstudio → gateway (deepseek opt-in) |
| s4 | the other 4 `call_gemini_pro` callers (kanban / self-improve / evaluator / git-watcher) | gemini → local (deepseek opt-in) |
| — | `CapabilityResolver` — the shared per-capability wiring, so s5+ are ~15 lines | — |

Knobs, per capability: `KENBUN_<CAP>_PROVIDERS` (ordered allowlist / opt-in),
`KENBUN_<CAP>_COOLDOWN_S`. Every failover is logged **and** written to a
cross-process trail the **Observatory → Resilience tab** renders live.

**The rule that emerged:** the fallback default for anything touching sensitive
payloads (audited source, agent system prompts) is *operator-configured
endpoints only*; a third party (DeepSeek) is opt-in. Task-planning text
(decomposition) can default to the wider set.

---

## Part 8 — Single points of failure: the hit list

| Capability | Status | File |
|---|---|---|
| **Queen task decomposition** | ✅ DSH‑06 s2 — Resolver `gemini→deepseek→local` | `tools/strategy/decomposition.py` |
| **Supervisor local senior reviewer** | ✅ DSH‑06 s3 — Resolver `lmstudio→gateway` | `tools/strategy/senior_reviewer.py` |
| **kanban / self-improve / evaluator / git-watcher** | ✅ DSH‑06 s4 — `tools/strategy/reasoning.py` | (4 call sites) |
| **Supervisor Pass 1 / Pass 2 scan** (`AUDIT_URL`) | ✅ DSH‑06 s3b — `_AUDIT_CAP` Resolver `audit→gateway` | `tools/audit/supervisor_agent.py` |
| **Memory** — Honcho only; `except` → silent empty | ✅ DSH‑06 s5 — degradation is now an observable `degraded` event | `tools/memory/honcho_connect.py` |
| **Vector store** — Chroma / one Postgres | ✅ DSH‑06 s5 — `/resilience` reports a memory SPOF when only one store is healthy | `tools/memory/honcho_connect.py` |
| **LLM gateway** — primary→fallback, but 1 fallback, not health-aware | ✅ DSH‑07 — Resolver `primary→fallback→gemini` | `tools/utils/llm_router.py` |
| **The `GEMINI_API_KEY` itself** — free tier `limit: 0` | ⬜ operational, not code | `.env` |

Closed since: **DSH‑02 s2** (`execute_cli_command` → `shell.run` seam, `e8b9f7f`),
**DSH‑03 s2** (model-visible⟺logged fix at the write site + observe-only guard on
the live chat path, `23b3f55`), **DSH‑05 s2** (compile generated source → callable
behind an AST allowlist + restricted `exec`, `e2b1702`), **DSH‑05 hooks** (the
command-hook wire-protocol — matcher + outcome codec + runner + registry, wired
as `PreToolUse` and `PostToolUse` in `execute_cli_command`, `e680f35`), **DSH‑07**
(LLM gateway health-aware failover via `CapabilityResolver` with auto-cooldown
demotion and resilience telemetry).

### DSH‑05 hooks in detail

An operator drops a `hooks.json` (`$KENBUN_HOOKS_FILE` or `~/.claude/hooks.json`,
same schema Claude Code uses). Before a guarded action, every hook whose matcher
selects the query runs as a shell line with a JSON payload on stdin:

- **exit 2** → block, stderr is the reason the model sees
- **exit 0 + `{…}` stdout** → structured: `decision` approve/block,
  `hookSpecificOutput.{permissionDecision, additionalContext, updatedInput}`
  (behind a `hookEventName` discriminator guard), `continue:false` + `stopReason`
- **any other exit / a spawn failure** → non-blocking (the action proceeds)

Hook commands are operator config (git-hook trust model) — deliberately **not**
run through the model-command argv allowlist — but the child env still has
`KEY`/`TOKEN`/`SECRET`/… scrubbed. `run_hook` never raises. Wired points so far:
`PreToolUse` (veto or rewrite CLI commands) and `PostToolUse` (fold context /
telemetry into tool output) in `execute_cli_command`.

---

## Part 9 — How to keep learning this

- **You already know the core of it** if you've used React's `useEffect(fn, [deps])`
  with a cleanup `return`. The cleanup = the undo. The deps array = the coeffect.
  The paper generalises that from one function to a whole live system.
- Read only these of the 92‑page paper: **§1** (the VS Code example), **§1.3**
  (the six contributions), **§5.1** (the ~15‑line algorithms). Skip the proofs.
- The paper repo's own docs are human‑written: `~/Dev/deepseek-harness/docs/cordis-primer.md`.
- Try the real thing: `npx @deepseek-ai/dsh web`, then open **Creator mode** —
  it lets you inspect the running runtime and combine plugins into a new mode.
  That is "everything is a plugin" you can click on.
- Best exercise in *our* code: read `core/tools/strategy/capability_resolver.py`
  (~150 lines) then `senior_reviewer.py` (~110). The primitive + one use of it —
  provider adapters, a health-aware resolver, config-driven order, failover
  telemetry — small enough to hold in your head. `subagent/__init__.py` (~180)
  is the same shape for the seam idea.
- For the hook wire-protocol, read `core/tools/hooks/protocol.py` (~210) — a
  total decoder (`parse_hook_output`) is a good study in "every input maps to
  exactly one outcome, malformed included". Compare it against the TypeScript
  original at `~/Dev/deepseek-harness/packages/hooks/hook-protocol/src/codec.ts`.

---

*Companion doc: `docs/deepseek-harness-study.md` (the full plan + comparison).*
