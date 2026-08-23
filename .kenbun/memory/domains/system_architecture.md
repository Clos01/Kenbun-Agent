# System Architecture: Kenbun Sovereign Workbench

- **Host Machine:** Apple Silicon MacBook Pro (Coordinator)
- **Execution Satellite:** Lenovo ThinkStation P330 (Ubuntu 24.04, Quadro P600 GPU, Tailscale IP: 100.100.199.127)
- **Local VLM:** UI-TARS-2B + mmproj on P330 Port 8090
- **Display Pipeline:** Xorg on DISPLAY=:0 with HDMI dummy plug, console mirror on Port 5900 (VNC) and Port 3389 (RDP)
- **Core Orchestrator:** FastMCP running in Kenbun core with System 2 Supervisor audits
