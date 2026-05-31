# 🩺 System Post Mortems & Architectural Corrections

This document records technical failures, root causes, security remediations, and lessons learned to prevent regression and inform future Swarm operations.

---

## 1. 🚨 Portainer CE v2.21.5 GitOps Deployment Failure

### Incident Summary
Deploying the multi-container stack inside Portainer CE `2.21.5` failed with a generic `Failure: Failed redeploying stack` parser error, locking the environment.

### Root Cause
Portainer's legacy internal YAML parser does not support the modern nested `env_file:` syntax with `path:` and `required: false` parameters. 

### Architectural Resolution
Reverted the `env_file` block in `docker-compose.yml` to the standard, highly compatible flat list syntax:
```yaml
    env_file:
      - .env
```
We also documented a persistent, non-root multi-stage caching blueprint inside `sprint_2_senior_version.md` to prevent local file permission pollution and dependency drift.

---

## 2. 🛡️ Network Boundary Exposure (CORS Wildcard)

### Incident Summary
FastAPI backend was configured with wildcard origins `allow_origins=["*"]` while using `allow_credentials=True`.

### Root Cause
This configuration violated standard CORS specifications (credentials cannot be paired with wildcard origins in modern browsers) and exposed the local system to CSRF and DNS-rebinding attacks.

### Architectural Resolution
Replaced wildcard origins with explicit whitelisting in `api_server.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=build_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
```
Origins are now dynamically constructed and sanitized strictly from Tailscale, Docker host, and verified localhost IPs.

---

## ⚙️ 3. Configuration Cache Desync (Stale Hot-Reloads)

### Incident Summary
Modifying configuration variables via `/api/v1/config` wrote updates successfully to `.env` but changes failed to apply in-memory without a physical container reboot.

### Root Cause
The Pydantic Settings instance was initialized globally at boot, and subsequent imports from `config.py` referenced the stale cached settings object. Pydantic’s `get_settings()` loader used `@lru_cache`, which was never cleared on POST updates.

### Architectural Resolution
1. Added key validation checking incoming keys against Pydantic's `settings.model_fields.keys()` to completely block arbitrary `os.environ` injection attempts.
2. Triggered class-level Pydantic verification *prior* to committing any changes to disk or process memory to ensure type-safety.
3. Added cache eviction `get_settings.cache_clear()` and mapped validated parameters dynamically directly to the imported global `settings` instance in memory. Config edits now apply instantly across all active modules.

---

## 📈 4. Telemetry Latency & Lock Contention (TokenGovernor)

### Incident Summary
Under concurrent LLM execution, background agents experienced severe latency, database timeouts, and telemetry read timeout exceptions.

### Root Cause
`TokenGovernor` performed synchronous disk reading, JSON parsing, and process file-locking of `usage_stats.json` on *every single LLM request*, creating massive thread and process blockages.

### Architectural Resolution
Implemented an atomic double-checked lock-free memory cache in `TokenGovernor` with a **1-second TTL (Time-To-Live)**:
* Monotonic clock checking (`time.monotonic()`) intercepts read requests and serves them from cache without acquiring locks.
* Telemetry writes bypass the cache, acquire exclusive RLock synchronization, atomically save using `tempfile.NamedTemporaryFile` with strict `0600` POSIX permissions, directory-level `fsync` flush operations, and update the cache instantly.
* Enforced per-access path validation to defeat TOCTOU directory attacks.
* Implemented a fail-closed architecture to secure spending if disk I/O fails.

---

## 🔌 5. Database Connection Failures (ChromaDB Client Caching)

### Incident Summary
If the remote `chromadb` container restarted or dropped offline, the Python API crashed downstream with unhandled connection errors.

### Root Cause
`get_chroma_client()` permanently cached a single `chromadb.HttpClient` instance and never verified if the connection remained healthy or active.

### Architectural Resolution
1. Refactored `get_chroma_client()` to run a fast TCP ping using socket context managers and a lightweight `.heartbeat()` call on the cached client.
2. Implemented a self-healing recovery loop: if the heartbeat fails, the client is dropped and the system falls back to a localized `PersistentClient` archive.
3. Throttled re-connection attempts to the remote database to a 30-second interval to prevent connection stampedes and socket exhaustion on thread-heavy server configurations.
4. Set `allow_reset=False` to securely disable remote database unauthenticated resets.

---

## 🏛️ Permanent Lessons Learned for Swarm Operations

1.  **Stick to Flat YAML Declarations:** To ensure maximum deployment compatibility across Portainer, Kubernetes, and legacy orchestrators, always use standard flat lists for environment file arrays.
2.  **Never Pair Wildcards with Credentials:** Standardize explicit whitelisting in FastAPI/Next.js integrations. Sanitizing origins at boot is mandatory to preserve API security.
3.  **Avoid High-Frequency Disk I/O:** Any configuration or telemetry stats check must use short-TTL memory caching inside high-speed async environments to prevent IO bottlenecks.
4.  **Always Probe Cached Connections:** Never assume a cached network client is permanently online. Wrap remote connections in cheap, non-blocking heartbeat checks and throttled recovery fallback loops.
