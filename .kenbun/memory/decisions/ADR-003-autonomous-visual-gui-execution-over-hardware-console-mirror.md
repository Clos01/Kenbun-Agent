# ADR-003: Autonomous Visual GUI Execution over Hardware Console Mirror

**Date:** 2026-08-23
**Status:** Accepted

## Context
Agent needed to see physical Xorg screen on DISPLAY=:0 without GUI crashes.

## Decision
Attached x11vnc to Quadro GPU dummy plug and launched UI-TARS-2B on port 8090.

## Consequences
Achieved 5.47s visual grounding with 100% accurate coordinate actuation.
