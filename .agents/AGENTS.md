# Workspace Agentic Rules & Learnings

These rules and architectural patterns define how the Swarm designs, refines, and manages workflows and integrations.

---

## 1. AGENTIC WORKFLOW DESIGN VS. VISUAL SPAGHETTI

When building automations in n8n or scripting back-office pipelines:
*   **De-clutter Node Complexity**: Avoid creating massive, multi-branched visual node maps ("visual spaghetti") for complex logical conditions. 
*   **Goal-Oriented Directives**: Use a three-layer architecture:
    1.  **Directive (Goal)**: Define *what* needs to be accomplished in plain English.
    2.  **Orchestration (AI Router)**: Delegate the reasoning and decision loops to local agent scripts (Ollama/FastMCP) or terminal agents.
    3.  **Execution (Self-Correcting Scripts)**: Have the agent execute targeted Python/JS code, test it, capture failures, and rewrite parameters dynamically until success is verified.
*   **State & Session Persistence**: When running multi-stage scripts or interacting with agents over successive nodes, maintain continuous context using UUID Session IDs:
    ```bash
    # Specifying session-id allows agents to resume context across successive runs
    claude -p "Verify current AP status" --session-id "uuid-1234"
    claude -p "Why is AP-2 down?" -r "uuid-1234"
    ```
*   **Watchdog Error Handlers**: Every API/OAuth2 integration (e.g., Google Calendar, Gmail, Twilio) must have a scheduler watchdog or an *Error Trigger* node configured to alert developers immediately (via Telegram/SMS) upon connection expiry.

---

## 2. INTEGRATED BUSINESS FLOW PIPELINE STANDARDS

When modeling business processes (such as flooring staging, client intake, or scheduling), design workflows to transition cleanly across these eight phases:

1.  **Phase 1: Inbound Lead Capture**: Catching webhooks, cleaning data, and auto-replying.
2.  **Phase 2: CRM & Planka Board Sync**: Automatically creating task cards on the board and moving them based on client states.
3.  **Phase 3: AI Valuation & turn-key Estimations**: Calling calculation API endpoints (e.g., Turnkey labor/material checks) and injecting values into Planka/emails.
4.  **Phase 4: Logistics & Access Management**: Capturing lockbox keys, entrance codes, and coordinates. Syncing events to Google Calendar.
5.  **Phase 5: Automated Upsell Chasing**: Schedulers checking task completion (e.g., 24h post-install) to pitch add-on services or materials.
6.  **Phase 6: Live Market Scanners**: Scrapers checking listing websites to detect when properties sell or change status.
7.  **Phase 7: Team Operations Dispatch**: Pushing SMS/Telegram notifications to installers/crews with logistics briefs.
8.  **Phase 8: Close-out & Tally Completion**: Client confirmation forms trigger final invoices and move the Planka cards to "Completed".

---

## 3. GIT BRANCHING & PR SAFETY MANDATE

*   **Never Push Directly to `main`**: When initiating any new feature, integration, or refactor, the Swarm MUST create an isolated feature branch (e.g., `feature/nevermiss-evals-dashboard`) from `main`.
*   **Branching Workflow**:
    1. `git checkout -b feature/<feature-name>`
    2. Commit all changes locally on the feature branch.
    3. Push feature branch and open a Pull Request (PR) for review.
    4. Only merge to `main` after CI/CD automated deployment verification.

---

## 4. STANDALONE APP ISOLATION & WORKBENCH DECOUPLING MANDATE

*   **Kenbun Core is sacred**: Kenbun (`/Users/carlosrivas/Dev/Kenbun`) is the Sovereign Engine, CTO Workbench, and Orchestration Tool. It MUST NEVER contain client application production code directly inside its core tree.
*   **Isolated Workspace Standard**: Every client project, SaaS product, or external app (e.g., `NeverMiss.ai`, `spf-admin`) MUST be initialized in its own dedicated, isolated directory (e.g., `/Users/carlosrivas/Dev/Projects/<project-name>` or `/Users/carlosrivas/Dev/<project-name>`).
*   **Decoupled Repositories**: Each project maintains its own independent Git repository, `package.json`, environment variables, and deployment pipeline to prevent corruption or cross-contamination of the Kenbun workbench.

---

## 5. AZURE POSTGRES FIREWALL TIMEOUT TROUBLESHOOTING

