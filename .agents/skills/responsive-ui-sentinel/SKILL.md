---
name: "responsive-ui-sentinel"
description: "Autonomously audits web components, dialogs, drawers, and layouts for viewport width mismatches, 1-word vertical text wrap collapse, and 13-inch laptop (1280px-1440px) scaling issues."
version: "1.0.0"
license: "MIT"
---

# Responsive UI Sentinel

Autonomous Viewport Width, Intrinsic Text Collapse, & 13-Inch Screen Scaling Sentinel.

Version: 1.0.0  
License: MIT

## Purpose

Use this skill whenever creating, modifying, or reviewing web UI components, modals, overlays, or responsive layouts.

This sentinel prevents:
1. **Intrinsic Min-Content Collapse (1-Word Wrapping)**: Prevents flex containers with `items-center` from calculating narrow intrinsic widths on absolute overlays and empty state cards.
2. **13-Inch Screen Oversized Clutter**: Prevents fixed `max-w-[620px]` or `min-h-[460px]` dialogs from overcrowding smaller laptop screens (MacBook Air / Pro 13").
3. **Conflicting Width Rules**: Identifies parents with `overflow-hidden` or missing `min-w-0` that cause horizontal clipping or awkward margins.

---

## When to Activate

- **Pre-Flight UI Verification**: Before marking frontend UI tasks as Complete.
- **Modal & Drawer Audits**: Whenever creating or editing dialogs, drawers, or overlay backdrops.
- **Laptop & Tablet Breakpoint Optimization**: When testing 1280px, 1366px, and 1440px responsive widths.

---

## Tool & CLI Integration

### Standalone CLI Utility (`bin/ui-sentinel`)
```bash
# Scan a project for viewport width issues
bin/ui-sentinel /path/to/project

# Auto-audit active Next.js app
bin/ui-sentinel /Users/carlosrivas/Dev/Projects/eko-veritas-prod
```
