# Cloudflare Tunnel & Tailscale Routing Guide

This guide provides configurations and diagnostic workflows for edge tunnels, reverse proxies, and Tailscale mesh routing.

---

## 1. Cloudflare Tunnel Configuration (`config.yml`)

```yaml
tunnel: <TUNNEL_UUID>
credentials-file: /etc/cloudflared/<TUNNEL_UUID>.json

ingress:
  # Next.js Dashboard
  - hostname: dashboard.domain.com
    service: http://localhost:3000
    originRequest:
      noTLSVerify: true
      connectTimeout: 10s

  # FastAPI Backend
  - hostname: api.domain.com
    service: http://localhost:8000
    originRequest:
      connectTimeout: 15s

  # Catch-all 404
  - service: http_status:404
```

---

## 2. Tailscale Subnet Router Setup

To route traffic to local LAN subnets without installing Tailscale on every device:

```bash
# 1. Enable IP forwarding on Linux host
echo 'net.ipv4.ip_forward = 1' | sudo tee -a /etc/sysctl.d/99-tailscale.conf
sudo sysctl -p /etc/sysctl.d/99-tailscale.conf

# 2. Advertise subnet
sudo tailscale up --advertise-routes=192.168.1.0/24 --accept-routes

# 3. Approve routes in Tailscale Admin Console
```
