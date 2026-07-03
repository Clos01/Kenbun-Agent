---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [bash, python, config]
  discovery_required: false
---

# Fallback Providers & Resilience

Configure cross-provider fallbacks and task-specific models to keep agent sessions alive when primary providers encounter rate limits, billing limits, or server drops.

---

## 1. Primary Model Fallback
When your main LLM provider encounters errors — rate limits (HTTP 429), server errors (500/502/503), auth failures (401/403), or not found (404) — the agent can automatically switch to a backup provider and model mid-session.

### Interactive Configuration
```bash
kenbun fallback
```
Use subcommands (`add`, `list`/`ls`, `remove`/`rm`, `clear`) to manage your fallback chain.

### Manual Configuration (in `~/.kenbun/config.yaml`)
Add a top-level `fallback_providers` list containing the preferred fallback model stack:
```yaml
fallback_providers:
  - provider: openrouter
    model: anthropic/claude-sonnet-4
  - provider: nous
    model: nous-hermes-3
  - provider: custom
    model: llama-3.1-70b
    base_url: http://localhost:8000/v1
    key_env: LOCAL_API_KEY
```

---

## 2. When Fallback Triggers
The fallback triggers automatically when the primary model fails. The switch is completely seamless: conversation history, tool calls, and execution contexts are fully preserved.

### Per-Turn Scope
Fallback is turn-scoped: each new user message starts by attempting to restore the primary model. If the primary fails mid-turn, fallback activates for that turn only. This prevents cascading loop failures.

---

## 3. Auxiliary Task Fallback
The agent uses separate, lighter-weight models for side tasks (vision, web extraction, context compression, skills hub, etc.). Each task has its own provider resolution chain that acts as a fallback system.

### Auto-Detection Chain
When an auxiliary task's provider is set to `"auto"`, the fallback path runs as:
`Main provider + main model` → `auxiliary.<task>.fallback_chain` → `fallback_providers` → `built-in discovery chain`

### Configuring Auxiliary Providers (in `~/.kenbun/config.yaml`)
Configure tasks individually:
```yaml
auxiliary:
  vision:
    provider: "auto"              # auto | openrouter | nous | codex | main | anthropic
    model: "openai/gpt-4o"
  web_extract:
    provider: "auto"
    model: "google/gemini-3-flash-preview"
  compression:
    provider: "main"
    model: "google/gemini-3-flash-preview"
    fallback_chain:
      - provider: openrouter
        model: inclusionai/ring-2.6-1t:free
```

#### Direct Endpoint Overrides
Bypass provider resolution entirely by pointing directly to local or custom endpoints:
```yaml
auxiliary:
  vision:
    base_url: "http://localhost:1234/v1"
    api_key: "local-key"
    model: "qwen2.5-vl"
```

---

## Summary of Fallback Mechanisms

| Target | Fallback Mechanism | Config Location |
| :--- | :--- | :--- |
| **Main agent model** | Per-turn failover on errors | `fallback_providers` (top-level list) |
| **Auxiliary tasks ("auto")** | Full auto-detection discovery chain | `auxiliary.<task>.provider: auto` |
| **Auxiliary tasks (explicit)** | Per-task `fallback_chain` → main model | `auxiliary.<task>.fallback_chain` |
| **Delegation** | Provider override only (no auto-fallback) | `delegation.provider` / `delegation.model` |
| **Cron jobs** | Per-job override only (no auto-fallback) | Per-job `provider` / `model` |
