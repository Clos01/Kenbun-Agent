# Service Startup Ordering & Healthchecks

This document explains how Kenbun-Agent ensures reliable startup, even after unattended server reboots.

## Startup Order

```
1. chromadb           (starts immediately)
   ↓ healthcheck: TCP port 8000
2. ollama_server      (starts immediately)
   ↓ healthcheck: "ollama ps"
3. ollama_init        (waits: ollama_server healthy)
   ↓ (pulls models, no healthcheck needed)
4. fastmcp_server     (waits: chromadb healthy + ollama_server healthy)
   ↓ healthcheck: "curl http://localhost:8001/health"
5. dashboard          (waits: fastmcp_server healthy)
   ↓ healthcheck: fetch('http://localhost:3000')
6. dozzle             (starts independently, has healthcheck)
```

## Healthchecks

All services have healthchecks except `ollama_init` (which runs once per startup):

| Service | Healthcheck | Trigger |
|---------|------------|---------|
| **chromadb** | TCP 8000 | Ensures DB is listening (10s start_period) |
| **ollama_server** | `ollama ps` | Ensures inference engine is ready (30s start_period) |
| **fastmcp_server** | HTTP /health | Verifies API + DB + LLM connectivity (45s start_period) |
| **dashboard** | HTTP fetch | Verifies Next.js dev server is live (300s start_period) |
| **dozzle** | `dozzle healthcheck` | Ensures log viewer is running (15s start_period) |

## Why This Matters

**Before:** Services could start in any order. On reboots, fastmcp might come up before Ollama was ready, and it would fail to connect to the LLM.

**After:** Each service waits for its dependencies to be healthy (`service_healthy` conditions). This guarantees:
- ✅ Cold boots work reliably (no race conditions)
- ✅ Unattended reboots recover without manual intervention
- ✅ Health probes detect dead services and trigger `restart: unless-stopped`

## Healthcheck Details

### chromadb
- **Probe:** `nc -z localhost 8000` (netcat TCP check)
- **Why TCP?** ChromaDB runs in a distroless container (no shell, no curl). TCP probes work anywhere.
- **Start period:** 10s (ChromaDB is fast to initialize)

### ollama_server
- **Probe:** `ollama ps` (list loaded models)
- **Why?** The command runs against the local API socket, guaranteeing the server is responsive.
- **Start period:** 30s (model loading can take time)

### fastmcp_server
- **Probe:** `curl http://127.0.0.1:8001/health`
- **Why?** Verifies the Python API server is up AND can reach its dependencies.
- **Start period:** 45s (Python startup + dependency initialization)
- **Key:** Waits for BOTH chromadb and ollama_server to be healthy before starting

### dashboard
- **Probe:** `fetch('http://localhost:3000')` using Node.js
- **Why?** Next.js dev server takes time on first boot (pnpm install, bundling).
- **Start period:** 300s (5 minutes for full npm install on cold start)
- **Key:** Waits for fastmcp_server to be healthy

### dozzle
- **Probe:** Built-in `/dozzle healthcheck` command
- **Why?** Dozzle ships with its own health subcommand.
- **Start period:** 15s (fast startup)
- **Independent:** No explicit dependencies; reads Docker socket directly

## Testing Startup Order

After a clean `docker compose down`:

```bash
# Watch the startup in order
docker compose up

# In another terminal, watch healthchecks update
watch -n 1 docker ps --format "table {{.Names}}\t{{.Status}}"
```

You should see services coming up in this order:
1. chromadb (healthy within 10s)
2. ollama_server (healthy within 30s)
3. ollama_init (runs, exits)
4. fastmcp_server (healthy within 45s, waiting for #1 and #2)
5. dashboard (healthy within 300s, waiting for #4)
6. dozzle (healthy within 15s)

## Troubleshooting Slow Startup

If a service takes longer to become healthy:

```bash
# View healthcheck status
docker ps --format "table {{.Names}}\t{{.Status}}"

# View service logs
docker logs portable_fastmcp      # for fastmcp_server
docker logs portable_dashboard    # for dashboard

# Check what a service is waiting for
docker inspect portable_fastmcp_server | grep -A 20 '"DependsOn"'
```

## Production Deployments

For headless (unattended) servers:
- All services have `restart: unless-stopped` — they recover from crashes
- `docker compose up -d` at boot (e.g., in systemd service or cron @reboot)
- Services wait for their dependencies — no race conditions
- Health probes trigger automatic restarts if needed

Recommended systemd service (`/etc/systemd/system/kenbun-agent.service`):

```ini
[Unit]
Description=Kenbun-Agent
After=docker.service
Requires=docker.service

[Service]
Type=simple
WorkingDirectory=/path/to/kenbun-agent
ExecStart=/usr/bin/docker compose -f docker-compose.yml -f docker-compose.gpu.yml up
ExecStop=/usr/bin/docker compose down
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

(Use `docker compose up` without GPU for CPU-only servers.)

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable kenbun-agent
sudo systemctl start kenbun-agent
```

After a reboot, services will start in the correct order and become healthy automatically.