When resolving `Connection terminated due to connection timeout` failures connecting to Azure PostgreSQL Flexible Server:
*   **Identify Outbound Host IP:** Outbound client IPs shift dynamically when working on residential or cellular carrier networks. Run `curl api.ipify.org` inside the dev shell to inspect the actual source IP of the local container or dev host.
*   **Subnet Range Rule Configuration:** Instead of allowing a single static IP address (which breaks as soon as the carrier leases a new IP), configure Azure Firewall Networking rules to allow the carrier's subnet (e.g., set Start IP to `174.245.0.0` and End IP to `174.245.255.255` for `/16` blocks). This prevents continuous connection timeouts.

---

## 6. GIT OPERATIONS SAFETY GUARDRAILS

*   **No Blind Pulls:** The Swarm is strictly forbidden from running `git pull` if there are local uncommitted changes. Stash or commit edits first.
*   **Feature Branch Isolations:** Never pull main directly into a feature branch. Use `git fetch origin` followed by `git merge origin/main` to carefully merge incoming code.
*   **Validation Guardrail:** Use the local safety script `bin/git-safe` in the repository's root to check workspace status and safely run Git sync operations.

---

## 7. CARLOS HONCHO OUTPUT ORGANIZATION SCHEMA & TOOL OBSERVABILITY PROTOCOL

Every time the agent answers an architectural query, executes a pipeline, completes a task, or resolves a bug, it MUST present its final response structured strictly according to the Carlos Honcho Standard:

### 1. High-Level Summary of Reasoning
[Provide a concise 2-3 sentence summary explaining the diagnosis, architectural rationale, and resolution steps.]

---

