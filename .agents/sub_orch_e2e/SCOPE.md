# Scope: E2E Testing Track

## Architecture
- **E2E Test Runner**: Opaque-box test suite executing tests against the running Next.js server or utilizing lightweight HTTP/HTML verification scripts.
- **Mock Server / API Proxy**: Stubs backend responses for `/api/backend/leads` and other endpoints with custom multi-tenant scenarios.
- **Methodology**: Categorized into 4 Tiers of testing (Feature Coverage, Boundary/Corner, Cross-Feature Combinations, Real-World workloads).

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| T1 | Test Infra Setup | Set up the E2E test runner, routing, mock endpoints/harness, and configuration. | None | PLANNED |
| T2 | Tier 1 & 2 Test Suite | Implement >=5 tests per feature for Tier 1 and Tier 2 (boundary, malicious inputs). | T1 | PLANNED |
| T3 | Tier 3 & 4 Test Suite | Implement Tier 3 (pairwise combinations) and Tier 4 (real-world workflows, e.g. Landscaping lead), producing `TEST_READY.md`. | T2 | PLANNED |

## Interface Contracts
- All E2E tests must be run via `npm run test:e2e` or `node scripts/run-e2e.js`.
- The test harness must accept a custom `x-tenant-id` header/parameter to verify multi-tenant isolation.
