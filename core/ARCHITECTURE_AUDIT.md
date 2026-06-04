# 🏗️ Kenbun/core — Architecture & Tech-Debt Audit

**Date:** 2026-05-04
**Scope:** Architecture, organization, layering, coupling, tech debt
**Method:** `scan_repo` symbol map + import graph + filesystem analysis
**Stats:** 115 Python files · 847 symbols · 61,926 LOC · 2.0 GB on disk

---

## 1. Executive Summary

The project has a **clear conceptual architecture** ("Systems 1–6" neural hierarchy documented in `STRUCTURE.md` and `NEURAL_HIERARCHY.md`) and the directory layout under `tools/` reflects it well (`audit/`, `memory/`, `strategy/`, `execution/`, `core/`). However, the **implementation has drifted from the design** and accumulated meaningful tech debt:

- **Inconsistent import scheme** — files mix `from tools.core.x` and bare `from core.x`, propped up by `sys.path` shims.
- **Duplicate modules** with divergent contents (`error_memory.py`, `orchestrator.py`, `server.py`, two copies of `skills/hatch-pet/`).
- **God modules** — `core/orchestrator.py` (987 LOC) and `core/server.py` (756 LOC) concentrate too much responsibility.
- **Hardcoded user-specific paths** (`/Users/dev/...`) in 5+ files break portability.
- **Repo hygiene issues** — 184 MB `external/`, 541 MB `.venv` (correctly ignored), 50 k-line `STRATEGY_BENCHMARK.py`, scratch files committed at the root.

Overall grade: **C+** — the bones are good, but the system needs an "import unification" pass and a `god-module split` to prevent decay into spaghetti.

---

## 2. Findings by Severity

### 🔴 HIGH — Inconsistent Import Strategy (architectural smell)

Two import styles coexist across the codebase:

| Style | Count | Examples |
|---|---|---|
| Absolute `from tools.x.y` | 25 | `tools/core/orchestrator.py` lines 26–37 |
| Bare `from x.y` (relies on `sys.path` injection) | 20+ | `tools/core/server.py:35,62,63`, `tools/core/api_server.py`, `tools/audit/gemini_reviewer.py`, `tools/memory/knowledge_manager.py` |

The bare imports only work because of shims like:

```python
# tools/orchestrator.py
sys.path.insert(0, str(tools_dir))
from core.orchestrator import *
```

**Risk:**
- Modules become un-importable from anywhere except a specific entry point.
- Same module (`tools.core.orchestrator`) can be loaded twice under different names → duplicate state, broken singletons (e.g. `governor`, `router`).
- Refactoring tools (mypy, IDE rename, pylint) silently misbehave.

**Fix:** Pick **one** style (recommend `from tools.x.y import …`), make `tools/` a proper package, and remove all `sys.path.insert` shims. Treat `tools/orchestrator.py` and `tools/server.py` as deprecated re-export shims to delete.

---

### 🔴 HIGH — Duplicate / Conflicting Modules

| Pair | Issue |
|---|---|
| `tools/orchestrator.py` ↔ `tools/core/orchestrator.py` | Top-level file is a `sys.path` shim doing `from core.orchestrator import *`. Risk of double-import. |
| `tools/server.py` ↔ `tools/core/server.py` | Top-level is a `subprocess.run` re-launcher. Confusing. |
| `tools/memory/error_memory.py` ↔ `tools/utils/error_memory.py` | The `memory/` version is a 9-line `print()` stub; the `utils/` version is the real 153-line ChromaDB-backed implementation. `production_swarm.py` imports the real one, but the stub will silently shadow it depending on import path. |
| `tools/skills/hatch-pet/scripts/*` ↔ `external/open-design/skills/hatch-pet/scripts/*` | `diff -rq` shows 13 byte-identical files duplicated — 2× maintenance cost. |
| `tools/observatory/` ↔ `neural_observatory/` ↔ `tools/dashboard/` (WIP per docs) | Three potential UI homes; `STRUCTURE.md` mentions all three. |

**Fix:**
1. Delete `tools/memory/error_memory.py` (stub).
2. Delete `tools/orchestrator.py` and `tools/server.py` shims (replace with proper `python -m tools.core.server` invocations).
3. Make `external/open-design/skills` either a git submodule or a single source-of-truth directory; remove the duplicate.
4. Decide on **one** observatory project; archive the others under `archive/`.

