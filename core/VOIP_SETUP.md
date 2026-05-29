# ☎️ Kenbun SIP Sentinel: VoIP Setup Guide

The SIP Sentinel allows your server to register as a **3CX SIP Extension**, enabling it to call your phone directly for critical alerts (e.g., storage failures or security breaches).

## 1. 3CX Management Console Configuration
1.  **Create a New Extension**:
    - Go to `Users` > `Add User`.
    - Note the **Extension Number** (e.g., `105`).
2.  **Retrieve SIP Credentials**:
    - Go to the `Options` or `Phone Provisioning` tab of the new extension.
    - Find the **Authentication ID** (this is often different from the extension number).
    - Note the **SIP Password**.
3.  **Security Settings**:
    - Go to `Dashboard` > `Security` > `IP Blacklist`.
    - Ensure your Mac Studio's local IP is NOT blacklisted.
    - In the extension settings, ensure "Disallow use of extension outside the LAN" is UNCHECKED if your Mac is on a different subnet.

## 2. Environment Configuration
Add the following variables to your `.env` file in the project root:

```bash
# SIP Sentinel (3CX)
SIP_SERVER="YOUR_PBX_IP"    # Your 3CX PBX IP address
SIP_PORT=5060               # Default SIP port
SIP_USERNAME="YOUR_EXT"     # Your Extension Number
SIP_PASSWORD="enc:..."      # Use encrypt_secret.py to encrypt your SIP password
USER_PHONE_NUMBER="DEST"    # The extension or phone number you want the server to call
LOCAL_IP="YOUR_MACHINE_IP"  # The local IP of your machine
```

## 3. Encryption (Mandatory)
For security, the SIP Sentinel expects an encrypted password. Run the following to encrypt your 3CX password:

```bash
python3 tools/utils/secret_manager.py --encrypt "YOUR_SIP_PASSWORD"
```
Copy the output (starting with `enc:`) into your `.env`.

## 4. Testing the Bridge
Once configured, you can test the proactive alert logic by running:

```bash
export PYTHONPATH=$PYTHONPATH:.
python3 tools/infrastructure/sip_sentinel.py
```

Your phone (or 3CX app) should ring, and the server will deliver the "System Storage Critical" test message.

## 🚀 Proactive Integration
The Sentinel is now integrated into `native_ears.py`. If the system detects a critical failure, it will automatically call `sentinel.initiate_proactive_alert()`.
