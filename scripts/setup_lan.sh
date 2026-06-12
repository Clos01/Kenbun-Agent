#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Kenbun-Agent LAN Setup & Network Doctor
#
# One command to make a server-hosted Kenbun-Agent reachable from
# other machines on the local network, and to diagnose/repair the
# classic "Docker picked a subnet that collides with my LAN and now
# the server is unreachable" failure.
#
# Usage:
#   ./scripts/setup_lan.sh            # configure LAN access + restart stack
#   ./scripts/setup_lan.sh --doctor   # diagnostics only, change nothing
#   ./scripts/setup_lan.sh --yes      # non-interactive (CI / provisioning)
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
ENV_EXAMPLE="$REPO_ROOT/.env.example"
DEFAULT_SUBNET="172.28.77.0/24"
DOCTOR_ONLY=false
ASSUME_YES=false

for arg in "$@"; do
  case "$arg" in
    --doctor) DOCTOR_ONLY=true ;;
    --yes|-y) ASSUME_YES=true ;;
    *) echo "Unknown flag: $arg"; exit 1 ;;
  esac
done

say()  { printf '%b\n' "$1"; }
ok()   { say "  ✅ $1"; }
warn() { say "  ⚠️  $1"; }
err()  { say "  ❌ $1"; }

# ── 1. Detect the host's primary LAN IP ──────────────────────────────
detect_lan_ip() {
  local ip=""
  if command -v ip >/dev/null 2>&1; then
    ip=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}' | head -1)
  fi
  if [ -z "$ip" ] && command -v ipconfig >/dev/null 2>&1; then # macOS
    for iface in en0 en1; do
      ip=$(ipconfig getifaddr "$iface" 2>/dev/null) && break || true
    done
  fi
  if [ -z "$ip" ] && command -v hostname >/dev/null 2>&1; then
    ip=$(hostname -I 2>/dev/null | awk '{print $1}') || true
  fi
  echo "$ip"
}

say "\n🔎 Kenbun Network Doctor"
say "────────────────────────"

LAN_IP=$(detect_lan_ip)
if [ -n "$LAN_IP" ]; then
  ok "Host LAN IP detected: $LAN_IP"
else
  err "Could not auto-detect a LAN IP. Are you connected to a network?"
  exit 1
fi

# ── 2. Check Docker is alive ─────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  err "Docker is not installed or not on PATH."
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  err "Docker daemon is not responding. Try: sudo systemctl restart docker"
  exit 1
fi
ok "Docker daemon is running"

# ── 3. Subnet collision check ────────────────────────────────────────
# If a Docker bridge network overlaps the subnet of the host's primary
# interface, Docker's route wins and the server drops off the LAN.
LAN_PREFIX=$(echo "$LAN_IP" | cut -d. -f1-2)
COLLISION=false
while IFS= read -r net; do
  [ -z "$net" ] && continue
  subnets=$(docker network inspect "$net" --format '{{range .IPAM.Config}}{{.Subnet}} {{end}}' 2>/dev/null) || continue
  for sn in $subnets; do
    sn_prefix=$(echo "$sn" | cut -d. -f1-2)
    if [ "$sn_prefix" = "$LAN_PREFIX" ]; then
      COLLISION=true
      warn "Docker network '$net' ($sn) overlaps your LAN ($LAN_IP)."
    fi
  done
done < <(docker network ls --format '{{.Name}}')

if [ "$COLLISION" = true ]; then
  say ""
  say "  This is the cause of the 'server loses network until Docker is fixed' issue."
  say "  Fixes:"
  say "   1. Kenbun's own network is pinned via KENBUN_SUBNET in .env (default $DEFAULT_SUBNET)."
  say "      Pick any range that does NOT overlap your LAN, then run:"
  say "        docker compose down && docker compose up -d"
  say "   2. For OTHER Docker networks/projects, pin the daemon-wide pool in /etc/docker/daemon.json:"
  say '        { "default-address-pools": [ { "base": "172.28.0.0/16", "size": 24 } ] }'
  say "      then: sudo systemctl restart docker"
  say ""
else
  ok "No Docker network overlaps your LAN subnet"
fi

# Warn if the pinned default itself would collide with this LAN.
SUGGESTED_SUBNET="$DEFAULT_SUBNET"
if [ "$LAN_PREFIX" = "172.28" ]; then
  SUGGESTED_SUBNET="10.213.77.0/24"
  warn "Your LAN uses 172.28.x.x — Kenbun will use $SUGGESTED_SUBNET instead."
fi

if [ "$DOCTOR_ONLY" = true ]; then
  say "\n🩺 Doctor mode: no changes made."
  exit 0
fi

# ── 4. Write .env ────────────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  ok "Created .env from .env.example"
fi

set_env_var() {
  local key="$1" value="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    # BSD/GNU sed portable in-place edit
    sed -i.bak "s|^${key}=.*|${key}=${value}|" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

if [ "$ASSUME_YES" = false ]; then
  say ""
  printf "Expose Kenbun on the LAN (BIND_IP=0.0.0.0) so other devices on %s can reach it? [y/N] " "$LAN_PREFIX.x.x"
  read -r reply
  case "$reply" in [Yy]*) ;; *) say "Aborted. Nothing changed."; exit 0 ;; esac
fi

set_env_var "BIND_IP" "0.0.0.0"
set_env_var "ASSEMBLY_PC_IP" "$LAN_IP"
set_env_var "KENBUN_SUBNET" "$SUGGESTED_SUBNET"
ok "Updated .env (BIND_IP=0.0.0.0, ASSEMBLY_PC_IP=$LAN_IP, KENBUN_SUBNET=$SUGGESTED_SUBNET)"

# ── 5. Recreate the stack (subnet changes need full recreation) ──────
say "\n♻️  Recreating containers (a pinned subnet only applies on recreation)..."
cd "$REPO_ROOT"
docker compose down --remove-orphans
docker compose up -d
ok "Stack is up"

# ── 6. Firewall hint (Linux servers) ─────────────────────────────────
if command -v ufw >/dev/null 2>&1 && sudo -n ufw status 2>/dev/null | grep -q "Status: active"; then
  warn "UFW firewall is active. Open the ports for LAN clients:"
  say "     sudo ufw allow 3000/tcp && sudo ufw allow 8001/tcp"
fi

API_PORT=$(grep -E '^API_PORT=' "$ENV_FILE" | cut -d= -f2); API_PORT=${API_PORT:-8001}
DASHBOARD_PORT=$(grep -E '^DASHBOARD_PORT=' "$ENV_FILE" | cut -d= -f2); DASHBOARD_PORT=${DASHBOARD_PORT:-3000}

say "\n🎉 Kenbun-Agent is now reachable on your LAN:"
say "   Dashboard:  http://$LAN_IP:$DASHBOARD_PORT"
say "   FastMCP:    http://$LAN_IP:$API_PORT"
say "\n   (CORS already trusts private-LAN origins — no extra config needed.)"
