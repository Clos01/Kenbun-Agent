# ADR-001: Hardware Accelerated Console Mirror for Remote Desktop

**Date:** 2026-08-23
**Status:** Accepted

## Context
XRDP standard sessions spawned isolated secondary X servers that had no access to the GPU or physical DISPLAY=:0, causing black screens.

## Decision
Bind x11vnc to DISPLAY=:0 and configure XRDP [console-mirror] proxying to 127.0.0.1:5900. Auto-login configured in GDM3.

## Consequences
Instant 60 FPS remote desktop access over macOS Screen Sharing and Windows App with zero authentication roadblocks.
