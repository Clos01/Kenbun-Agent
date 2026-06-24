---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [bash, python, config]
  discovery_required: false
---

# AI Inference Providers Setup

This page covers configuring inference providers for the agent — from cloud APIs like OpenRouter and Anthropic, to self-hosted endpoints like Ollama and vLLM, to advanced routing and fallback configurations.

---

## Supported Providers & Setup Commands

| Provider | Setup Method | Environment Variable (in `~/.hermes/.env`) |
| :--- | :--- | :--- |
| **Nous Portal** | `hermes model` (OAuth) | *None (managed via auth.json)* |
| **OpenAI Codex** | `hermes model` (OAuth device code) | *None (managed via auth.json)* |
| **GitHub Copilot** | `hermes model` (OAuth device code) | `COPILOT_GITHUB_TOKEN` or `GH_TOKEN` |
| **Anthropic (Native)** | `hermes model` (OAuth / API Key) | `ANTHROPIC_API_KEY` |
| **OpenRouter** | Manual config | `OPENROUTER_API_KEY` |
| **DeepSeek** | Manual config | `DEEPSEEK_API_KEY` |
| **Google Gemini** | Manual config | `GOOGLE_API_KEY` or `GEMINI_API_KEY` |
| **OpenAI API (direct)**| Manual config | `OPENAI_API_KEY` |
| **AWS Bedrock** | `hermes model` | Uses standard AWS SDK (`boto3`) auth chain |
| **Azure AI Foundry** | `hermes model` | *Uses Azure endpoint credentials* |
| **Ollama Cloud** | `hermes model` | `OLLAMA_API_KEY` |
| **NovitaAI** | Manual config | `NOVITA_API_KEY` |
| **z.ai / GLM** | Manual config | `GLM_API_KEY` |
| **Kimi / Moonshot** | Manual config | `KIMI_API_KEY` or `KIMI_CN_API_KEY` |
| **xAI (Grok)** | `hermes model` (OAuth / API Key) | `XAI_API_KEY` |
| **NVIDIA NIM** | Manual config | `NVIDIA_API_KEY` |
| **Hugging Face** | Manual config | `HF_TOKEN` |
| **StepFun** | Manual config | `STEPFUN_API_KEY` |

---

## Model Management Commands

Use these commands to configure or switch models/providers:
- **`hermes model`** (Run in terminal, outside active session): Full setup wizard. Use this to add new providers, register API keys, or authenticate via OAuth.
- **`/model`** (Type inside active chat session): Quick-switch between already-configured models and providers.
  *Example:* `/model openrouter:anthropic/claude-sonnet-4.6`

---

## Custom & Self-Hosted LLM Providers
Any API implementing the OpenAI `/v1/chat/completions` endpoint can be wired into the agent.

### General Configuration (in `~/.hermes/config.yaml`)
```yaml
model:
  default: your-custom-model-name
  provider: custom
  base_url: http://localhost:8000/v1
  api_key: your_key_or_leave_empty
```

### Self-Hosted Integrations

#### 1. Ollama (Local)
Best for offline use and privacy. Start the server on port `11434`:
```bash
ollama serve
ollama pull qwen2.5-coder:32b
```
> [!WARNING]
> Ollama defaults to small context windows (often 4,096 tokens). The agent requires at least **64,000 tokens** of context for tool routing.
> Enforce this by setting: `export OLLAMA_CONTEXT_LENGTH=64000` before running `ollama serve`, or baking it into a custom Modelfile:
> ```dockerfile
> FROM qwen2.5-coder:32b
> PARAMETER num_ctx 64000
> ```

#### 2. vLLM (High-Performance GPU serving)
Launch the API server with tool-calling capabilities:
```bash
vllm serve meta-llama/Llama-3.1-70B-Instruct \
  --port 8000 \
  --max-model-len 65536 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes
```

#### 3. SGLang
Launch the inference engine with prefix caching enabled:
```bash
python -m sglang.launch_server \
  --model meta-llama/Llama-3.1-70B-Instruct \
  --port 30000 \
  --context-length 65536 \
  --tool-call-parser qwen
```

#### 4. llama.cpp / llama-server
Run GGUF quants on CPU or Apple Silicon:
```bash
./build/bin/llama-server \
  --jinja -fa \
  -c 64000 \
  -ngl 99 \
  -m models/qwen2.5-coder-32b-instruct-Q4_K_M.gguf \
  --port 8080
```
