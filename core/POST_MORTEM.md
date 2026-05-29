# POST_MORTEM: System 4 Bottleneck Resolution

## Context
The Kenbun system was experiencing "Audit Friction" and routing inaccuracies due to its reactive, keyword-based nature. System 2 (Supervisor) was rejecting too many valid UI tasks, and System 4 (Strategy) was failing to classify complex, multi-layered tasks.

**Design Spec**: [DESIGN.md](./design_systems/sovereign-sharp/DESIGN.md)

## The "Senior Version" Solution
We architected a transition to an **Autonomous CTO** model.
1. **Semantic Routing**: Switched from keyword weights to hybrid signal aggregation (Semantic + Contextual + Keywords).
2. **Consensus Auditing**: Implemented a security-first consensus loop to eliminate "Hung Juries" in System 2.
3. **Proactive Watchdog**: Added a heartbeat monitor for cross-device infrastructure.

## Lessons Learned
- **Parametric Trust is a Vulnerability**: Relying on the Agent to pass a `category` to the Supervisor was identified as a critical risk. Automatic triage (content-based) is the superior pattern.
- **Context is King**: Tracking `recent_paths` significantly reduces "Route Oscillations" during focused sprints.

## Strategic Mandate
All future tools MUST implement a `record_success` method to feed the Hivemind's routing history.

---

# POST_MORTEM: Obsidian Nexus UI Modernization (May 2026)

## Context
The previous "Neural Observatory" was card-heavy and used "vibe-coded" blue/purple aesthetics that felt unprofessional and lacked technical depth. Telemetry was capped at 5s, leading to a stale "reactive" feel.

## The "Senior Version" Solution
1. **Architectural Minimalism**: Transitioned to the **Obsidian Nexus** design system. Used true black (#0e0e10) and a unified glass surface to reduce visual noise.
2. **Frequency Hardening**: Implemented **1Hz (1s) polling** across all telemetry endpoints. Optimized backend I/O to sustain real-time feedback without CPU spikes.
3. **Technical Typography**: Standardized on **Space Grotesk** and **Inter** to align with high-fidelity technical documentation standards.
4. **Framer-Motion Integration**: Added declarative layout animations to make data updates feel like a seamless "Neural Pulse" rather than discrete re-renders.

## Lessons Learned
- **Borders > Shadows**: In dark-mode professional UIs, 1px borders with low-opacity colors provide superior structural definition without the "muddy" look of drop shadows.
- **Unified Plane**: Grouping components onto a single glass surface (the "Nexus" pattern) creates a much more cohesive user experience than floating cards.

---

# POST_MORTEM: Ollama Disk Overfill & Local Ensemble Integration (May 2026)

## Context
When running local ensemble validation via System 2 (`ensemble_audit.py`), model pulls failed with a `no space left on device` error. Furthermore, a `ModuleNotFoundError` for `aiohttp` caused the local supervisor to fall back straight to Tier 2 (cloud escalation), bypassing the local GPU workstation's sovereign voting pool entirely.

## The "Senior Version" Solution
1. **Container Isolation (Ext4 Named Volume)**: Removed WSL2 home-directory host bind-mounts shadowing tiny virtual memory overlays, replacing them with a named Docker volume (`ollama_data`). This successfully mounted the workstation's `/root/.ollama` path to the primary 914 GB ext4 volume (`/dev/sde`), resolving the storage bottleneck permanently.
2. **Warm-VRAM Pre-flight Check**: Verified all three models are actively cached in parallel (`gemma2:latest`, `llama3.2:latest`, `phi3:latest`).
3. **Dependency Hardening**: Integrated `aiohttp` into the local virtual environment to restore the async HTTP parallel processing layer.
4. **Resilient Key Triage**: Patched assertion parsing in `test_ensemble.py` to seamlessly accept both dynamic and executive audit response keys (`status`/`critique` vs. `decision`/`reason`).

## Lessons Learned
- **WSL2 Shadowing**: WSL2 mounts under user home directories on Windows hosts can be silently capped by `tmpfs` overlays. Named volumes are mandatory for heavy local LLM directories to inherit physical hard disk partitions.
- **Warm VRAM Loading Time**: Initial loading times of concurrent local LLMs (e.g., 9.2B gemma2 + 3B llama3.2 + 3.8B phi3) can exceed standard 45s HTTP client timeouts. Subsequent requests are warm and sub-second.

---

# POST_MORTEM: Phase 2 Codebase Hardening, SVE Verification & SAC Integration (May 2026)

## Context
The Kenbun backend system had accumulated several "ghost" file dependencies, dangling imports, and unhandled async coroutines. Furthermore, running cloud AI requests on sensitive files exposed private naming schemes and structural details, while standard context-jailing caused the AI to hallucinate and guess interface names.

## The "Senior Version" Solution
1. **Exhaustive Pruning**: Deleted 12 verified dead files from disk and synchronized `STRUCTURE.md` and `FILE_GLOSSARY.md` to completely eliminate "ghost" references.
2. **Registry Hardening**: Hardened `server.py` with a path-traversal-proof jailed file reader fallback and registered all missing orchestrator tools.
3. **Async & Memory Corrections**: Patched `awareness_engine.py` to be fully asynchronous and resolved a missing `time` import bug in `hive_memory.py` that had caused zero-valued timestamps in the knowledge pool.
4. **Sovereign Agentic Cryptography (SAC)**: Engineered and verified a zero-trust development framework:
   * **Hybrid AST Shadowing**: Feeds structural signatures to the cloud to prevent guesses without exposing logic.
   * **Semantic Pseudonymization**: Maps sensitive names (variables/keys) to stable semantic placeholders.
   * **Scope-Aware AST Sentinel**: Audits returned code, tracks local variables on a scope stack to prevent false-positives, and auto-heals typos or blocks shell exploits before execution.

## Lessons Learned
- **Unawaited Coroutines**: Evolutionary background daemons running unawaited coroutines (like the old `run_supervisor_audit`) fail silently and crash on subsequent dict access.
- **AST Loop Scopes**: Static AST code audits must build local scope stacks (tracking loop targets and function arguments) to avoid incorrectly flagging locally bound variables as "Wild Variables."
- **Path Traversal Guards**: Custom file-reading fallback tools inside MCP servers must strictly jail their resolution targets within the project root to prevent Local File Inclusion (LFI) security vulnerabilities.
