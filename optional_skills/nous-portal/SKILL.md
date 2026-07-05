---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [bash, python]
  discovery_required: false
---

# Nous Portal Integration

Nous Portal is a unified subscription gateway and the recommended way to run coding agents. One OAuth login replaces separate accounts, API keys, and billing relationships across multiple model providers, search APIs, image generators, and browser providers.

---

## What's in the Subscription

### 1. Unified Model Catalog (300+ frontier models)
- Access Anthropic (Claude), OpenAI (GPT-5/4), Google (Gemini), DeepSeek, Qwen, Kimi, xAI (Grok), NVIDIA, and more under a single billing account.
- Switch between models mid-session (e.g., `/model anthropic/claude-sonnet-4.6`).

### 2. Nous Tool Gateway
Routing for essential agent actions without registering for separate API accounts:
- **Web Search & Extract:** Firecrawl (agent-grade search and full-page extraction).
- **Image Generation:** FAL (FLUX 2 Pro, Z-Image Turbo, Ideogram V3, Recraft V4 Pro, etc.).
- **Text-to-Speech:** OpenAI TTS (high-quality speech synthesis).
- **Cloud Browser Automation:** Browser Use (headless Chromium sessions).
- **Cloud Terminal Sandbox:** Modal (serverless terminal sandboxes for code execution).

---

## Setup & Onboarding

### One-Command Setup
```bash
kenbun setup --portal
```
This command:
1. Opens your browser to `portal.nousresearch.com` for OAuth login.
2. Stores the refresh token locally at `~/.kenbun/auth.json`.
3. Sets up inference provider settings in `~/.kenbun/config.yaml`.
4. Automatically opts in and turns on the Tool Gateway.

### Adding alongside other providers
If you already have other API keys configured and want to add Nous Portal as a secondary option:
```bash
kenbun model
# Select "Nous Portal" from the list and complete the browser OAuth flow
```

---

## Day-to-Day CLI Usage

```bash
# Onboard and login to Nous Portal
kenbun portal

# Check login status, subscription info, and model/gateway routing
kenbun portal info
kenbun portal status

# View detailed Tool Gateway catalog with per-tool routing
kenbun portal tools

# Open the subscription management page in your browser
kenbun portal open
```

---

## Configuration Reference
After onboarding, your `~/.kenbun/config.yaml` will be structured as follows:

```yaml
model:
  provider: nous
  default: anthropic/claude-sonnet-4.6
  base_url: https://inference-api.nousresearch.com/v1

web:
  backend: nous       # routes web search/extract through Tool Gateway

image_gen:
  provider: nous

tts:
  provider: nous

browser:
  backend: nous
```
*(Note: OAuth refresh tokens are stored separately at `~/.kenbun/auth.json` to keep credentials distinct from configuration).*

---

## Troubleshooting

- **Portal info shows "not logged in":** Run `kenbun portal` or run `kenbun model` and select "Nous Portal" to re-authenticate.
- **Got a "re-authentication required" message:** Your refresh token has been invalidated or expired. Run `kenbun auth add nous` to refresh the session.
- **Model missing from /model selection:** Ensure you use the exact OpenRouter-style slug (e.g. `/model anthropic/claude-opus-4.6`).
