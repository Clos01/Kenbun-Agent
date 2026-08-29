## 2026-07-07T11:18:09Z
You are worker_m3_1. Your working directory is ~/Dev/Kenbun/.agents/worker_m3_1.
Your task is to implement Milestone 3 (Normalization & Component Registry) for the Kenbun dashboard.

Input/Blueprints:
- Proposed MetadataTransformer blueprint: ~/Dev/Kenbun/.agents/explorer_m3_1_gen1/proposed_metadataTransformer.ts
- Proposed MetadataRegistry component blueprint: ~/Dev/Kenbun/.agents/explorer_m3_1_gen1/proposed_MetadataRegistry.tsx
- Proposed leads page integration patch: ~/Dev/Kenbun/.agents/explorer_m3_1_gen1/proposed_leads_page.patch

Detailed Steps:
1. Create `dashboard/src/lib/metadataTransformer.ts` based on the blueprint in `~/Dev/Kenbun/.agents/explorer_m3_1_gen1/proposed_metadataTransformer.ts`.
2. Create `dashboard/src/components/MetadataRegistry.tsx` based on the blueprint in `~/Dev/Kenbun/.agents/explorer_m3_1_gen1/proposed_MetadataRegistry.tsx`.
3. Integrate the Metadata Registry into `dashboard/src/app/leads/page.tsx` using the logic in `~/Dev/Kenbun/.agents/explorer_m3_1_gen1/proposed_leads_page.patch`. Make sure to import `MetadataTransformer` and `METADATA_COMPONENTS` / `ListCard`, and replace the hardcoded metadata display inside the `CustomMetadataBento` component with a dynamic loop over transformed fields. Ensure all required imports (e.g. `AnimatePresence`, `motion`, React hooks) are correct.
4. Ensure all UI/UX components generated strictly inherit and adhere to the Heritage Design System tokens (primary `#1A1C1E`, secondary `#6C7278`, tertiary `#B8422E`, neutral Limestone `#F7F5F2`, card background `#FFFFFF`, custom margins and rounded classes, and typography).
5. Load the modern-web-guidance skill at `~/Dev/Kenbun/.agents/skills/modern-web-guidance/SKILL.md` to guide modern React, Tailwind, and Framer Motion styling patterns.
6. Run `npm run lint` and `npm run build` in the `dashboard` directory and ensure it builds successfully.
7. Run `npm run test:e2e` in the `dashboard` directory and verify that 100% of E2E tests pass.
8. Write a detailed `handoff.md` file in your working directory (`~/Dev/Kenbun/.agents/worker_m3_1/handoff.md`) detailing the files created/modified, the commands run, and their exact outputs (compilation, lint, E2E tests).

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT
hardcode test results, create dummy/facade implementations, or
circumvent the intended task. A Forensic Auditor will independently
verify your work. Integrity violations WILL be detected and your
work WILL be rejected.