### 2. Tool Execution & Observability Telemetry
[Disclose every tool invoked during the turn to provide complete transparency into the agent's actions:]
| Tool Name | Purpose / Input Summary | Status | Result / Output Summary |
|---|---|---|---|
| `tool_name` | Concise description of arguments | ✅ Success / ⚠️ Failed | Outcome or extracted value |

---

### 3. Core Architecture & Implementation
[Deliver the direct, actionable answer, code blocks, diffs, or system modifications.]

---

### 4. Memory & Database Sync References

#### 🧠 Honcho (Supervisor Memory Fix IDs)
* **[Name of First Fix] Fix:** `[Honcho Fix ID, e.g. fix_123456789_abcdef]`
* **[Name of Second Fix] Fix:** `[Honcho Fix ID]`
* **Error Log Reference ID:** `[Original error hash, digest, or code from the log, e.g. digest_3888016447]`

#### 📁 Chroma DB Vector Indexing & Semantic References
* **Status:** Successfully reindexed [N] files into [M] semantic chunks under project path `[Project Path]`.
* **Cited Files & Symbols:** [`filename.py`](file:///path/to/file#L1-L20)

---

### 5. Next Best Move / Proactive Recommendations
[Outline the immediate next logical step or proactive architectural improvements.]

## 8. AUTONOMOUS MULTI-SOURCE RESEARCH & DIALECTIC EVOLUTION PROTOCOL

When solving complex engineering, UI/UX, or architectural challenges:
1. **System 3 Memory Recall First:** Eagerly search Hivemind / Honcho (`search_hivemind_concepts`, `recall_fix`, `ask_architect`) to retrieve established patterns, past fixes, design tokens, and recorded anti-patterns.
2. **Autonomous Multi-Source Investigation on Miss:** If Hivemind returns empty, inconclusive, or outdated results, the Swarm MUST NEVER guess blindly or fall back to generic boilerplate. It must immediately:
   * **Multi-Source Web Search:** Query `search_web` / `web_search` across current official docs, GitHub repositories, and industry leaders.
   * **Official Docs & AI Synthesis:** Query `research_official_docs` and `research_with_gemini` (Gemini 2.0 Flash) to cross-check latest specs.
   * **UI/UX Engineering Guidance:** Consult `ask_ui_expert` and cross-reference modern component patterns (`21st.dev`, `Aceternity UI`, `Linear`, `Raycast`).
3. **Iterative Best-Move Formulation:** Synthesize past project history with the newly discovered external intelligence to propose the optimal "Senior Version" solution.
4. **The User Decision Fork:**
   * **Branch A: User Approves / Validates:**
     - Immediately forge new permanent history in Hivemind (`save_to_hivemind`, `remember_fix`, `remember_preference`) so future tasks benefit permanently without repeated research.
   * **Branch B: User Rejects, Corrects, or Requests Redesign:**
     - **Capture Negative Constraints:** Immediately log the rejected pattern or negative preference in Honcho (`remember_preference`, `remember_fix`) as an *anti-pattern* to avoid repeating.
     - **Analyze Delta & Root Cause:** Identify the exact gap (e.g. excessive complexity, wrong aesthetic direction, performance concern, missing requirement).
     - **Targeted Re-Investigation Loop:** Query `research_with_gemini` / `ask_ui_expert` with the new negative constraints to discover viable alternative paradigms.
     - **Re-Propose Revised Senior Pattern:** Present the adapted solution with clear trade-offs and diffs until user approval is achieved.

---

## 9. PROACTIVE OPERATOR MILESTONE COMMUNICATION MANDATE

When interacting across terminal environments, Claude Code, IDE extensions, or MCP tools:
* **No Black-Box Silence:** The agent is strictly prohibited from running long sequences of silent tool calls without communicating progress.
* **Transparent Step Milestones:** At each critical phase of diagnosis, online research synthesis, file modifications, or compiler testing, output a concise 1-2 sentence visible progress checkpoint.
* **Continuous Alignment:** Keep the operator informed of *what* is being investigated, *why* a particular decision is being tested, and *what* the immediate next step is.

---

### Tools Used
* [List of tools called, e.g. view_file, run_command, call_mcp_tool, etc.]





---

## 10. AUTONOMOUS REFLEXION (MANDATORY RAG MEMORY)

**Mandatory Pre-Flight Check:** Before answering architectural questions, executing significant code changes, or proposing a solution, you MUST call the `autonomous_reflexion` tool (if available in your MCP tools) to retrieve past mistakes, fixes, and contextual logic. Do not skip this step; it is how you retrieve the logic flows and anti-patterns tracked by the system.

---

## 11. MINTO PYRAMID EXECUTIVE COMMUNICATION PROTOCOL

Every response delivered to the operator must adhere to Barbara Minto's Bottom-Line-Up-Front (BLUF) hierarchy:
1. **The Peak (Answer First):** Deliver the direct conclusion, decision, or status in the very first 1-2 sentences. Never force the user to wade through preamble.
2. **The Pillars (Supporting Rationale):** Provide 2-4 structured arguments grouped by logical domains (Performance, Security, Cost).
3. **The Base (Technical Evidence):** Back up every claim with code blocks, diffs, telemetry metrics, and terminal outputs.

---

## 12. 5-PERSONA ADVISORY COUNCIL (SYSTEM 2 CONSENSUS AUDIT)

Before marking complex tasks as Complete, major refactors, or database/auth alterations, the agent must evaluate decisions across the 5 specialized perspectives:
* 🛡️ **CyberGuard (Security):** Zero-trust boundary check, input sanitation, secret isolation.
* ⚡ **ScaleMaster (Scalability):** Horizontally scalable DB schemas, indexing, concurrency limits.
* 💰 **FrugalCFO (Cost/Tokens):** Local-first execution (P330), minimal token waste, serverless scaling.
* 🎨 **PixelArchitect (UX/Design):** Heritage Design System tokens, micro-interactions, responsive layouts.
* 🔮 **FutureSelf (Tech Debt):** Clean documentation (`STRUCTURE.md`), modular code, anti-pattern prevention.

---

## 13. CLIENT MULTIMODAL FEEDBACK GROUNDING & KNOWLEDGE PROTOCOL

When ingesting client or stakeholder video walkthroughs, voice feedback, or product critiques (e.g. Adrian's NeverMiss AI / Eko-Veritas review videos):
1. **Verbatim Timestamped Grounding:** Always extract exact quotes with second-level timestamps. Never summarize vaguely or lose the speaker's original wording.
2. **UI Route & Tab Correlation:** Map the spoken context directly to the active application route (e.g. `/fleet-overview`, `/voice-agents`, `/call-telemetry`).
3. **AST Codebase Dictionary Lookup:** Map the user's critique or feature request to concrete React components, API routes, and line numbers in the target codebase (`core/tools/codebase/codebase_feedback_mapper.py`).
4. **Proactive Gap & Audit Formulation:** Automatically generate audit questions to verify whether current code fulfills the client's intent or requires technical debt remediation.
5. **Triple-Memory Persistence:** Persist all structured intelligence across Chroma DB vector embeddings, Honcho/Hivemind System 3 memory, and the local SQLite Knowledge Graph (`data/feedback_intelligence.db`).

---

## 14. ADVANCED WHITE SPACE & NEGATIVE SPACE UX/UI PATTERNS

When architecting, refining, or auditing user interfaces, the Swarm MUST apply intentional micro and macro negative space principles (grounded in Alena Krupko's white space methodology):

1. **Micro vs. Macro White Space:**
   * **Micro White Space:** Spacing between atomic elements (letter-spacing, padding, line-height `1.5` to `1.65` for body text). Tight line-heights in multi-line text are strictly prohibited.
   * **Macro White Space:** Negative space between structural containers, sections, and cards that establishes breathing room and anchors visual hierarchy.
2. **The Law of Proximity:**
   * Group related interactive elements closely with micro-spacing; separate distinct logical domains with macro-spacing instead of relying on heavy visual borders or cluttered divider lines.
3. **Emphasis Without Artificial Distortion:**
   * Draw focus to critical CTAs, KPIs, or key metrics by expanding surrounding negative space rather than artificially inflating font size or using loud neon colors.
4. **Creative Negative Space Techniques:**
   * **Asymmetrical Carousels & Grid Disruption:** Allow cards to bleed subtly toward viewport edges to invite horizontal exploration and signal hidden depth.
   * **Shadowy & Natural Bleed Borders:** Replace rigid, blocky horizontal container lines with soft ambient shadows, radial gradients, or textured negative space.
   * **Fullscreen Focus Interstitials:** Replace cluttered overlay modals with spacious, textured fullscreen interstitials for single-action decision gates.
   * **Animated Negative Space Displacement:** Animate containers to expand into negative space or merge elements dynamically upon scroll for tactile responsiveness.

---

## 15. ZERO-ERROR PRE-FLIGHT SENTINEL PROTOCOL (`console-network-sentinel`)

The Swarm is strictly prohibited from marking code changes as complete without executing an automated pre-flight console, network, and database query audit:
1. **Live Route Probe Guard:** Run `bin/console-sentinel probe http://localhost:3000` (or `audit_console_and_network`) across all active dashboard routes.
2. **Zero-Tolerance Criteria:**
    * **0 Console / SSR Errors:** No `ReferenceError`, `TypeError`, React hydration mismatches, or unhandled exception overlays.
    * **0 Statement Timeouts:** No PostgreSQL queries exceeding `statement_timeout` (`canceling statement due to statement timeout`).
    * **Fast Latency SLA:** Every primary route must respond under `<1000ms`.
3. **Autonomous Auto-Fix Loop:** If a statement timeout or slow query is detected, immediately refactor correlated subqueries into CTEs with `DISTINCT ON` and pre-aggregations.

---

## 16. THE FEYNMAN REVERSIBLE COGNITION & 30-DAY TOOL AUDIT PROTOCOL

On every task selected from the Kanban board or codebase:
1. **The Feynman Zero-Jargon Test (Explain to a Dumb Supervisor):**
   * Deeply study the task/feature -> Close all open tabs/crutches -> Explain it out loud in plain, simple English as if explaining to a naive supervisor AI (which could hallucinate the moon is made of cheese).
   * **Zero Jargon Rule:** Technical jargon is a hiding place where complicated words fake understanding. Using simple words leaves nowhere to hide.
2. **Freeze & Hallucination Point Detection:**
   * If you get halfway through an explanation and freeze, stumble, or rely on vague assumptions, that "freeze point" is the exact epistemic gap or tool-calling failure point (common on smaller models like Ollama/P330 that hallucinate arguments).
3. **The Raw Source Gap-Fill Loop:**
   * When a freeze moment hits: STOP immediately. Go back to raw source code/data, locate the exact line/structure, fill the gap, and re-explain simply from the beginning until clear.
4. **Dual-Persona Reversible Thinking (Developer <-> User):**
   * **Phase 1 (Developer Mode):** Focus on algorithmic rigor, scalable schemas, indexes, and defensive error handling.
   * **Phase 2 (End-User Mode):** Step into the shoes of the real human (the homeowner requesting an estimate, the hardwood flooring contractor on-site, the healthcare worker, the receptionist). Audit usability, ergonomics, and clarity.
5. **30-Day Tool Invocation Ledger:**
   * Forcefully log and verify all tool calls over a rolling 30-day window (`data/tool_telemetry_30d.db`) to ensure smaller models execute tool pipelines reliably without hallucinating parameters.
