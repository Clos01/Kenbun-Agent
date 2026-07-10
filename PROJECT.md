# Project: Aura Lead OS Frontend Upgrade for CRG Backoffice SaaS

## Architecture
- **Tenant Context (`TenantContext`)**: Injected via React Context at the root of the app. Components consume it to isolate data by tenant and prevent cross-tenant leakage.
- **Frontend Fetching (`apiClient`)**: API request utilities that read from the `TenantContext` to secure all calls.
- **Validation Layer (`MetadataSchema`)**: Built with Zod to sanitize and strip malicious keys from incoming lead metadata at the frontend boundary.
- **Normalization Layer (`MetadataTransformer`)**: Processes raw metadata keys, maps them to human-readable labels, and determines their visual ordering.
- **Component Registry**: Automatically maps normalized data types (e.g., date, currency, boolean) to custom-styled React components conforming to Heritage design tokens.

## Milestones

### Implementation Track
| # | Name | Scope | Dependencies | Status | Conversation ID |
|---|------|-------|-------------|--------|-----------------|
| M1 | Tenant Context & Refactoring | Refactor data fetching and state to use UUIDs, inject `tenant_id` via secure React Context. | None | DONE | b04c4944-b936-4925-8c72-a37159eff02d |
| M2 | Zod Metadata Validation | Define and enforce Zod schemas at the boundary, stripping malicious payload keys. | M1 | DONE | 0a726816-f2db-4744-afe3-ca9db3e4ddbd |
| M3 | Normalization & Component Registry | Implement `MetadataTransformer` and React Component Registry for generic metadata. | M2 | DONE | 0a726816-f2db-4744-afe3-ca9db3e4ddbd |
| M4 | Heritage Styling Enforcement | Apply Heritage Design System tokens to all metadata elements. | M3 | DONE | 0a726816-f2db-4744-afe3-ca9db3e4ddbd |
| M5 | Final E2E Integration & Verification | Pass 100% of E2E tests, resolve Architectural AI Review, run Forensic Audit. | M4, T_ALL | DONE | 0a726816-f2db-4744-afe3-ca9db3e4ddbd |

### E2E Testing Track
| # | Name | Scope | Dependencies | Status | Conversation ID |
|---|------|-------|-------------|--------|-----------------|
| T1 | E2E Test Infra Setup | Design and establish testing framework/harness. | None | DONE | 37f41beb-ae3a-4a63-9a6b-31172942b5fd |
| T2 | Tier 1 & 2 Test Suite | Feature coverage, boundary, and corner cases tests. | T1 | DONE | 37f41beb-ae3a-4a63-9a6b-31172942b5fd |
| T3 | Tier 3 & 4 Test Suite | Cross-feature combinations and real-world workloads, publishing `TEST_READY.md`. | T2 | DONE | 37f41beb-ae3a-4a63-9a6b-31172942b5fd |

## Interface Contracts
### Client ↔ API Gateway
- All requests must authenticate and include a valid `x-tenant-id` header (or context parameter).
- Core lead IDs must be UUID string format.
- Metadata must be a key-value JSON dictionary structure inside `metadata`.

### Components ↔ Context
- Components requiring `tenant_id` must call `useTenant()` hook instead of receiving props.
