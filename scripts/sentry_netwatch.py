#!/usr/bin/env python3
import subprocess
import json
import os
import datetime

KNOWN_FILE = "/etc/sentry/known_devices.json"
INTRUDER_LOG = "/var/log/sentry/intruders.log"
LATEST_FILE = "/var/log/sentry/devices_latest.json"

os.makedirs("/etc/sentry", exist_ok=True)
os.makedirs("/var/log/sentry", exist_ok=True)

# Parallel sweep to warm ARP
subprocess.run(["fping", "-g", "-q", "-r", "1", "-t", "50", "192.168.1.0/24"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Read /proc/net/arp
devices = []
with open("/proc/net/arp", "r") as f:
    lines = f.readlines()[1:] # skip header

known = []
if os.path.exists(KNOWN_FILE):
    try:
        with open(KNOWN_FILE, "r") as f:
            known = json.load(f)
    except Exception:
        known = []

known_macs = {k.get("mac", "").lower(): k for k in known}
new_devices = []

header_ip = "IP Address"
header_mac = "MAC Address"
header_vendor = "Vendor / Hardware"
header_status = "Status"

print("")
print("=" * 90)
print("  🏠 CONNECTED HOUSEHOLD NETWORK INVENTORY (192.168.1.0/24)")
print("=" * 90)
print(f"{header_ip:<16} {header_mac:<19} {header_vendor:<40} {header_status:<10}")
print("-" * 90)

for line in lines:
    parts = line.split()
    if len(parts) >= 4:
        ip = parts[0]
        mac = parts[3].lower()
        flags = parts[2]
        
        if mac == "00:00:00:00:00:00" or flags == "0x0":
            continue
            
        # Vendor heuristics
        vendor = "Standard LAN Device"
        if ip == "192.168.1.1":
            vendor = "Google Fiber Gateway Router"
        elif ip == "192.168.1.183":
            vendor = "Raspberry Pi (Legion Sentry)"
        elif ip == "192.168.1.116":
            vendor = "Legion Server (lg2025)"
        elif ip == "192.168.1.196":
            vendor = "Carlos's MacBook Pro (Apple)"
        elif mac.startswith("08:27:a8") or mac.startswith("50:5b:c2"):
            vendor = "Smart TV / IoT Hub"
        elif mac.startswith("6c:24:08") or mac.startswith("c0:95:cf"):
            vendor = "Network Station / Media Client"
        elif mac.startswith("2a:8d:0f") or mac.startswith("d0:ab:d5"):
            vendor = "Apple Device (iPhone / iPad)"
        elif mac.startswith("be:eb:a1") or mac.startswith("b2:e7:97") or mac.startswith("d6:90:a4"):
            vendor = "Mobile / Wireless Client (Private MAC)"
            
        status = "✅ Known"
        if mac not in known_macs:
            status = "🚨 NEW"
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            new_record = {"ip": ip, "mac": mac, "vendor": vendor, "first_seen": now_iso}
            known.append(new_record)
            known_macs[mac] = new_record
            new_devices.append(new_record)
            with open(INTRUDER_LOG, "a") as logf:
                logf.write(f"{now_iso} - NEW DEVICE: {ip} ({mac}) - {vendor}\n")
                
        print(f"{ip:<16} {mac:<19} {vendor:<40} {status:<10}")
        devices.append({"ip": ip, "mac": mac, "vendor": vendor, "status": status})

print("=" * 90)
print(f"  Total Active Devices: {len(devices)} | Newly Discovered: {len(new_devices)}")
print("=" * 90)
print("")

with open(KNOWN_FILE, "w") as f:
    json.dump(known, f, indent=2)

with open(LATEST_FILE, "w") as f:
    json.dump(devices, f, indent=2)
