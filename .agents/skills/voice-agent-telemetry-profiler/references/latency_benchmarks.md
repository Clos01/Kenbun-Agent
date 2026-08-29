# Voice AI Latency Benchmarking & Tuning Reference

This guide provides optimization specs for conversational Voice AI streaming, WebSockets, and VAD parameters.

---

## 1. Provider Latency Comparison Table

| Pipeline Stage | Recommended Provider | Typical Latency | SLA Target |
|---|---|---|---|
| **Speech-to-Text (STT)** | Deepgram Nova-2 / Whisper Groq | 90ms - 140ms | <120ms |
| **LLM Reasoning** | Gemini 2.0 Flash / Claude 3.5 Haiku / Cerebras | 180ms - 260ms | <220ms |
| **Text-to-Speech (TTS)** | ElevenLabs Flash v2.5 / Cartesia Sonic | 120ms - 180ms | <150ms |
| **Transport & Audio I/O** | Twilio Media Streams / LiveKit WebRTC | 40ms - 80ms | <60ms |

---

## 2. Voice Activity Detection (VAD) Tuning

To prevent voice agents from cutting off users mid-sentence while maintaining swift responsiveness:

```json
{
  "vad_mode": "adaptive",
  "min_silence_duration_ms": 350,
  "prefix_padding_ms": 100,
  "speech_threshold": 0.5,
  "interruption_threshold_words": 2
}
```

- **`min_silence_duration_ms`**: Setting below 250ms causes false interruptions; setting above 500ms makes the agent feel unresponsive. 350ms is optimal.
- **`interruption_threshold_words`**: Avoid triggering cancel/flush on background noise or single filler sounds ("uh-huh").
