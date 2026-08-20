#!/usr/bin/env python3
import paramiko

def main():
    print("Connecting to legion-sentry (192.168.1.183)...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("192.168.1.183", username="carlos", password="jyZbJ%ljOC&N%kD5", timeout=10)

    def sudo_exec(cmd):
        stdin, stdout, stderr = ssh.exec_command(f"sudo -S {cmd}")
        stdin.write("jyZbJ%ljOC&N%kD5\n")
        stdin.flush()
        out = stdout.read().decode()
        err = stderr.read().decode()
        return out, err

    print("Installing fping for micro-speed sweeps...")
    sudo_exec("apt-get install -y fping")

    netwatch_script = '''#!/bin/bash
# ==============================================================================
# 🚨 Sentry LAN Device Scanner & Intruder Watchdog
# Continuous ARP scan and hardware vendor auditing for 192.168.1.0/24
# ==============================================================================
set -euo pipefail

KNOWN_FILE="/etc/sentry/known_devices.json"
INTRUDER_LOG="/var/log/sentry/intruders.log"
LATEST_INVENTORY="/var/log/sentry/devices_latest.json"

mkdir -p /etc/sentry /var/log/sentry

if [ ! -f "$KNOWN_FILE" ]; then
    echo "[]" > "$KNOWN_FILE"
fi

# 1. Warm up ARP table with fast parallel sweep
fping -g -q -r 1 -t 50 192.168.1.0/24 2>/dev/null || true

# 2. Extract IPv4 neighbors
RAW_NEIGHBORS=$(ip -4 neigh show dev wlan0 | grep -E "lladdr" | awk '{print $1, $5, $6}' || true)

DEVICES="[]"
NEW_COUNT=0
TOTAL_COUNT=0

echo ""
echo "=========================================================================================="
echo "  🏠 CONNECTED HOUSEHOLD NETWORK INVENTORY (192.168.1.0/24)"
echo "=========================================================================================="
printf "%-16s %-19s %-38s %-10s\\n" "IP Address" "MAC Address" "Vendor / Hardware" "Status"
echo "------------------------------------------------------------------------------------------"

while read -r IP MAC STATE; do
    if [ -n "$IP" ] && [ -n "$MAC" ]; then
        TOTAL_COUNT=$((TOTAL_COUNT + 1))
        
        # OUI Lookup
        OUI_PREFIX=$(echo "$MAC" | tr '[:lower:]' '[:upper:]' | cut -d: -f1-3 | tr -d ':')
        VENDOR=$(grep -i "^$OUI_PREFIX" /usr/share/arp-scan/ieee-oui.txt 2>/dev/null | cut -f2- || true)
        
        # Friendly naming heuristics
        if [ "$IP" = "192.168.1.1" ]; then
            VENDOR="Google Fiber Gateway Router"
        elif [ "$IP" = "192.168.1.183" ]; then
            VENDOR="Raspberry Pi (Legion Sentry)"
        elif [ "$IP" = "192.168.1.116" ]; then
            VENDOR="Legion Server (lg2025)"
        elif [ "$IP" = "192.168.1.196" ]; then
            VENDOR="Carlos's MacBook Pro (Apple)"
        elif [ -z "$VENDOR" ]; then
            VENDOR="Standard LAN Device"
        fi
        
        # Check if known
        IS_KNOWN=$(jq --arg mac "$MAC" 'map(select(.mac == $mac)) | length' "$KNOWN_FILE" 2>/dev/null || echo 0)
        
        if [ "$IS_KNOWN" -eq 0 ]; then
            STATUS="🚨 NEW"
            NEW_COUNT=$((NEW_COUNT + 1))
            echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") - NEW DEVICE: $IP ($MAC) - $VENDOR" >> "$INTRUDER_LOG"
            NEW_KNOWN=$(jq --arg ip "$IP" --arg mac "$MAC" --arg vendor "$VENDOR" --arg first "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" '. += [{ip: $ip, mac: $mac, vendor: $vendor, first_seen: $first}]' "$KNOWN_FILE")
            echo "$NEW_KNOWN" > "$KNOWN_FILE"
        else
            STATUS="✅ Known"
        fi
        
        printf "%-16s %-19s %-38s %-10s\\n" "$IP" "$MAC" "${VENDOR:0:37}" "$STATUS"
        
        DEVICES=$(echo "$DEVICES" | jq --arg ip "$IP" --arg mac "$MAC" --arg vendor "$VENDOR" --arg status "$STATUS" '. += [{ip: $ip, mac: $mac, vendor: $vendor, status: $status}]')
    fi
done <<< "$RAW_NEIGHBORS"

echo "=========================================================================================="
echo "  Total Active Devices: $TOTAL_COUNT | New Detected: $NEW_COUNT"
echo "=========================================================================================="

echo "$DEVICES" > "$LATEST_INVENTORY"
'''

    sftp = ssh.open_sftp()
    with sftp.file("/tmp/sentry-netwatch", "w") as f:
        f.write(netwatch_script)
    sftp.close()

    sudo_exec("mv /tmp/sentry-netwatch /usr/local/bin/sentry-netwatch && chmod +x /usr/local/bin/sentry-netwatch")
    print("✅ UPDATED sentry-netwatch WITH PARALLEL ARP SWEEP!")
    ssh.close()

if __name__ == "__main__":
    main()
