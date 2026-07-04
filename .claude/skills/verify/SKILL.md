---
name: verify
description: Verify the deployed Kenbun stack on lg2025 actually works — drive Honcho memory write path, check container fleet, probe the API surface. Use after config/compose changes or when asked "is kenbun working".
---

# Verifying the Kenbun stack (lg2025)

The stack runs remotely: compose project at `/home/carlos/Kenbun` on host `lg2025`
(ssh alias works from the Mac). All portable_* containers share the tailscale
container's network namespace — from inside any of them, every service is on
`localhost` (ollama :11434, honcho :8006, chroma :8000, fastmcp :8001).
The server's `.env` DIFFERS from the Mac repo's — never overwrite it; edit in place.

## Fleet health (30s)

```bash
ssh lg2025 'docker ps --format "{{.Names}}\t{{.Status}}" | sort'
```
Known-unhealthy that is NOT a regression: `samba` (healthcheck timeout too tight; service works).
"Healthy" containers can still be cognitively broken — always drive a real flow.

## Honcho memory write path (the flow that matters, ~3 min)

`DERIVER_FLUSH_ENABLED=true` is set (since 2026-07-04), so any message batch
derives immediately. If flush is ever disabled, Honcho gates derivation until a
session accumulates >= 1024 tokens (`REPRESENTATION_BATCH_MAX_TOKENS`) and
smaller ingests queue forever.

```bash
# 1. baseline
ssh lg2025 'docker exec portable_honcho_database psql -U postgres -d postgres -t -c \
  "SELECT count(*) filter (where embedding is not null), count(*) FROM documents;"'

# 2. post a >1024-token message (sessions/peers/workspaces get-or-create implicitly)
ssh lg2025 'docker exec portable_honcho_api /app/.venv/bin/python -c "
import json, urllib.request
text = \"<distinct factual sentences about a test peer> \" * 20
req = urllib.request.Request(\"http://localhost:8006/v3/workspaces/config-smoke-test/sessions/<fresh-name>/messages\",
  data=json.dumps({\"messages\": [{\"peer_id\": \"carlos-test\", \"content\": text}]}).encode(),
  headers={\"Content-Type\": \"application/json\"}, method=\"POST\")
print(urllib.request.urlopen(req, timeout=30).status)  # expect 201
"'

# 3. wait ~100s (llama3.2:3b derivation takes ~25-30s once claimed; poll backoff max 30s)
#    then re-run the baseline query: count must GROW and with_embedding == total.
#    Deriver evidence: docker logs portable_honcho_deriver | grep -i "observation count"
```

If count doesn't grow: check `queue` table (`processed=false` rows) and sum
tokens per work unit — under 1024 means gated, not broken:
```sql
SELECT q.work_unit_key, sum(m.token_count) FROM queue q
  JOIN messages m ON q.message_id = m.id WHERE NOT q.processed GROUP BY 1;
```
Save failures are swallowed: item marked processed, error only in deriver logs.

## Model wiring gotchas

- Honcho ignores unknown env vars silently (`extra="ignore"`). Real knobs:
  `LLM_OPENAI_API_KEY/BASE_URL`, `{DERIVER,SUMMARY}_MODEL_CONFIG__MODEL`,
  `DREAM_{DEDUCTION,INDUCTION}_MODEL_CONFIG__MODEL`,
  `DIALECTIC_LEVELS__<lowercase>__MODEL_CONFIG__MODEL`,
  `EMBEDDING_MODEL_CONFIG__{MODEL,DIMENSIONS_MODE,OVERRIDES__BASE_URL}`.
- Embeddings do NOT inherit `LLM_OPENAI_BASE_URL` — separate override required.
  Current: qwen3-embedding:4b truncated to 1536 (schema dim) via Ollama.
- `.env` secrets are `enc:`-encrypted; only kenbun core decrypts them. Honcho
  and other third-party containers cannot use them.
- Dialectic chat runs on qwen3:8b (all 5 levels) — llama3.2:3b was too weak
  for the tool loop (emitted tool calls as literal text). Deriver/summary/dream
  stay on llama3.2:3b. First chat after idle swaps models in Ollama (~30-60s).

## Other surfaces

- Honcho from the Mac (user-facing): `curl http://100.92.127.1:8006/health` → `{"status":"ok"}`
- fastmcp (kenbun-swarm MCP): `ssh lg2025 'docker exec portable_fastmcp curl -fsS http://127.0.0.1:8001/health'`
- New python deps in `pyproject.toml` need BOTH: scp pyproject.toml to the
  server (it is NOT a git repo — scp is the deploy mechanism) AND
  `docker compose build fastmcp_server && up -d fastmcp_server`
  (bit us with pypdf, 2026-07-04).
- `samba` healthcheck times out (15s too tight) but the service works
  (`smbclient -L` lists shares instantly); managed outside this compose file.

## Deploy

```bash
scp docker-compose.remote.yml lg2025:/home/carlos/Kenbun/
ssh lg2025 'cd /home/carlos/Kenbun && docker compose -f docker-compose.remote.yml up -d honcho_api honcho_deriver'
# verify env landed: docker exec portable_honcho_deriver env | grep EMBEDDING
```