---

### 🟠 MEDIUM — God Modules

| File | LOC | Smell |
|---|---|---|
| `tools/core/orchestrator.py` | **987** | 14 imports, contains pipeline builders for bug-fix/code-review/research/shadow-test/design-ui, agent spawning, context building, language detection, async swarm, sync swarm wrapper. |
| `tools/core/server.py` | **756** | Single module exposes ~30 MCP tools — every new capability lands here. |
| `tools/audit/gemini_reviewer.py` | 374 | Mixes Gemini client init, DDG search, code review, plain research, and audio transcription. |
| `brain_health/STRATEGY_BENCHMARK.py` | **50,063** | This is almost certainly a generated benchmark dump committed by mistake. **Should not be in source control.** |

**Fix:**
- Split `orchestrator.py` into `tools/core/orchestrator.py` (the state machine only) and `tools/core/pipelines/{bugfix,code_review,research,shadow_test,design_ui}.py`. Each `_build_*_pipeline` function becomes its own module.
- In `server.py`, group the 30 tool registrations into routers (`tools/core/server/{memory_tools,audit_tools,exec_tools,hivemind_tools}.py`) and import them — same pattern Flask/FastAPI uses for blueprints.
- Move/archive `STRATEGY_BENCHMARK.py` out of source (`brain_health/data/` or `.gitignore` it).
- Split `gemini_reviewer.py` → `gemini_client.py`, `code_reviewer.py`, `researcher.py`, `transcriber.py`.

---

### 🟠 MEDIUM — Hardcoded User-Specific Paths

```text
tools/core/report_intelligence.py:8  → "/Users/dev/Dev/Kenbun/core/..."
tools/core/minimal.py:8              → "/Users/dev/Dev/Kenbun/core/..."
tools/memory/chroma_db_connect.py:21 → "/Users/dev/Dev/Projects/_TEMPLATE_PROJECT" (env override exists ✅)
tools/utils/harvester.py:53          → "/Users/dev/.gemini/kenbun/brain"
tools/scratch/swarm_test.py:7        → "/Users/dev/Dev/Projects/Food/ElToroLoco"
```

The project already has `tools/utils/path_utils.get_project_root()` — use it everywhere. For external paths, read from `.env` (you already do this for some).

---

### 🟡 LOW — Tests Scattered, No Unified Test Tree

Test files live in three places:
- `brain_health/test_*.py` (3 files)
- `tools/audit/test_ensemble.py`
- `scratch/test_supervisor_demo.py`

There is no `tests/` directory and no `pytest.ini`/`pyproject.toml` test config. CI discovery becomes guesswork.

