# 🤖 n8n Workflow Deployment (Target Server: p330)

This document maps the deployment configuration for running a secure **n8n** automation instance on the **p330** target server.

---

## 1. Run n8n Locally
The n8n service runs containerized on the **p330** server (typically binding to port `5678`). In the Docker compose stack, configure n8n with the crucial environment variable to handle public webhook callback signatures:

```env
WEBHOOK_URL=https://n8n.yourdomain.com/
```

---

## 2. Configure Cloudflare Tunnel (`cloudflared`)
Run the Cloudflare Tunnel daemon (`cloudflared`) as a sidecar container in the same Docker network stack on the **p330** host.

1. In the **Cloudflare Zero Trust Dashboard**, create a new tunnel and link it to your domain.
2. Route a public subdomain (e.g., `n8n.yourdomain.com`) through the tunnel to the local service:
   * **Service Type**: `HTTP`
   * **URL**: `http://localhost:5678` (or `http://n8n:5678` if using Docker bridge service names)

---

## 3. Secure the Dashboard (Cloudflare Access)
To protect your workflows from unauthorized access while allowing third-party API webhook payloads to pass through:

*   **Protect the Admin UI**: Set up an Access Policy requiring email PIN verification, Google, or GitHub login for the main path:
    ```path
    n8n.yourdomain.com/
    ```
*   **Exempt Webhooks (Bypass)**: Create a bypass rule specifically for n8n's webhook URL patterns so external APIs can trigger workflows without auth blocks:
    ```path
    n8n.yourdomain.com/webhook/*
    ```

Once deployed, you can securely access n8n's visual builder from anywhere at `https://n8n.yourdomain.com` without exposing raw ports to the public internet.
