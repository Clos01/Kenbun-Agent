# 🛰️ Kenbun: Deployment & Swarm Management Guide

This guide outlines the infrastructure and workflows for the **Kenbun Engine**, a high-fidelity, autonomous agentic swarm.

## 🏗️ Core Architecture
- **Sensory Layer (System 6)**: Telegram Voice/Text Bridge via Gemini 3.
- **Orchestrator**: Asynchronous State-Machine (Python 3.11+).
- **Intelligence Layer (System 4)**: Local Bayesian Governor with Remote Fallback.
- **Memory (System 3)**: ChromaDB (Remote) + SQLite (Local).

---

## 🚀 Deployment Steps

### 1. Prerequisites
- Python 3.11+
- FFmpeg (for audio processing)
- Telegram Bot Token (@BotFather)
- Google GenAI API Key (Gemini)

### 2. Environment Setup
Create a `.env` file in the root directory:
```env
TELEGRAM_BOT_TOKEN=your_token_here
GEMINI_API_KEY=your_key_here
PC_IP_ADDRESS=10.0.0.1 (Your remote ChromaDB IP)
CHROMA_PORT=8000
```

### 3. Initialize the Sensory Layer (System 6)
The sensory layer runs as a background daemon:
```bash
# Start the voice listener
python3 tools/infrastructure/swarm_voice.py > /tmp/swarm_voice.log 2>&1 &
```

### 4. Hardware Resonance (System 4)
The engine automatically detects if you are on a restricted network (Mobile Hotspot):
- **Timeout**: 2 seconds.
- **Action**: Auto-fails to local SQLite (`kenbun_intelligence.db`) to prevent hangs.
- **Maintenance**: No manual intervention required.

---

## 🛠️ Swarm Management

### Monitoring the Brain
To see what the swarm is thinking in real-time:
```bash
tail -f /tmp/swarm_voice.log
```

### Resetting the Hivemind
If the logic becomes skewed or the imports hang:
```bash
pkill -9 -f swarm_voice.py
# Verify zero-error state
python3 tools/infrastructure/swarm_voice.py
```

---

## 🛡️ Maintenance & Security
- **POST_MORTEM.md**: Always check this file after a failure to see the architectural fix.
- **STRUCTURE.md**: The technical map for all autonomous agents.
- **Encrypted Secrets**: Use `tools/utils/secret_manager.py` for sensitive keys.

**Kenbun is designed to be mobile-first and resilient. If the cloud fails, the local brain takes over.**
