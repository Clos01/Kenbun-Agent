# 🧠 Ensemble Models & Supervisor Defaults

The Kenbun intelligence architecture (System 2) relies on an ensemble of specialized language models rather than a single monolith. This distributed approach allows for specialized auditing, lower latency on edge cases, and reduced token costs.

## Default Ensemble Models (Ollama)

The default ensemble has been updated to match the latest locally hosted Ollama models. 

| Specialization | Default Local Model (Ollama) | Role in System 2 |
| :--- | :--- | :--- |
| **Primary Supervisor** | `llama3.1` | The general orchestrator and reasoning engine. |
| **Code Auditor** | `qwen2.5-coder` | Specialized for deep AST and syntax analysis during the SVE pulse. |
| **Vision/UI Auditor** | `llava` | Analyzes screenshots of the Observatory UI to ensure Heritage Design System compliance. |
| **Adversarial Court** | `mistral-nemo` | Tries to break the Primary Supervisor's logic and checks for edge cases. |

## Timeout Hardening

To prevent infinite hallucination loops or hung API connections, the Supervisor and the Ensemble agents strictly adhere to the following execution timeouts:

- **Local Task Execution Timeout**: `60 seconds`
  *If a local Ollama model fails to respond or process the execution within 60s, the process is killed and automatically retried by the autonomic scheduler.*
- **Cloud Escalation Timeout**: `45 seconds`
  *If a task is escalated to a cloud API (e.g. Gemini or Claude) and fails to return within 45s, the system will instantly failover back to the local ensemble.*

## Configuration

These default models and timeouts are configured in `core/tools/infrastructure/config.py`. Ensure that your local Ollama instance has these models pulled (`ollama pull llama3.1`, etc.) before initiating the orchestrator.
