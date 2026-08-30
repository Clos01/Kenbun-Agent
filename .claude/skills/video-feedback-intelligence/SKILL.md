---
name: video-feedback-intelligence
description: Processes client video walkthroughs, extracts transcripts and quotes, grounds feedback to codebase files and UI routes, and persists knowledge across SQLite, Chroma, and Honcho.
---

# Video Feedback Intelligence & Codebase Grounding Skill

## Overview
Automates the extraction of client video feedback into structured engineering insights, linking spoken critiques to source code files and Next.js routes.

## Terminal CLI
```bash
bin/ingest-feedback-video <video_path> [--project <name>]
bin/ingest-feedback-video --query "<term>"
bin/ingest-feedback-video --stats
```

## Grounding Taxonomy
1. **Verbatim Spoken Quotes**: Captured with exact timestamp ranges.
2. **UI Route & Tab Grounding**: Links user speech to active screens (`/fleet-overview`, `/voice-agents`, `/call-telemetry`).
3. **AST Codebase Dictionary**: Locates exact files, functions, and components in the target repo.
4. **Triple-Memory Persistence**: SQLite relational store + Chroma vector embeddings + Honcho memory.
