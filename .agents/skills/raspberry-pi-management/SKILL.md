---
name: raspberry-pi-management
description: Use this skill to diagnose, maintain, and update the Raspberry Pi running Pi-hole and to troubleshoot local .lan domain resolution via the LG 2025 reverse proxy.
---

# Raspberry Pi & Network Management

## 1. Network Context
- **Local Domains**: Local services are routed via `.lan` (e.g., `sentry.lan`, `kenbun.lan`), NOT `.alan`.
- **DNS Resolution**: Handled by Tailscale MagicDNS and the Raspberry Pi Pi-hole (`192.168.1.183`).
- **Reverse Proxy**: Located on `LG 2025` (`192.168.1.116` locally, `100.104.211.61` on Tailscale). The `kenbun_reverse_proxy` Docker container routes incoming `.lan` traffic to the appropriate backend service.

## 2. Standard Operating Procedures (SOPs)

### A. Troubleshooting Domain Resolution
If the user complains about a local domain not loading:
1. Verify the exact domain string (often voice-to-text interprets `.lan` as `.alan`).
2. Run `ping <domain>.lan` from the Mac.
3. Check `LG 2025` reverse proxy logs:
   ```bash
   ssh lg2025 "docker logs kenbun_reverse_proxy --tail 50"
   ```

### B. Accessing the Raspberry Pi
The Pi-hole is located at `192.168.1.183`.
1. Use SSH to access the Pi:
   ```bash
   ssh carlos@192.168.1.183
   ```
   *(Note: Verify the correct SSH key or request the password from the user if `Permission denied` occurs).*

### C. Updating Pi-hole & OS
Once SSH access is secured, always perform these steps to ensure the node is secure and ad-blocking is functional:
1. **Update OS**: `sudo apt update && sudo apt upgrade -y`
2. **Update Pi-hole**: `pihole -up`
3. **Update Gravity (Adlists)**: `pihole -g`

### D. Improving Ad-Blocking
If the user is seeing ads, the Pi-hole Adlists need to be augmented:
1. Open the Pi-hole Web UI or edit `/etc/pihole/adlists.list` directly.
2. Add comprehensive lists such as:
   - `https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts`
3. Re-run `pihole -g` to compile the new blocked domains.

### E. Authentication & Credentials
- **SSH Linux User (`carlos@192.168.1.183`)**: The password is `SENTRY_PASSWORD` located in the `Kenbun/.env` file. (Currently: `jyZbJ%ljOC&N%kD5`)
- **Pi-hole Web API**: The password is `PIHOLE_PASSWORD` located in the `Kenbun/.env` file. (Currently: `Kenbun2026$`)
