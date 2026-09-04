"""Dynamic cluster hardware topology resolver.

Maps IP addresses, hostnames, and services to human-friendly physical hardware node names
(e.g., 'LG 2025 (Legion PC)' vs 'P330 (ThinkStation Tiny)' vs 'Local Mac (Workstation)').
Dynamic: Reads directly from cluster_inventory.json and environment configuration without hardcoding.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

INVENTORY_FILE = Path(__file__).parent / "cluster_inventory.json"


def load_inventory() -> Dict[str, Any]:
    """Loads the cluster inventory dynamically from JSON."""
    if not INVENTORY_FILE.exists():
        return {"nodes": {}}
    try:
        with open(INVENTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"nodes": {}}


def resolve_hardware_node(query: str) -> Dict[str, Any]:
    """Resolves an IP, hostname, or service key to its physical hardware node.

    Args:
        query: IP address (e.g. '100.104.211.61'), hostname ('lg2025.tailbe4852.ts.net'),
               node key ('lg2025', 'p330'), or service name ('postgres', 'n8n').

    Returns:
        Dict with node details:
            - node_key: str
            - display_name: str
            - hardware_type: str
            - roles: list[str]
            - matched_by: str
    """
    if not query:
        return {
            "node_key": "unknown",
            "display_name": "Unknown Node",
            "hardware_type": "Unspecified Hardware",
            "roles": [],
            "matched_by": "empty_query",
        }

    inventory = load_inventory()
    nodes = inventory.get("nodes", {})
    clean_q = str(query).strip().lower()

    # 1. Direct node key match
    if clean_q in nodes:
        node = nodes[clean_q]
        return {
            "node_key": clean_q,
            "display_name": node.get("display_name", clean_q),
            "hardware_type": node.get("hardware_type", ""),
            "roles": node.get("roles", []),
            "matched_by": "node_key",
        }

    # 2. Match IP address or host domain in node IPs
    for key, node in nodes.items():
        ips = node.get("ips", {})
        for ip_type, val in ips.items():
            if str(val).lower() == clean_q or clean_q in str(val).lower():
                return {
                    "node_key": key,
                    "display_name": node.get("display_name", key),
                    "hardware_type": node.get("hardware_type", ""),
                    "roles": node.get("roles", []),
                    "matched_by": f"ip:{ip_type}",
                }

    # 3. Match service name
    for key, node in nodes.items():
        services = node.get("services", {})
        if clean_q in services:
            return {
                "node_key": key,
                "display_name": node.get("display_name", key),
                "hardware_type": node.get("hardware_type", ""),
                "roles": node.get("roles", []),
                "matched_by": f"service:{clean_q}",
            }

    # 4. Fallback for localhost / 127.0.0.1
    if clean_q in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        mac_node = nodes.get("mac_workstation", {})
        return {
            "node_key": "mac_workstation",
            "display_name": mac_node.get("display_name", "Local Mac (Workstation)"),
            "hardware_type": mac_node.get("hardware_type", "Apple Silicon Mac"),
            "roles": mac_node.get("roles", []),
            "matched_by": "loopback",
        }

    return {
        "node_key": "unregistered",
        "display_name": f"Remote Node ({query})",
        "hardware_type": "External Node",
        "roles": [],
        "matched_by": "none",
    }


def format_node_label(query: str) -> str:
    """Returns a clean display label (e.g. 'LG 2025 (Legion PC)')."""
    info = resolve_hardware_node(query)
    return info["display_name"]


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "100.104.211.61"
    res = resolve_hardware_node(q)
    print(f"Query: '{q}' -> {res['display_name']} ({res['hardware_type']}) [Matched by: {res['matched_by']}]")
