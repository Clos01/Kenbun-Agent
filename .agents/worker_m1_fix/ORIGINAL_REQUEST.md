## 2026-07-07T03:53:43Z
You are Worker 2 (M1 Fix). Your working directory is `~/Dev/Kenbun/.agents/worker_m1_fix`.
Your objective is to fix the issues discovered in Milestone 1 (Tenant Context & Refactoring) to pass the code quality and security reviews.

Input Information:
- Reviewer 1 Report: `~/Dev/Kenbun/.agents/reviewer_m1_1/review_report.md`
- Reviewer 2 Report: `~/Dev/Kenbun/.agents/reviewer_m1_2/handoff.md`
- Forensic Auditor Report: `~/Dev/Kenbun/.agents/auditor_m1/audit_report.md`
- Challenger 2 Report: `~/Dev/Kenbun/.agents/challenger_m1_2/challenger_report.md`

Tasks:
1. **ESLint Cleanliness (Blocker)**:
   - Run `npm run lint` inside the `dashboard/` directory.
   - Resolve the TypeScript lint error in `dashboard/src/app/api_proxy/[...slug]/route.ts` (Unexpected any).
   - Resolve the ESLint warnings/errors concerning calling `setState` directly inside a `useEffect` effect in `dashboard/src/app/settings/page.tsx` and `dashboard/src/app/supervisor/page.tsx` (the `react-hooks/set-state-in-effect` rule). Fix these properly (e.g. wrap the logic or structure state updates correctly).
   - Fix any other typescript or react lint errors in the project so `npm run lint` compiles with ZERO errors/warnings.
2. **Heritage Styling Tokens**:
   - Align the CSS variable definitions under `:root` in `dashboard/src/app/globals.css` with the Heritage Design System tokens defined in `dashboard/DESIGN.md`.
   - Update `--primary` to `#1A1C1E` (Dark Charcoal).
   - Update `--secondary` to `#6C7278` (Slate Gray).
   - Update `--tertiary` to `#B8422E` (Boston Clay).
   - Update `--neutral` to `#F7F5F2` (Matte paper).
   - Make sure that these theme colors are reflected correctly on the Leads dashboard page, rendering text, backgrounds, and borders properly without drift.
3. **Log Injection Mitigation (CWE-117)**:
   - Sanitize `baseRoute` and `slugPath` before logging in `dashboard/src/app/api_proxy/[...slug]/route.ts`. Use a clean regular expression matching pattern (e.g., stripping characters that aren't alphanumeric or safe separators) to prevent log injection.
4. **Hydration Mismatch & Client Validation**:
   - Resolve the hydration mismatch risk in `dashboard/src/context/TenantContext.tsx`. Do not read from `localStorage` during initial state initialization if it causes rendering differences between server-side static/SSR and client hydration. Use `useEffect` to safely hydrate client-specific tenant state from `localStorage` after mounting.
   - Implement strict format validation (UUID check) on the client side when loading/setting the tenant ID, defaulting to `00000000-0000-0000-0000-000000000000` if invalid.
5. **Proxy Header Strictness**:
   - In `dashboard/src/app/api_proxy/[...slug]/route.ts`, if the `x-tenant-id` header is missing, empty, or does not match a valid UUID, block the request and return `400 Bad Request` directly (unless it is a known bypass route like `/api/v1/ping` or `/api/v1/config` that does not require tenant context, but verify leads/data endpoints strictly reject missing headers).

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Output Requirements:
Write `handoff.md` in `~/Dev/Kenbun/.agents/worker_m1_fix/` detailing:
- The exact changes made.
- The output of `npm run lint` and `npm run build` showing clean 100% success.
- Log/Proxy validation test verification evidence.

When done, message the parent (conv ID: 03916b26-dcbd-4b7e-acb3-a1793d59c891) with the path to your handoff report.
