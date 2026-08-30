---
name: voice-agent-telemetry-profiler
description: Benchmarks and diagnoses conversational Voice AI latency, Time-to-First-Audio (TTFA), WebSocket streaming jitter, SIP trunk connectivity, and audio chunk buffering across ElevenLabs, Twilio, LiveKit, and Deepgram.
---

# 🎙️ Voice Agent Telemetry Profiler

The **Voice Agent Telemetry Profiler** diagnoses, benchmarks, and optimizes real-time conversational Voice AI pipelines to achieve **sub-800ms end-to-end conversational turn-taking latency**.

---

## 🎯 When to Activate

Trigger this skill immediately when:
- Designing or debugging conversational Voice AI architectures (ElevenLabs, Twilio, LiveKit, Deepgram, Vapi, Retell).
- Investigating high turn-taking delays or awkward silence (>1200ms).
- Diagnosing choppy audio, WebSocket disconnections, or packet jitter.
- Auditing SIP trunk routing, Twilio Media Streams, and WebSocket payload sizing.
- Implementing Voice Activity Detection (VAD) and interruption handling.

---

## ⚡ The Voice Latency Budget SLA (<800ms Total)

```text
┌─────────────────────────────────────────────────────────────┐
│ 🎙️ TOTAL END-TO-END CONVERSATIONAL TURN BUDGET: 800ms       │
├─────────────────┬───────────────────┬───────────────────────┤
│ Stage 1: VAD    │ Voice Stop Detect │ 150ms - 200ms         │
│ Stage 2: STT    │ Audio -> Text     │ 100ms - 150ms         │
│ Stage 3: LLM    │ First Token (TTFT)│ 200ms - 250ms         │
│ Stage 4: TTS    │ First Audio (TTFA)│ 150ms - 200ms         │
│ Stage 5: Audio  │ Stream Playback   │ 50ms                  │
└─────────────────┴───────────────────┴───────────────────────┘
```

---

## 🛡️ Core Optimization Rules

### 1. Token-to-Audio Streaming Pipeline
Never wait for the LLM to complete its full response before triggering Text-to-Speech (TTS). Pipe LLM token chunks sentence-by-sentence or by clause boundaries (`.`, `?`, `!`, `,`):
```python
# Stream tokens into TTS chunk buffer
buffer = ""
async for token in llm_stream:
    buffer += token
    if any(buffer.endswith(punct) for punct in [". ", "? ", "! ", ",\n"]):
        await tts_client.send_text(buffer)
        buffer = ""
```

### 2. Audio Format Sizing
For telephony (Twilio/LiveKit SIP), use raw `μ-law 8kHz` (Mulaw) or `PCM 16kHz` to eliminate transcoding overhead.

### 3. Server Proximity
Deploy voice bridge servers in the same cloud region as the voice provider (e.g. AWS `us-east-1` for ElevenLabs / Twilio).

---

## 📚 Deep-Dive References
- [references/latency_benchmarks.md](references/latency_benchmarks.md) — TTFA breakdown, WebSocket audio chunking configurations, and VAD tuning parameters.
