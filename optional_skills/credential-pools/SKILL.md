---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [bash, python, config]
  discovery_required: false
---

# Credential Pools & Rotation

Register multiple API keys or OAuth tokens for the same provider. When one key hits a rate limit or billing quota, the agent automatically rotates to the next healthy key in the pool, keeping sessions alive without switching providers.

> [!NOTE]
> Credential pools handle same-provider rotation (e.g. rotating OpenRouter keys). Fallback providers handle cross-provider failovers. Pools are tried first; if all pool keys are exhausted, fallback providers are activated.

---

## Quick Start
To register multiple credentials for the same provider, run `kenbun auth add` commands:

```bash
# Add a second OpenRouter key
kenbun auth add openrouter --api-key sk-or-v1-your-second-key

# Add a second Anthropic key
kenbun auth add anthropic --type api-key --api-key sk-ant-api03-your-second-key

# Add an Anthropic OAuth credential
kenbun auth add anthropic --type oauth
```

### Check Pool Status
```bash
kenbun auth list
```
*Example Output:*
```
openrouter (2 credentials):
  #1  OPENROUTER_API_KEY   api_key env:OPENROUTER_API_KEY ←
  #2  backup-key           api_key manual
```
*(The `←` marker represents the active credential).*

---

## Interactive Pool Wizard
Run `kenbun auth` with no subcommands to manage credentials interactively:
```bash
kenbun auth
```

---

## Rotation Strategies
Configure rotation strategies in `~/.kenbun/config.yaml`:
```yaml
credential_pool_strategies:
  openrouter: round_robin
  anthropic: least_used
```

### Available Strategies:
- **`fill_first`** (Default): Use the first healthy key until exhausted, then move to the next.
- **`round_robin`**: Cycle through keys evenly, rotating after each request.
- **`least_used`**: Always pick the key with the lowest total request count.
- **`random`**: Random selection among healthy keys.

---

## Error Recovery Details

| Error Type | Trigger | Cooldown Period |
| :--- | :--- | :--- |
| **429 Rate Limit** | Retry same key once. Rotate to next key on second consecutive 429. | 1 hour |
| **402 Billing/Quota**| Immediately rotate to the next key. | 24 hours |
| **401 Auth Expired** | Attempt OAuth token refresh. Rotate only if refresh fails. | N/A |

---

## Custom Endpoint Pools
Custom OpenAI-compatible endpoints (e.g., Together.ai, RunPod, local servers) get their own pools, keyed by their endpoint name:
```bash
kenbun auth add Together.ai --api-key sk-together-second-key
```

---

## Delegation & Subagent Sharing
When parent agents spawn subagents, the parent's active credential pool is automatically inherited by children. Per-task credential leasing ensures concurrent child runs do not conflict when rotating keys.
