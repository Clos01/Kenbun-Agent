# OS Independence & Portability Guide: Kenbun-Agent

This guide outlines how Kenbun-Agent achieves cross-platform development patterns (OS Independence) to ensure seamless execution across Windows, macOS, and Linux. It covers deployment nuances and known workarounds for modern environments.

---

## 🏛️ Executive Summary

Kenbun-Agent is designed from the ground up as a **portable, local-first agentic swarm**. By leveraging Python, Node.js, and Docker containerization, it achieves a high degree of operating system independence. All system-dependent features (such as macOS voice synthesis, shell bindings, and directory paths) are strictly isolated using runtime checks and dynamic path resolution.

---

## 🔍 Strategy Alignment

### 1. Containerization (Docker)
*   **Implementation:**
    *   The project provides a multi-container stack in `docker-compose.yml` hosting **ChromaDB**, **Ollama**, the **FastMCP Swarm Server**, and the **Next.js Dashboard**.
    *   The backend runs inside a `python:3.11-slim` container defined in the `Dockerfile`. By encapsulating the agent execution context inside a Linux container, the host OS (whether Windows/WSL, macOS, or Linux) becomes irrelevant to the core swarm logic.

### 2. Cross-Platform Runtimes
*   **Implementation:**
    *   The core swarm engine is written in **Python 3**, using interpreted runtimes with built-in OS abstraction layers.
    *   The web dashboard uses **Node.js/Next.js**, which leverages the cross-platform V8 runtime.

### 3. Abstract File Paths
*   **Implementation:**
    *   Hardcoded paths like `C:\` or `/opt/` are eliminated in the core modules.
    *   The codebase utilizes Python's built-in `pathlib.Path` library exclusively to handle path joins, resolutions, and expansions. This dynamically adapts the folder separator (`/` on Unix vs. `\` on Windows) at runtime.
    *   **Dynamic Roots:** The active workspace is resolved dynamically using the `get_active_project_root()` helper.

### 4. OS-Specific Logic
*   **Implementation:**
    *   **Conditional Dependencies:** In `core/requirements.txt`, macOS-specific speech synthesis dependencies (`pyobjc`) are conditionally installed using platform markers:
        ```text
        pyobjc-core==12.1; sys_platform == 'darwin'
        pyobjc-framework-Speech==12.1; sys_platform == 'darwin'
        ```
    *   **Runtime CLI Bindings:** In `engine.py`, Enter key bindings are dynamically adjusted based on platform checks. For example, `Ctrl+Enter` newline behavior is altered for Windows, WSL, and SSH environments where keyboard keypress wire encodings vary.

### 5. Standardized Environment Variables
*   **Implementation:**
    *   The project uses `pydantic-settings` to handle configurations. It merges environment variables, `.env` files, and defaults in a single, safe, type-checked configurations class.

---

## 🏗️ Deployment Portability Matrix

| Feature | Linux/macOS (Native) | Containerized (Docker) | Windows (Native) | Windows (WSL) |
|---|---|---|---|---|
| **CLI REPL (`kenbun`)** | Supported (`install.sh`) | Supported (`docker exec`) | Supported (`python`) | Supported (`install.sh`) |
| **Swarm Orchestrator** | Supported | Supported | Supported | Supported |
| **Vector DB (Chroma)** | Local SQLite fallback | Supported | Local SQLite fallback | Local SQLite fallback |
| **Telemetry Dashboard** | Local npm run | Supported | Local npm run | Local npm run |

---

## 🛑 Modern OS Workarounds & Edge Cases

### PEP 668: `EXTERNALLY-MANAGED-ENVIRONMENT` (Ubuntu 24.04+, macOS Homebrew)
Modern Linux distributions and macOS Homebrew implementations strictly enforce PEP 668, preventing global `pip install` commands to protect system Python binaries.

*   **Symptom:** Running `pip install -e .` fails with an `EXTERNALLY-MANAGED-ENVIRONMENT` error.
*   **Resolution A (Best Practice - Virtual Environments):**
    Always use a virtual environment, ensuring you have the `venv` module installed natively:
    ```bash
    sudo apt install python3-venv  # Ubuntu/Debian
    python3 -m venv venv
    source venv/bin/activate
    pip install -e .
    ```
*   **Resolution B (YOLO Global Bypass):**
    If running within an isolated VM (like Proxmox LXC or a dedicated lab node) where global package pollution is acceptable:
    ```bash
    sudo python3 -m pip install -e . --break-system-packages
    ```

### NVIDIA GPU Acceleration on Linux/Ubuntu
Local models (via Ollama or Docker) will default to CPU inference unless the host has the NVIDIA Container Toolkit correctly installed and the Docker daemon is configured to use the NVIDIA runtime.
*   **Symptom:** Running local models like `gemma4:12b` or `deepseek-r1:8b` is extremely slow, and running `ollama ps` shows `CPU` instead of `100% GPU`.
*   **Resolution:**
    Execute the provided setup script on your Ubuntu/Debian server to automatically install the toolkit, configure Docker, and restart the swarm containers:
    ```bash
    sudo ./scripts/setup_nvidia_gpu.sh
    ```
