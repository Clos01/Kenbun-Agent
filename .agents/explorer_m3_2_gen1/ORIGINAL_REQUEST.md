## 2026-07-07T10:52:33Z

You are an Explorer subagent (Archetype: teamwork_preview_explorer) tasked with exploring and formulating an implementation strategy for Milestone 3: Normalization & Component Registry in the Kenbun codebase.

Your working directory is `~/Dev/Kenbun/.agents/explorer_m3_2_gen1`.

## Objective
Analyze the codebase and propose a concrete implementation plan for:
1. **Normalization Layer (`MetadataTransformer`)**:
   - A layer that processes raw custom lead metadata.
   - Maps raw keys to human-readable labels (e.g. `budget` -> "Expected Budget", `permit_num` -> "Permit Number").
   - Defines a standardized visual display ordering for these metadata fields.
2. **Component Registry**:
   - Automatically maps normalized metadata types (e.g. dates, currency, booleans, lists/arrays, strings) to dedicated Tailwind-styled React components conforming to the Heritage Design System tokens.
   - The components should use Framer Motion for premium hover states, sticky/mesh transitions, and reveals.
   - Ensure the leads page (`dashboard/src/app/leads/page.tsx`) correctly integrates these components.

## Tasks
1. Search the workspace to see if there is any existing layout, interface, or file for metadata transformation or component mapping.
2. Propose where to create the `MetadataTransformer` and `Component Registry` files. Suggest exact structures, classes, and types.
3. Propose how the `CustomMetadataBento` component inside `leads/page.tsx` should use this registry to render arbitrary custom fields dynamically and safely.
4. Run ESLint, builds, and E2E tests to check the current health of the repository before any code changes.
5. Save your exploration results, code observations, logic chain, and recommendations in `handoff.md` and `explorer_report.md` inside your working directory.
