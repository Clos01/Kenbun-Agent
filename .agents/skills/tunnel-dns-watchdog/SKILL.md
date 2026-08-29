---
name: tunnel-dns-watchdog
description: Diagnoses, maintains, and audits Cloudflare Tunnels (cloudflared), Tailscale subnet routers, Pi-hole DNS sinks, and public reverse proxy endpoints for zero-downtime remote connectivity.
---

# 🌐 Tunnel & DNS Watchdog

The **Tunnel & DNS Watchdog** monitors, diagnoses, and repairs edge networking, Cloudflare Tunnels (`cloudflared`), Tailscale mesh routes, and local `.lan` DNS resolution across self-hosted and cloud infrastructure.

---

## 🎯 When to Activate

Trigger this skill immediately when:
- Deploying or debugging Cloudflare Tunnels (`cloudflared tunnel run <NAME>`).
- Diagnosing public domain connection timeouts or `502 Bad Gateway` / `504 Gateway Timeout` errors on remote domains.
- Setting up or troubleshooting Tailscale subnets, exit nodes, or MagicDNS.
- Resolving DNS resolution failures on `.lan` or reverse proxy hosts.
- Handling dynamic residential/cellular IP changes on carrier subnets.

---

## 🛡️ The 4 Core Networking Diagnostics

### 1. Carrier Outbound Subnet Mismatch
When client IPs shift dynamically on residential/cellular connections, Azure/AWS firewalls drop connections.
- **Diagnosis:** Run `curl -s api.ipify.org` on the host to discover the live outbound public IP.
- **Remediation:** Whitelist the `/16` subnet CIDR block (e.g. `174.245.0.0/16`) in firewall security groups.

### 2. Cloudflare Tunnel Zero-Downtime Heartbeats
Verify tunnel daemon health:
```bash
# Check cloudflared service status
sudo systemctl status cloudflared || launchctl list | grep cloudflared

# Inspect active tunnel connectors
cloudflared tunnel info <TUNNEL_NAME>
```

### 3. Local Reverse Proxy & DNS Resolution
For local development domains (e.g. `kenbun.lan`):
- Verify Pi-hole DNS sink is forwarding requests to the reverse proxy.
- Verify Nginx / Caddy reverse proxy binds `host.docker.internal` or host loopback ports.

---

## 📚 Deep-Dive References
- [references/tunnel_routing_guide.md](references/tunnel_routing_guide.md) — Cloudflare tunnel config templates, Tailscale CLI commands, and DNS health probe scripts.
