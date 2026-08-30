---
name: video-feedback-intelligence
description: Processes client and stakeholder walkthrough videos, extracts audio, generates timestamped transcripts, quotes exact feedback, maps feedback to UI routes and codebase components, and persists insights across Chroma DB, Honcho, and SQLite.
---

# Video Feedback Intelligence & Codebase Grounding Skill

## Overview
When clients, stakeholders, or senior developers record video walkthroughs (e.g. Adrian reviewing NeverMiss AI / Eko-Veritas), this skill ingests the media, extracts verbatim timestamped quotes, categorizes feature/bug requests, maps quotes to concrete React/Next.js/Python files in the target repository, and stores knowledge in the Triple-Memory store.

## CLI Usage
```bash
# Ingest single video file
bin/ingest-feedback-video path/to/adrian_review_1.mp4 --project eko-veritas-prod

# Query indexed feedback
bin/ingest-feedback-video --query "approval feed"

# Check database stats
bin/ingest-feedback-video --stats
```

## Python Sovereign Tool Workflow
```python
from tools.multimodal.video_feedback_transcriber import VideoFeedbackTranscriber
from tools.codebase.codebase_feedback_mapper import CodebaseFeedbackMapper
from tools.memory.feedback_knowledge_store import FeedbackKnowledgeStore

# 1. Transcribe & Decompose
transcriber = VideoFeedbackTranscriber()
video_env = transcriber.process_video("path/to/video.mp4", project_name="eko-veritas-prod")

# 2. Ground to Codebase
mapper = CodebaseFeedbackMapper("/Users/carlosrivas/Dev/Projects/eko-veritas-prod")
grounding_env = mapper.ground_feedback_envelope(video_env["intelligence"])

# 3. Triple-Memory Sync
store = FeedbackKnowledgeStore()
res = store.persist_feedback_envelope(video_env, grounding_env)
```

## Grounding Taxonomy
- **Executive Takeaway**: High-level business and operational intent.
- **Verbatim Timestamped Quotes**: Exact quotes with second-range precision.
- **UI Route Grounding**: Next.js route mapping (`/fleet-overview`, `/voice-agents`, `/call-telemetry`).
- **Codebase Symbol Links**: React components, server actions, and API routes responsible.
- **Proactive Gap Formulations**: Prompts to clarify client intent and bridge technical debt.
