---
name: cluster-hardware-topology
description: Resolves and audits multi-node cluster physical hardware locations (LG 2025 Legion PC vs P330 ThinkStation Tiny vs Local Mac vs Legion Sentry Pi-hole). Guarantees all agent communication uses exact physical machine names instead of ambiguous raw IP addresses.
---

# 🖥️ Cluster Hardware Topology & Node Sentinel

The **Cluster Hardware Topology** skill provides dynamic, non-hardcoded resolution of all physical nodes, virtual machines, and network endpoints across the Kenbun sovereign multi-node home-lab cluster.

---

## 🎯 Mandatory Communication Rule

Whenever communicating database health, server statuses, container deployments, or network connectivity to the operator (Carlos), the Swarm **MUST NEVER** use ambiguous phrases like "the remote PC" or naked IP addresses like `100.104.211.61` without identifying the physical hardware node.

Always dynamically resolve and state the exact machine:
* **LG 2025 (Legion PC)** — Windows 11 / WSL2, Tailscale `100.104.211.61` / `100.92.127.1`. Hosts PostgreSQL (:5432), LM Studio (RTX 5070 :2065), and Nginx wildcard SSL proxy (:443).
* **P330 (ThinkStation Tiny)** — Lenovo ThinkStation P330 SFF, Tailscale `100.100.199.127`. Hosts Proxmox / Ubuntu, n8n automations (:5678), Planka (:1337), and RTX 4090 / CPU Ollama embeddings.
* **Local Mac (Workstation)** — Apple Silicon development host (`localhost` / `127.0.0.1`). Hosts FastMCP server (:8001), Next.js dashboard (:3000), and local SQLite fallback (`brain_health/kenbun_intelligence.db`).
* **Legion Sentry (Raspberry Pi)** — Dedicated Pi-hole DNS sinkhole (`192.168.1.183` / `100.102.104.66`) resolving local `.lan` hostnames.

---

## 🛠️ Dynamic Node Resolution Usage

To look up any node dynamically from Python without hardcoding:

```python
from pathlib import Path
import sys

# Import the dynamic resolver
skill_dir = Path(".agents/skills/cluster-hardware-topology")
if str(skill_dir) not in sys.path:
    sys.path.insert(0, str(skill_dir))

from resolver import resolve_hardware_node, format_node_label

# Resolve an IP or service
node = resolve_hardware_node("100.104.211.61")
print(node["display_name"])  # "LG 2025 (Legion PC)"
print(node["hardware_type"]) # "Lenovo Legion Gaming PC (Windows 11 / WSL2)"
```

---

## 🔄 Updating Cluster Inventory

The physical inventory is maintained in `cluster_inventory.json` in this skill directory.
When physical machines are added, network leases change, or new services are assigned, update `cluster_inventory.json` to keep all Swarm agents in sync with zero code modifications.
