# Scope: Implementation Track (Milestones M3 - M5)

## Architecture
- **Tenant Context (`TenantContext`)**: React Context provider storing the current `tenant_id` (UUID format) securely at the root layout of the dashboard. (Completed)
- **Zod validation**: Runs validation at the boundary of component data ingestion (`types.ts` / API layer), stripping out malicious/unknown properties. (Completed)
- **Normalization Layer (`MetadataTransformer`)**: Normalizes raw keys into clean labels with display ordering.
- **Component Registry**: Automatically renders specialized components (dates, currency, booleans, arrays, nested metadata) using Tailwind-styled components.
- **Heritage Design System**: Styles conforming to primary (`#1A1C1E`), secondary (`#6C7278`), tertiary (`#B8422E`), neutral (`#F7F5F2`), and borders/spacing from `DESIGN.md`.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Tenant Context & Refactoring | Refactor data fetching and state to use UUIDs, inject `tenant_id` via secure React Context. | None | DONE |
| M2 | Zod Metadata Validation | Define and enforce Zod schemas at the boundary, stripping malicious payload keys. | M1 | DONE |
| M3 | Normalization & Component Registry | Implement `MetadataTransformer` and React Component Registry for generic metadata. | M2 | IN_PROGRESS |
| M4 | Heritage Styling Enforcement | Apply Heritage Design System tokens to all metadata elements. | M3 | PLANNED |
| M5 | Final E2E Integration & Verification | Pass 100% of E2E tests, resolve Architectural AI Review, run Forensic Audit. | M4 | PLANNED |

## Interface Contracts
- `TenantContext` must export `useTenant` hook to components.
- Incoming lead data must pass through `leadSchema.parse(...)` before being set in React state.
- Component Registry maps types (`date`, `currency`, `boolean`, `string`) to components.
