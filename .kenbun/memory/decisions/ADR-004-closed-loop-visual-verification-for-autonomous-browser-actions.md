# ADR-004: Closed-Loop Visual Verification for Autonomous Browser Actions

**Date:** 2026-08-23
**Status:** Accepted

## Context
Open-loop browser automation failed silently when address bar typing truncated URLs, falling back to Google search.

## Decision
Implement Observe-Act-Verify cycle: Hard-clear address bar with Ctrl+L -> Ctrl+A -> Backspace, stream full URL, and query local VLM inspector gate to confirm page arrival before proceeding.

## Consequences
100% reliable browser navigation with automated error recovery.
