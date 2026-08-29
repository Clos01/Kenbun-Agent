# Original User Request

## Initial Request — 2026-07-06T23:45:20-04:00

<USER_REQUEST>
# Teamwork Project Prompt — Draft

> Status: Launched

Update the Aura Lead OS Next.js frontend to integrate seamlessly with our new CRG Backoffice multi-tenant SaaS architecture.

Working directory: `~/Dev/Projects/construction/crg-backoffice/frontend`
Integrity mode: demo

## Requirements

### R1. Generic API Integration & Tenant Isolation
Refactor the frontend data fetching and state management to handle the new `core_leads` backend schema. The frontend must expect UUIDs for primary keys. Furthermore, the `tenant_id` MUST be injected via a secure context provider (e.g., React Context) and must not be passed down as a prop through the component tree, ensuring cross-tenant data leakage is impossible.

### R2. Strict Security & Validation (Zod)
You must mandate a Zod schema for the generic `metadata` object at the frontend boundary. Any key not explicitly allowed or sanitized must be ignored to prevent Cross-Site Scripting (XSS) attacks from malicious JSON payloads.

### R3. Normalization & Component Registry
Do not blindly map and render raw JSON keys. You must implement:
1. A **Normalization Layer** (`MetadataTransformer`) that maps raw keys to human-readable labels (e.g. `permit_num` -> "Permit Number") and defines a display order.
2. A **Component Registry** pattern where specific data types (e.g., `date`, `currency`, `boolean`) are automatically mapped to specific, styled React components rather than being rendered as raw text.

### R4. Heritage Design System Enforcement
The styling must strictly adhere to the Heritage Design System. You must use explicit design tokens (e.g., `bg-surface-secondary`, `text-on-surface-muted`, `spacing-md`) for all rendered metadata elements to ensure visual consistency across any industry vertical.

### R5. Architectural AI Review
You must use the `orchestrate` MCP tool to run a `code_review` (or manually trigger `review_code_with_gemini`) on your proposed frontend component changes to verify your React patterns are optimal for a highly scalable Next.js App Router setup before finalizing.

## Acceptance Criteria

### Build & Integrity
- [ ] The Next.js application builds successfully (`npm run build`) without TypeScript or ESLint errors.
- [ ] Zod validation explicitly strips out unhandled or malicious keys from the metadata payload before rendering.

### UI Agnosticism & Design
- [ ] A mock Lead object representing an entirely different industry (e.g., Landscaping) correctly and beautifully renders its custom metadata keys using the Normalization Layer and Component Registry.
- [ ] The rendered output explicitly uses Heritage Design System tokens.

### Architectural Validation
- [ ] An explicit `orchestrate` or `review_code_with_gemini` review is executed on the frontend component changes.
- [ ] The agent successfully resolves any critical findings raised by the Supervisor/Gemini before marking the task complete.
</USER_REQUEST>

## Follow-up — 2026-07-07T03:51:48Z

The user has requested: "make sure fr teamwork delegation we are also using kenbun planka stuff on the legion containers". Please ensure you utilize Planka for task tracking and orchestration.

## Follow-up — 2026-07-07T11:18:00Z

Update the Aura Lead OS Next.js frontend to integrate seamlessly with our new CRG Backoffice multi-tenant SaaS architecture.

Working directory: `~/Dev/Projects/construction/crg-backoffice/frontend`
Integrity mode: demo

### Requirements

#### R1. Generic API Integration & Tenant Isolation
Refactor the frontend data fetching and state management to handle the new `core_leads` backend schema. The frontend must expect UUIDs for primary keys. Furthermore, the `tenant_id` MUST be injected via a secure context provider (e.g., React Context) and must not be passed down as a prop through the component tree, ensuring cross-tenant data leakage is impossible.

#### R2. Strict Security & Validation (Zod)
You must mandate a Zod schema for the generic `metadata` object at the frontend boundary. Any key not explicitly allowed or sanitized must be ignored to prevent Cross-Site Scripting (XSS) attacks from malicious JSON payloads.

#### R3. Normalization & Component Registry
Do not blindly map and render raw JSON keys. You must implement:
1. A **Normalization Layer** (`MetadataTransformer`) that maps raw keys to human-readable labels (e.g. `permit_num` -> "Permit Number") and defines a display order.
2. A **Component Registry** pattern where specific data types (e.g., `date`, `currency`, `boolean`) are automatically mapped to specific, styled React components rather than being rendered as raw text.

#### R4. Heritage Design System Enforcement
The styling must strictly adhere to the Heritage Design System. You must use explicit design tokens (e.g., `bg-surface-secondary`, `text-on-surface-muted`, `spacing-md`) for all rendered metadata elements to ensure visual consistency across any industry vertical.

#### R5. Architectural AI Review
You must use the `orchestrate` MCP tool to run a `code_review` (or manually trigger `review_code_with_gemini`) on your proposed frontend component changes to verify your React patterns are optimal for a highly scalable Next.js App Router setup before finalizing.

### Acceptance Criteria

#### Build & Integrity
- [ ] The Next.js application builds successfully (`npm run build`) without TypeScript or ESLint errors.
- [ ] Zod validation explicitly strips out unhandled or malicious keys from the metadata payload before rendering.

#### UI Agnosticism & Design
- [ ] A mock Lead object representing an entirely different industry (e.g., Landscaping) correctly and beautifully renders its custom metadata keys using the Normalization Layer and Component Registry.
- [ ] The rendered output explicitly uses Heritage Design System tokens.

#### Architectural Validation
- [ ] An explicit `orchestrate` or `review_code_with_gemini` review is executed on the frontend component changes.
- [ ] The agent successfully resolves any critical findings raised by the Supervisor/Gemini before marking the task complete.

---
Please review the existing `PROJECT.md`, `progress.md`, and the current state of the codebase. Resume the orchestration and execution exactly from where the previous agent left off. Do not restart the project from scratch. Also, remember to continue updating Planka!

## Follow-up — 2026-07-10T15:20:47Z

<USER_REQUEST>
Implement database columns and codebase changes in Kenbun to accurately capture, store, and display Success Trials and Failure Trials on the `/telemetry` dashboard.

Working directory: ~/Dev/Kenbun
Integrity mode: development

## Requirements

### R1. PostgreSQL Table Migration
Update the `bayesian_weights` schema in PostgreSQL to include `success_count` and `failure_count` columns. Proactively migrate existing tables on the live database.

### R2. Core Python Codebase Upgrades
Modify the following backend scripts:
1. `postgres_client.py`: Update `init_db()` schema to declare `success_count` and `failure_count`.
2. `strategy_manager.py`: 
   - Update `get_tool_stats()` to query and return actual `success_count` and `failure_count` from SQLite and PostgreSQL (rather than hardcoded `0, 0`).
   - Update `update_intelligence()` to update `success_count` and `failure_count` in PostgreSQL.
   - Update `get_all_stats()` to select and return actual `success_count` and `failure_count` from PostgreSQL.
3. `bayesian.py`: Update `tune_swarm()` to increment `success_count` and `failure_count` in PostgreSQL when tuning tool weights.

### R3. Synchronization
Ensure the code changes compile and hot reload cleanly in `portable_fastmcp`, and sync the updated codebase files to Gitea and remote containers.

## Acceptance Criteria

### Verification
- [ ] Running a test command like `python3 -m tools.utils.bayesian` from inside `portable_fastmcp` outputs updated success/failure metrics from PostgreSQL.
- [ ] Telemetry dashboard API (`/stats`) retrieves actual success/failure values from PostgreSQL, showing non-zero trials once executed.
</USER_REQUEST>

