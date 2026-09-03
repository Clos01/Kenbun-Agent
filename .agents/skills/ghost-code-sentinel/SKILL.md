---
name: "ghost-code-sentinel"
description: "Autonomously detects, isolates, and purges ghost code, unreachable conditional branches, orphaned React state/hooks, zombie event listeners, dead imports, stale commented-out logic, and phantom variables across TypeScript, Next.js, Python, and JavaScript."
version: "1.0.0"
license: "MIT"
---

# Ghost Code Sentinel

Autonomous detection, AST traversal, and systematic elimination of dead code, orphaned state, zombie handlers, and phantom dependencies.

Version: 1.0.0  
License: MIT

## Purpose

Use this skill whenever auditing codebases before release, refactoring complex components, reviewing pull requests, or preparing code for production builds (`npm run build` / `pytest`).

This skill identifies and purges the 6 core archetypes of **"Ghost Code"**:
1. **Orphaned React State & Hooks**: `useState`, `useRef`, or `useMemo` declarations whose values are mutated or declared but never read in the JSX render tree or lifecycle.
2. **Zombie Event Handlers & Callbacks**: Functions like `handleOldModalSubmit`, `onLegacyClick`, or old debounce wrappers left behind after a UI refactor.
3. **Unreachable Conditional Branches & Dead Gates**: `if (false)`, `if (env === 'mock_legacy')`, or logical conditions whose prerequisites are permanently false.
4. **Phantom Imports & Stale Type Aliases**: Imported symbols, icons, or interfaces that have 0 references in the file.
5. **Ghost Modals & Phantom Overlays**: Modal state variables (`showOldModal`) that remain defined, causing layout calculation bugs or invisible click interception even when unrendered.
6. **Stale Commented-Out Blocks**: Legacy code left commented in files that clutters context and confuses LLM reasoning.

---

## When to Activate

Activate this skill automatically:
- **Pre-Push Validation**: Before merging feature branches or pushing commits to `main`.
- **Post-Refactoring Clean-up**: Immediately after rewriting a component, modal, or API route to ensure old state and helper functions didn't survive as dead code.
- **Bundle & Memory Optimization**: When diagnosing oversized JavaScript bundles, memory leaks, or unneeded re-renders.

---

## Operational Workflow

### 1. AST & Reference Discovery
Scan the modified file or workspace using TypeScript compiler diagnostics (`tsc --noEmit`), ESLint unused variable rules (`@typescript-eslint/no-unused-vars`), and ripgrep identifier lookups.

### 2. The 3-Point Dependency Cross-Check
For every suspected symbol or state variable:
- Point A: Is it imported/declared?
- Point B: Is it mutated/set?
- Point C: Is it read by a consumer (JSX tree, return statement, dependency array, API call)?
*If Point C is FALSE, the symbol is Ghost Code.*

### 3. Surgical Removal & Validation
Remove the dead declaration, its setters, related import statements, and run `npm run build` / `npm test` to verify zero regressions.
