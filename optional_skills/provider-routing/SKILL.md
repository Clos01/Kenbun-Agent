---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [bash, config]
  discovery_required: false
---

# OpenRouter Provider Routing

Configure fine-grained control over which underlying AI providers (e.g., Anthropic, Google, AWS Bedrock, Together AI) handle your OpenRouter requests and how they are prioritized. Provider routing lets you optimize for cost, speed, quality, or enforce specific data privacy requirements.

> [!NOTE]
> Provider routing only applies when using OpenRouter. It has no effect with direct provider connections (such as connecting directly to the Anthropic API).

---

## Configuration
Add a `provider_routing` section to your `~/.kenbun/config.yaml`:

```yaml
provider_routing:
  sort: "price"           # How to rank providers ("price" | "throughput" | "latency")
  only: []                # Whitelist: only use these providers (leave empty for all)
  ignore: []              # Blacklist: never use these providers
  order: []               # Explicit provider priority order
  require_parameters: false  # Only use providers that support all request parameters
  data_collection: null   # Control training data collection ("allow" or "deny")
```

---

## Routing Options

### 1. sort
Controls how OpenRouter ranks available providers for your request.
- **`price`:** Cheapest provider first.
- **`throughput`:** Fastest tokens-per-second first.
- **`latency`:** Lowest time-to-first-token first.

### 2. only
Whitelist of provider names. When set, only these providers will be used.
```yaml
provider_routing:
  only:
    - "Anthropic"
    - "Google"
```

### 3. ignore
Blacklist of provider names. These providers will never be used.
```yaml
provider_routing:
  ignore:
    - "Together"
    - "DeepInfra"
```

### 4. order
Explicit priority order. Providers listed first are preferred. Unlisted providers are used as fallbacks.
```yaml
provider_routing:
  order:
    - "Anthropic"
    - "Google"
    - "AWS Bedrock"
```

### 5. require_parameters
When set to `true`, OpenRouter will only route to providers that support all parameters in your request (like temperature, top_p, tools, etc.) to prevent silent parameter drops.

### 6. data_collection
Controls whether providers can use your prompts for training. Options are `"allow"` or `"deny"`.

---

## Practical Examples

### Optimize for Cost
```yaml
provider_routing:
  sort: "price"
```

### Optimize for Speed / Latency
```yaml
provider_routing:
  sort: "latency"
```

### Lock to Specific Providers & Opt Out of Training
```yaml
provider_routing:
  only:
    - "Anthropic"
  data_collection: "deny"
```

### Preferred Order with Fallbacks
```yaml
provider_routing:
  order:
    - "Anthropic"
    - "Google"
  require_parameters: true
```

---

## How It Works
Provider routing preferences are passed to the OpenRouter API via the `extra_body.provider` field on every API call. This applies to both CLI sessions and local gateway servers.
The routing configurations are mapped directly into the internal AI agent initialization settings:
- `providers_allowed`
- `providers_ignored`
- `providers_order`
- `provider_sort`
- `provider_require_parameters`
- `provider_data_collection`
