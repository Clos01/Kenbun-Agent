# Gemini API Pricing & Model Research (May 2026)

## 📊 High-Fidelity Model Index

| Model ID | Tier | Status | Pricing (Input/Output per 1M) |
| :--- | :--- | :--- | :--- |
| `gemini-3.1-pro-preview` | Paid | Active | $1.25 / $5.00 |
| `gemini-3.1-flash-lite-preview` | Paid | Active | $0.075 / $0.30 |
| `gemini-3-flash-preview` | Paid | Active | $0.10 / $0.40 |
| **`gemini-2.0-flash-exp`** | **Free** | **Experimental** | **$0.00 / $0.00 (Current Default)** |
| `gemini-2.5-pro` | Paid | Stable | $1.25 / $5.00 |
| `gemini-2.0-flash` | - | Deprecated | $0.10 / $0.40 (Shutting Down) |

## 🚀 Transition Strategy: "The Free-First Swarm"
To minimize operational overhead, the Kenbun Swarm has been transitioned to **Gemini 2.0 Flash (Experimental)** as the primary cloud reasoning layer for System 2 audits.

### Benefits
- **Zero Cost**: Allows for unlimited high-fidelity code reviews and research.
- **Speed**: Flash-tier latency (~1-3s for most audits).
- **Multimodal**: Supports audio transcription (System 6) and image analysis.

### Risks & Mitigations
- **Stability**: Experimental models may be updated without notice.
  - *Mitigation*: The `token_governor.py` and `gemini_reviewer.py` use `os.getenv` fallbacks, allowing for instant hot-swapping back to `gemini-3-flash-preview` if `2.0-exp` becomes unstable.
- **Rate Limits**: Free tier has lower RPM.
  - *Mitigation*: The tiered architecture (System 2 -> Local PC) ensures that if the cloud tier is throttled, the **Local Ensemble** (Gemma 4/Llama 3) handles the workload.

## 📝 Gemini Deep Research (New Capability)
Available in preview. Supports:
- Collaborative planning
- Real-time visualization
- MCP Tool integration (Directly compatible with Kenbun Tools)
- Grounded research with citation mapping

---
*Last updated by Kenbun (System 1 Research) on 2026-05-05.*