**Fix:** Create top-level `tests/` mirroring `tools/` structure, add a `pyproject.toml` with `[tool.pytest.ini_options] testpaths = ["tests"]`. Move `scratch/test_supervisor_demo.py` out of "scratch" (it's a real test) or rename it.

---

### 🟡 LOW — Repo Hygiene

| Issue | Detail |
|---|---|
| `.venv` (541 MB) | Correctly gitignored ✅ |
| `external/` (184 MB) | Vendored Open Design assets — consider git submodule. |
| `artifacts/brain/<uuid>/scratch/verify_bridge.py` | Stale runtime artifact under source tree. Should be in a gitignored runtime dir. |
| `.gitignore` line `/Users/dev/Dev/Kenbun/core/nano .env` | Looks like an accidentally-committed shell command. Remove. |
| Root has 9 markdown docs | Consider consolidating into `docs/`: `DESIGN.md`, `STRUCTURE.md`, `SYSTEM_MAP.md`, `NEURAL_HIERARCHY.md`, `FILE_GLOSSARY.md`, `OPERATIONS_MANUAL.md`, `DEPLOYMENT_GUIDE.md`, `VOIP_SETUP.md`, `POST_MORTEM.md`. Keep only `README.md` at root. |
| Root has 3 entrypoint scripts (`production_swarm.py`, `swarm_daemon.py`, `export_to_obsidian.py`) | Move to `scripts/` or `bin/`, expose as console-scripts in `pyproject.toml`. |
| `tools/scratch/`, top-level `scratch/`, `tools/swarm_report_auth.md` | Mixing scratch/test/prod inside `tools/`. |
| 14 bare `except:` clauses in `tools/` | Catches `SystemExit`/`KeyboardInterrupt` — should be `except Exception:` minimum. |

---

### 🟡 LOW — Coupling: orchestrator imports almost everything

`tools/core/orchestrator.py` directly imports from 9 different submodules (`strategy`, `core`, `utils`, `audit`). This is expected for an orchestrator, but combined with its 987-LOC size it makes the module a single point of architectural failure. Recommendation: introduce a thin **dependency-injection seam** (a `ToolBox` dataclass passed in) so the orchestrator can be unit-tested in isolation. The `tools` dict already half-does this — formalize it with a Protocol/TypedDict.

---

### 🟡 LOW — Documentation Drift

`STRUCTURE.md` claims:
- `tools/memory/ALGORITHMS.md` exists → **not present.**
- `tools/dashboard/` exists → **not present** (only `tools/observatory/` and `neural_observatory/`).
- `tools/craft/` exists → **present** but not in scan output (likely no Python).

Run a periodic doc-vs-filesystem checker (you have a "Documentation Parity" mandate at the bottom of `STRUCTURE.md` — automate it).

---

## 3. What's Working Well 👍

- **Clear conceptual layering** (Systems 1–6) and folders match the layers.
- **Centralized config**: `tools/core/config.py`, `tools/utils/path_utils.py`, `tools/utils/secret_manager.py` are good patterns.
- **Brain-health/benchmark culture**: `brain_health/` showing routing failures, telemetry, hallucination tests is unusually mature.
- **Checkpoint/restore** (`backtracker.py`) and **error-memory recall** are sound resilience features.
- **Proper secret encryption** (`secret_manager.py` + `.kenbun_master.key` is gitignored).
- **No TODO/FIXME comments** — either pristine or aggressively cleaned.

---

## 4. Recommended Roadmap

### Sprint 1 — De-risk imports (½ day)
1. Pick `from tools.x.y` everywhere.
2. Search-replace 20 bare imports (`from core.`, `from audit.`, `from memory.`, `from strategy.`, `from utils.`, `from execution.`).
3. Delete `tools/orchestrator.py` and `tools/server.py` shims.
4. Add `pyproject.toml` declaring `tools` as a proper package.
5. Run pytest + a "import every module" smoke test.

### Sprint 2 — De-duplicate (½ day)
1. Delete the stub `tools/memory/error_memory.py`.
2. Resolve the `tools/skills` ↔ `external/open-design/skills` duplication.
3. Pick one observatory; archive the others.
4. Move `STRATEGY_BENCHMARK.py` out of the repo (or git-lfs / gitignore).

### Sprint 3 — Split god modules (1–2 days)
1. Extract pipeline builders from `orchestrator.py`.
2. Split `server.py` MCP tool registration into routers by domain.
3. Split `gemini_reviewer.py`.

### Sprint 4 — Hygiene (½ day)
1. Move docs into `docs/`, scripts into `scripts/`.
2. Replace hardcoded `/Users/dev/...` with `path_utils` + env vars.
3. Standardize tests under `tests/` with pytest config.
4. Fix bare `except:` clauses.
5. Clean stray `.gitignore` line.

---

## 5. Quick-Reference: Files to Touch First

| Priority | File | Action |
|---|---|---|
| P0 | `tools/orchestrator.py` | DELETE |
| P0 | `tools/server.py` | DELETE |
| P0 | `tools/memory/error_memory.py` | DELETE (stub) |
| P0 | `brain_health/STRATEGY_BENCHMARK.py` | Move out of repo |
| P1 | `tools/core/orchestrator.py` | Split |
| P1 | `tools/core/server.py` | Split into routers |
| P1 | `tools/audit/gemini_reviewer.py` | Split |
| P2 | `tools/core/report_intelligence.py` | Replace hardcoded path |
| P2 | `tools/core/minimal.py` | Replace hardcoded path |
| P2 | `.gitignore` | Remove malformed line |
| P3 | `STRUCTURE.md` | Reconcile with actual filesystem |

---

*Generated by the Kenbun audit pipeline · architecture lens · 2026-05-04*