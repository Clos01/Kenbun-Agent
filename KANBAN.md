# 📋 Kenbun & Eko-Veritas Unified Kanban Board

Last Updated: September 2, 2026 | Operator: Carlos Rivas (Augmented CTO)

---

## 🟢 COMPLETED (Live & Verified on Production)

### 🖥️ 1. Dedicated Full-Page Review Studio & Linear/Raycast Dark Theme (`#08090A`)
- [x] **Task ID:** `t_fb8ff7` | **Assignee:** Architect | **Tenant:** `eko-veritas`
- [x] **What was changed:** Redesigned `/voice-agents` from a cramped floating modal into a browser-wide, full-height 60/40 split workstation. Built a 4-layer Linear/Raycast surface elevation ladder (`#08090A` canvas, `#0E1013` cards, `#14171C` elevated containers, `#1E2228` hairlines, Raycast `#FF6363` coral, `#59D499` mint).
- [x] **What it does:** Provides a Monaco-style line-numbered diff view on the left filling full viewport height (`h-[calc(100vh-190px)]`) alongside a structured 3-card inspector on the right with zero OLED halation or eye strain.
- [x] **Why we did it:** Modal popups caused extreme visual fatigue and horizontal scrolling on long 200-line prompts. Full-screen workstation matches industry gold standards (GitHub PR / Linear / Monaco).

### 🛡️ 2. Cyber AI Prompt Security Sentinel & Auto-Restore Baseline Engine
- [x] **Task ID:** `t_c5f6a2` | **Assignee:** CyberGuard | **Tenant:** `eko-veritas`
- [x] **What was changed:** Engineered `src/lib/prompt-security-sentinel.ts` with regex and heuristic signatures for system prompt escapes (`ignore previous instructions`, `DAN mode`), credential leaks (`api_key`, `process.env`), and massive deletions ($\ge 15$ lines).
- [x] **What it does:** Scans AI proposals in real-time, displays risk score (`0-100`) and threat badges (`[✓ 0 Injections]`, `[✓ 0 Secret Leaks]`), and provides a 1-click `[Auto-Restore Baseline (Zero Deletions)]` button that extracts only the calibrated instruction and injects it under the target section header, preserving 100% of baseline lines.
- [x] **Why we did it:** Smaller LLMs frequently hallucinate truncated prompts that accidentally wipe out 100+ lines of lead intake and operational rules. The Sentinel mathematically guarantees zero line loss and stops cyber injection attacks.

### 🧩 3. Multi-Hunk Diff Splitting, Gap Folding & Intra-Line Word Token Highlighting
- [x] **Task ID:** `t_c5fca7` | **Assignee:** PixelArchitect | **Tenant:** `eko-veritas`
- [x] **What was changed:** Engineered a multi-hunk diff grouping algorithm that clusters separated changes (e.g. Line 29 deletion and Line 82 `+9` additions) and folds unchanged blocks between them with `↕ Expand {N} lines...`. Added pairwise LCS word alignment (`diffWords`) to highlight word token replacements within modified lines.
- [x] **What it does:** Enables multiple distant edits to fit on a single screen simultaneously without scrolling through 50 unchanged lines. Adds `[Change 1: L29]` and `[Change 2: L82]` quick jump pills in the header and wraps modified words in green/red token pills.
- [x] **Why we did it:** Previous single-range diffs occluded separated additions, making reviewers believe lines were missing. Word token highlights pinpoint the exact swapped words within a sentence.

### 🕹️ 4. 4-Button Granular Execution Decision Deck & Cognitive Streamlining
- [x] **Task ID:** `t_ca7866` | **Assignee:** ScaleMaster | **Tenant:** `eko-veritas`
- [x] **What was changed:** Implemented a 4-button execution dock: `[1] Reject Proposal`, `[2] Accept Prompt Only`, `[3] Accept Eval Only`, and `[4] Approve All (Full Deploy)`. Purged confusing latency and zero-injection jargon cards from the right column to keep it strictly to 3 high-signal cards.
- [x] **What it does:** Provides granular deployment control over ElevenLabs live prompt patching vs Postgres evaluation criterion activation, and keeps reviewer attention focused on essential business context.
- [x] **Why we did it:** Operators needed to separate prompt behavior updates from QA rule creation without all-or-nothing constraints, and removing technical clutter eliminates cognitive fatigue.

### 🌿 5. Automated Git Branching CLI (`bin/pr`) & GitHub Actions CI Gate
- [x] **Task ID:** `t_c87434` | **Assignee:** FutureSelf | **Tenant:** `eko-veritas`
- [x] **What was changed:** Created `bin/pr` automation CLI script (`start`, `push`, `sync`, `status`, `merge`), added `.github/workflows/pr-ci.yml` for Node.js 20 build and TypeScript compilation checks on all PRs, and created `.github/pull_request_template.md`.
- [x] **What it does:** Enforces isolated feature branches (`feature/<name>`), runs mandatory pre-flight build checks, generates 1-click GitHub Pull Request creation links, and blocks unverified code from hitting `main`.
- [x] **Why we did it:** Prevents accidental regressions on Azure Container Apps production deployments and ensures safe multi-developer collaboration.

### 📚 6. Client Documentation Hub & Sovereign Kenbun Operator Mastery Guide
- [x] **Task ID:** `t_4b3964` | **Assignee:** Architect | **Tenant:** `eko-veritas`
- [x] **What was changed:** Created `docs/eko-veritas/` subfolder in client repo with 6 dedicated markdown files (`README.md`, `OPERATOR_USER_MANUAL.md`, `GIT_AND_PR_WORKFLOW.md`, `CHANGELOG_AND_EVOLUTION.md`, `BUG_DOCUMENTATION_AND_POSTMORTEMS.md`, `SECURITY_AND_INJECTION_SENTINEL.md`, `ARCHITECTURE_AND_DATABASE_SCHEMA.md`). Authored `docs/KENBUN_OPERATOR_MASTERY_GUIDE.md` in Kenbun sovereign core.
- [x] **What it does:** Provides complete operational instructions for Adrian, post-mortem root causes for engineers, and a comprehensive master guide for Carlos on the 3-system cognitive engine and workbench decoupling.
- [x] **Why we did it:** Permanent institutional memory prevents repeating past bugs and ensures anyone on the team can operate and scale the platform without confusion.

---

## 🟡 IN PROGRESS / READY TO TEST

### 🧪 7. Executive Presentation & Adrian Walkthrough
- [x] **NotebookLM Master Briefing:** Created `EKO_VERITAS_NOTEBOOKLM_MASTER_BRIEFING.md`.
- [x] **Operator User Manual:** Created `docs/eko-veritas/OPERATOR_USER_MANUAL.md`.
- [ ] **Adrian Live Alignment Session:** Review live demonstration of Stagecoach Mechanics calibration, mobile fleet sync, and the new Full-Page Review Studio.

---

## 🔵 NEXT ROADMAP (Backlog)

### 🎙️ 8. Audio Spectrograms & Interactive Waveform Player
- [ ] Ingest ElevenLabs audio recording URLs directly into interactive waveform player.
- [ ] Synchronized transcript highlight scrubbers on audio playback.

### 👻 9. Automated Shadow Testing Engine
- [ ] Replay historical call transcripts against newly calibrated candidate prompts before operator approval.
- [ ] Compare pass/fail score deltas to verify prompt fixes don't introduce regressions.

### ☎️ 10. Direct Telephony Dispatch Bridges
- [ ] Live SIP trunking & Twilio Media Stream webhooks integration.
