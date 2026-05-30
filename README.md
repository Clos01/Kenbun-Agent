# Kenbun-Agent

[README](README.md) · [Contributing](CONTRIBUTING.md) · [MIT License](LICENSE) · [Security](docs/SECURITY.md)

# Kenbun-Agent

> [Documentation](docs/) · [License: MIT](LICENSE) · [GitHub Repository](https://github.com/Clos01/Kenbun-Agent)

**Kenbun-Agent** is an extensible, local-first AI development harness designed to safely execute, optimize, and persist automated tools in isolated workspaces. It connects local LLMs (such as Llama and DeepSeek) and cloud engines (such as Gemini) to a secure Docker runtime environment, using Abstract Syntax Tree (AST) analysis to dynamically load custom tools and index codebases without risking host system exposure.

Run it on a $5 Linux VPS, a serverless cluster, or directly on your local workstation. It is built to run entirely offline or connect with cloud reasoning gateways.

---

## ⚙️ Core Architecture & Features

*   **Isolated Docker Workspaces (Sandbox)**: File-writing, compilation, and terminal tasks are executed inside containerized, capability-dropped Docker containers. This prevents accidental host modifications or malicious commands from impacting your primary system.
    *   *Example:* If a generated tool accidentally triggers `rm -rf /`, it executes within a transient container, leaving your host disk untouched.
*   **Autonomic "Ralph-Loop" Recovery Engine**: High-fidelity self-healing execution loop that intercepts tool rejections, rolls back uncommitted workspace edits, feeds the compiler traceback or audit critique back into context, and requests alternative coding strategies from the healer model.
*   **Zero-Config Hook Gateways (`~/.kenbun/config.yaml`)**: Restrict and govern tool execution intercepts using an external configuration file. Standardizes security gates across manual TTY approval requests, smart LLM ensemble courts, off mode, and custom security shell executables with fail-closed timeouts.
*   **Autopilot VRAM & RAM Hardware-Sensing**: Zero-config setup wizard that dynamically audits macOS unified memory and Linux Nvidia GPU VRAM on startup to auto-select and download the optimal Ollama local model configuration for your machine.
*   **Automated Code Review & Safety Linting (Adversarial Court)**: Includes a multi-model validation engine (Defendant, Prosecutor, and Judge agents) that checks generated code changes for security vulnerabilities (e.g., SQL injections, hardcoded secret credentials) before committing.
    *   *Example:* Pre-commit hooks run generated scripts through an AST security linter to block unsafe code blocks.
*   **AST Code Indexing & Semantic Search**: Uses ChromaDB (a local vector database) to chunk, embed, and index your codebase. This enables context-aware queries to find the exact parts of your codebase you need without relying on exact keyword matches.
    *   *Example:* Searching for *"How do we handle API authentication?"* returns the correct security functions and file paths, even if they don't contain that exact phrase.
*   **Resource & Token Budget Optimizer**: Automatically routes tasks between local models (e.g., running `llama3.2:3b` on Ollama for simple tasks like syntax parsing) and cloud models (e.g., using `gemini-2.5-pro` for complex tasks like architecture audits), minimizing token usage and cost.
*   **Dynamic AST Tool Harvester (Zero-Config Extension)**: Extend the agent's tools simply by adding a standard Python script decorated with `@sovereign_tool` in `core/tools/` subdirectories. The bootstrapper uses non-executing AST parsing to discover, validate, and load tools dynamically.
    *   *Example:* Placing a script at `core/tools/send_slack.py` automatically registers the Slack tool globally across the agent framework without editing database tables or configuration files.
*   **Write-Ahead Logging (WAL) Persistence**: Built-in SQLite persistence engine utilizing Write-Ahead Logging (WAL) for safe, concurrent database reads and writes during heavy concurrent processing.
*   **Model Context Protocol (MCP) Native Support**: Acts as a standard Model Context Protocol (MCP) server, allowing AI-powered editors and assistants (such as Claude Desktop and Cursor) to consume Kenbun's search, indexing, and tool execution capabilities.

---

## 🚀 Quick Install (Zero Configuration)

### 🛠️ System Requirements
Before launching, ensure your machine meets the following:
- **Docker & Docker Compose** installed and running
- **Python 3.10+**
- **Minimum 15 GB Free Disk Space** (The local stack downloads container images and local model weights, including `llama3.2` and `deepseek-r1`, on first boot).
- **Recommended 16GB+ RAM** (to comfortably host local LLMs in memory).

### 📦 Installation Pathways

You can deploy Kenbun-Agent using one of two secure methods:

#### 🌟 Method 1: One-Click Automated Installer (Recommended)
This runs our secure, self-healing POSIX-compliant installer. It scans your OS dependencies (macOS, Ubuntu, Debian, RedHat, Alpine, Arch), provisions a secure Python virtual environment, installs required libraries, registers the global `kenbun` command wrapper in your PATH, and runs the interactive wizard automatically:

```bash
curl -fsSL https://raw.githubusercontent.com/Clos01/Kenbun-Agent/main/install.sh | bash
```
> [!IMPORTANT]
> **First-Time PATH Activation:** After running the automated curl installer, standard Unix shells will not immediately recognize the new `kenbun` command in your *current* terminal tab. You must **reload your shell configuration** by running `source ~/.bashrc` (or `source ~/.zshrc` on macOS), or open a **new terminal tab** before running `kenbun`.
>
> **Direct Path Fallback:** If your PATH hasn't loaded yet, you can launch the wizard directly using the absolute path wrapper:
> ```bash
> ~/.local/bin/kenbun
> ```
>
> **Piped Input (EOF) Notice:** When running the installer via `curl | bash`, the standard input is redirected to the download stream. Our safety guards gracefully exit the setup wizard menu to prevent raw Python tracebacks. Once the installation script finishes, simply type `source ~/.bashrc` and press ENTER, then configure your keys by typing `kenbun` and pressing ENTER!

### 🌸 The Global `kenbun` CLI Toolkit

Once the installer has registered `kenbun` in your PATH, you can use these fast CLI shortcuts from anywhere on your system:

| Command | Action | Description |
| :--- | :--- | :--- |
| **`kenbun`** | Interactive Wizard Menu | Launches the full Sakura interactive onboarding wizard. |
| **`kenbun chat`** | Cognitive Agent Shell (Termchat) | Starts the self-healing interactive terminal chat copilot directly. |
| **`kenbun start`** | Start Stack | Spins up the Docker Swarm Compose microservices in the background. |
| **`kenbun stop`** | Stop Stack | Stops and shuts down the Docker Compose containers. |
| **`kenbun setup`** | API Keys Setup | Opens the interactive API credentials configuration manager. |
| **`kenbun mcp`** | Register MCP | Registers Kenbun's tools inside Claude Desktop and Cursor automatically. |
| **`kenbun dashboard`**| Telemetry Guidelines | Shows access port mappings and links for the live telemetry dashboard. |
| **`kenbun express`** | Express Setup | Automates the core default seed environment (`.env`) generation. |

#### 🛠️ Method 2: Manual Clone & Setup
For manual audits or isolated workspace checkouts, perform these exact steps in sequence:

##### 1️⃣ Step 1: Clone the Repository and Navigate In
```bash
git clone https://github.com/Clos01/Kenbun-Agent.git kenbun-agent
cd kenbun-agent
```
> [!IMPORTANT]
> **Directory Check:** You must change directories (`cd kenbun-agent`) before executing any subsequent commands to avoid "No such file or directory" interpreter failures.

##### 2️⃣ Step 2: Run the Automated Bootstrapper
Initialize the environment configuration file, telemetry metrics, and local SQLite databases:
```bash
python3 scripts/bootstrap.py
```

### 3️⃣ Step 3: Boot up the Swarm & The Portable UI
Spin up the unified microservices stack:
```bash
docker compose up -d --build
```

> [!IMPORTANT]
> **AI Orchestration vs. Docker Swarm Clarification:**
> Kenbun-Agent is described as an agentic swarm because it orchestrates multiple specialized, collaborative AI worker personas. However, at the system infrastructure layer, the local stack runs entirely on **standard Docker Compose** (`docker compose`). It does **NOT** require initializing a Docker Swarm cluster (`docker swarm init`). This keeps local development zero-friction and lightweight!

**🎉 Access the Dashboard!**
Open your browser and navigate to the local dashboard interface:
[http://localhost:3000](http://localhost:3000)

> [!NOTE]
> **VM or Cloud Deployments:** If hosting Kenbun-Agent on a cloud VM or local VM instance (VirtualBox, Proxmox, VMware, Hyper-V), default NAT adapters and firewalls will block traffic. You must transition your VM network adapter to **Bridged Mode** and open UFW ports (3000, 8000, 8001, 8888). Refer to the comprehensive **[VM & Firewall Networking Guide](docs/VM_NETWORKING.md)** for step-by-step instructions.

#### 🏛️ Method 3: Proxmox VE & Portainer Home-Lab Node (Headless)
If you are deploying Kenbun-Agent on dedicated virtualization hardware (such as a headless home-lab server VM) to run as an autonomous, remote resource managed via a graphical browser console:
1. Refer to our step-by-step **[Proxmox VE & Portainer Deployment Guide](docs/PROXMOX_PORTAINER_DEPLOYMENT.md)** for BIOS, VM setup, and bridged routing parameters.
2. Run our secure, zero-touch bootstrapper script on your newly provisioned Ubuntu VM to automatically configure Docker, Portainer CE (on port `9443`), strict UFW firewalls, and custom hardware-sensing local LLM settings:
   ```bash
   sudo bash scripts/ubuntu_vm_bootstrap.sh
   ```
3. Deploy the container swarm stack directly using the Portainer Web UI or comfortably via the command line utilizing the interactive wizard wrapper command:
   ```bash
   kenbun
   ```

### 📡 Hybrid System Health & Gateway Probes

Whenever you open the Next.js Dashboard or boot up the Cognitive Shell (`kenbun chat`), an advanced **System Diagnostics Check** runs. This health probe features an advanced network-sensing engine:

1.  **Smart Cloud Gateway Audits**: If your primary LLM is a cloud provider (e.g., Google Gemini, OpenAI, Anthropic, DeepSeek, or Azure), the probe detects the domain name and performs a fast, non-blocking TCP socket verification on port `443` to ensure internet and endpoint reachability. This bypasses the Ollama-specific API tags query (`GET /api/tags`), preventing timeout delays, socket hangs, or false-offline reporting!
2.  **Local Ollama Reachability**: If configured for offline execution, the probe queries the local Ollama backend tags to ensure the primary model is active.
3.  **Docker CLI & Daemon Health Audit**: Verifies socket write permissions (`/var/run/docker.sock`) and alerts you with secure, non-leaking diagnostic summaries if access is blocked.
4.  **Decoupled Vector Database Connection**: Connects to the host/port defined by `CHROMA_HOST` and `CHROMA_PORT` in your `.env` (defaulting to `localhost:8000`), allowing you to point your agent swarm to a dedicated remote or shared ChromaDB instance!

### 🧹 Swarm Stack Cleanup & Reset Wizard

The setup wizard (`kenbun` or `python3 scripts/bootstrap.py`) provides an automated stack cleaning tool under Option 6: **`🧹 Clean/Reset Swarm Stack`**. This handles deep Docker house-cleaning when you need to free disk space or trigger a completely fresh container environment:

*   **Light Clean (Option 1)**: Stops the compose stack and deletes local containers, volumes, and local build images. This is **fast** and leaves standard pulled base images untouched.
*   **Deep Purge (Option 2)**: Completely prunes the stack. It deletes all containers, volumes, and large cached Docker base images (e.g. Ollama, ChromaDB, Next.js). Then, it runs `docker builder prune -f` and `docker image prune -f` to recover maximum host storage.

*Note on Zero-Config local models:* Kenbun automatically bundles a Dockerized Ollama container! When you run `docker compose up`, it will boot up the local engine and pull `llama3.2` and `deepseek-r1` in the background.

---

### 4️⃣ Step 4: Configure Your Environments (`.env`)
Configure your path settings and LLM providers inside the generated `.env` file:

**Option A: Local Offline Setup (Zero Cost / Private)**
```env
PROJECT_ROOT=/absolute/path/to/your/cloned/kenbun-agent
PROJECT_NAME=kenbun-agent

# Vector Database Binding (Decoupled Storage)
CHROMA_HOST=localhost
CHROMA_PORT=8000

# Ollama Binding
PRIMARY_LLM_URL=http://localhost:11434/v1
PRIMARY_LLM_MODEL=llama3.2:3b
```

**Option B: Cloud Reasoning Integration**
```env
PROJECT_ROOT=/absolute/path/to/your/cloned/kenbun-agent
PROJECT_NAME=kenbun-agent

# Vector Database Binding (Decoupled Storage)
CHROMA_HOST=localhost
CHROMA_PORT=8000

PRIMARY_LLM_URL=https://generativelanguage.googleapis.com/v1
PRIMARY_LLM_MODEL=gemini-2.5-pro
GEMINI_API_KEY=your_key_here
```

### 5️⃣ Step 5: FastMCP IDE Integration
Kenbun-Agent acts as a native Model Context Protocol (MCP) server. See setup instructions in the [MCP Integration Guide](docs/MCP_INTEGRATION.md).

Quick connection binding:
```url
mcp://localhost:8001
```

---

## 🌸 Kenbun Cognitive Agentic Shell (Termchat)

Kenbun-Agent includes an **autonomous, self-healing interactive terminal chat shell** located at `scripts/terminal_chat.py`. 

Instead of just chatting, the terminal agent acts as a fully situated developer copilot and system administrator:

1. **Self-Healing Reflex Shell**: The LLM (local Ollama or cloud) can autonomously diagnose system statuses, inspect files, or verify ports by proposing commands in ```execute\n<command>\n``` blocks.
2. **Human-in-the-Loop Safeguards**: Proposed commands are presented in a high-fidelity visual card. They are strictly blocked and only execute once you manually type `y` to authorize them.
3. **Dynamic Intent-Based RAG**: The CLI pre-flight pipeline checks the prompt's intent in the background:
   * **System Telemetry**: If asking about errors or Docker, it audits VM socket permissions, active containers, and UFW firewalls, injecting live metrics directly into context.
   * **Design Grounding**: If asking about UI/UX or styling, it runs a local BM25 query on the UI-UX Pro Max database, grounding the LLM with HSL palettes and typography tokens.
4. **Offline Local First**: Designed to run 100% free and private using your local Ollama models (`llama3.2:3b` or `deepseek-r1:8b`).

### 🚀 How to Launch the Termchat
```bash
python3 scripts/terminal_chat.py
```

### 🎨 Active Dialogue Commands
* `/exit` — Gracefully terminate the chat session.
* `/reset` — Purge conversation history to start fresh.
* `/system` — Prints a secure audit of your active `.env` configuration.
* `/search <query>` — Manually query UI-UX Pro Max for styles, color boards, or layouts.

---

## 🛡️ Standardized Error Catalog & Secure Self-Healing

If the automated installer `install.sh` or bootstrapper encounters runtime constraint failures, it outputs a secure, non-leaking terminal exception box containing a standardized error code:

| Error Code | Diagnostic Meaning | Affected Operating Systems | Secure Resolution |
| :--- | :--- | :--- | :--- |
| **`ERR_001_GIT_MISSING`** | Git executable is not installed or Xcode build system is inactive. | macOS, Linux | Install git via your package manager. For macOS, accept the Xcode developer terms by running `git --version` in terminal. |
| **`ERR_002_PYTHON_MISSING`** | Python 3.x executable is not installed or broken. | macOS, Linux | Install Python 3.8+ from official repositories. |
| **`ERR_003_PYTHON_VERSION`** | Python interpreter version is too old (< 3.8). | Linux, macOS | Upgrade your Python interpreter. |
| **`ERR_004_VENV_FAILED`** | Virtual environment creation failed (typically missing split package). | Ubuntu/Debian, CentOS/RHEL, Alpine | Run the targeted package installer listed in the dynamic installer box (e.g., `sudo apt install python3-venv` or `apk add py3-virtualenv`). |
| **`ERR_005_PIP_FAILED`** | Package bootstrap or requirements installation failed. | Alpine, Ubuntu, macOS | Occurs when compiler headers for cryptographic extensions are missing. Install native development headers safely (e.g., `build-essential`, `libssl-dev`, or `musl-dev`) and rerun. |
| **`ERR_006_BINARY_WRITE`** | Global wrapper script could not be written to `~/.local/bin` or permissions failed. | Linux, macOS | Verify write permission on your home directory. Do NOT run the installer with root (`sudo`) unless required for system-wide symlinking. |
| **`ERR_007_SHELL_CONFIG`** | Installer failed to append wrapper directory to Shell Profile PATH. | Linux, macOS | Manually append `export PATH="$HOME/.local/bin:$PATH"` to your active `~/.zshrc` or `~/.bashrc`. |
| **`ERR_008_MACOS_XCODE`** | Xcode Command Line Tools are missing or inactive. | macOS | Run `xcode-select --install` in terminal and accept the Apple popup wizard. |
| **`ERR_009_DOCKER_INACTIVE`** | Docker CLI exists, but the Docker Daemon is stopped or unreachable. | Linux, macOS | Start your local Docker system (e.g., `sudo systemctl start docker` or open Docker Desktop). |

### 🔒 Operational Security & Log Hygiene Guidelines

1. **Zero Raw Secret Leakage:** The decryption routine (`decrypt_value`) intercepts errors and forbids dumping active configuration files, tokens, or environment values to error diagnostics or system logs.
2. **Piping to Bash Safely:** As a general cybersecurity best practice, when downloading remote scripts via `curl | bash`, always inspect the script content beforehand:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/Clos01/Kenbun-Agent/main/install.sh
   ```
   Only pipe to `bash` after verifying that the source repository is valid and the remote endpoint uses HTTPS.
3. **No Sudo Arbitrary Execution:** The installer runs fully in user space (`$HOME/.kenbun-agent` and `$HOME/.local/bin`). Never run the installer script as `sudo` unless you are explicitly trying to link `kenbun` to `/usr/local/bin` for system-wide access. This protects host directories from privilege escalation risks.

---

## ⌨️ Terminal Navigation & SSH Latency Troubleshooting

When connected remotely to your server via SSH, network latency can occasionally interfere with multi-byte escape sequences (such as arrow keys `↑` and `↓`), causing the terminal menus to instantly cancel or behave erratically.

### 🌟 Tactile Navigation Shortcuts (Fallback)
If your arrow keys are not working or cause the setup menu to exit, you can use standard keyboard letters to navigate comfortably:
- Press **`w`** or **`k`** (Vim Up) to move **UP**.
- Press **`s`** or **`j`** (Vim Down) to move **DOWN**.
- Press **`ENTER`** or **`SPACE`** to select.
- Press **`ESC`** or **`q`** to cancel/exit.

### 📥 Safe Code Updates & Pulling fixes
To pull the latest updates cleanly without risking local merge conflicts, run:
```bash
cd ~/.kenbun-agent
git pull origin main
```
If you encounter git merge errors or want to force sync your server perfectly with the latest GitHub code, execute:
```bash
git fetch origin && git reset --hard origin/main
```

---

## 🏛️ Multi-Persona Onboarding Blueprint

To support standard developers and enterprise operations engineers alike, we categorize the onboarding experience into two distinct technical profiles:

### 🌟 Pathway A: The CLI Operator (Standard Setup)
*   **Target Audience:** 95% of developers who want a zero-friction local installation.
*   **Workflow:** Simply run the one-click installer (`curl | bash`), source your shell, and type `kenbun` to launch the **guided interactive wizard**.
*   **Benefit:** The wizard automatically audits your RAM, picks the best quantized local model, seeds databases, registers the FastMCP endpoints inside Claude Desktop/Cursor, and spins up the stack automatically—requiring zero Docker compilation knowledge.

### 🏛️ Pathway B: The Headless Infrastructure Engineer (Power Setup)
*   **Target Audience:** DevOps and home-lab engineers deploying Kenbun-Agent on headless servers, VirtualBox VMs, or Proxmox VE hypervisors.
*   **Workflow:** Run `sudo bash scripts/ubuntu_vm_bootstrap.sh` to configureTailscale, Docker, Portainer CE, and firewall endpoints automatically.
*   **Runbook for Common Headless Roadblocks:**

#### 1. Portainer Database Schema Mismatch (BoltDB Conflict)
*   **Symptom:** Running the bootstrapper completes, but navigating to `https://<VM_IP>:9443` fails. Running `docker ps` shows the `portainer` container constantly `Restarting`. Running `docker logs portainer` shows `The database schema version does not align with the server version`.
*   **Cause:** Your server already has an existing named Docker volume (`portainer_data`) initialized by a different version of Portainer CE.
*   **Safe Resolution:** Wipe the conflicting volume and restart (highly safe as Portainer is just a viewer and holds no code files):
    ```bash
    docker rm -f portainer
    docker volume rm portainer_data
    sudo bash scripts/ubuntu_vm_bootstrap.sh
    ```

#### 2. Portainer Web Editor Build Failures (Dockerfile Missing)
*   **Symptom:** Creating a new stack via Portainer's **Web editor** by pasting `docker-compose.yml` fails with: `Service fastmcp_server Building failed to solve: failed to read dockerfile: open Dockerfile: no such file or directory`.
*   **Cause:** Pasting compose configurations in a raw web editor does not provide Portainer with the local source directory files (like `Dockerfile` or python dependencies).
*   **Resolutions:**
    *   **Method 1 (Fast CLI):** Run `kenbun` in your server terminal and select **Option 5 (Start Swarm Stack)**. This compiles and launches the containers directly where the files exist.
    *   **Method 2 (Portainer Repository):** In Portainer, change the build method from **`Web editor`** to **`Repository`**. Specify `https://github.com/Clos01/Kenbun-Agent.git` as the URL and `refs/heads/main` as the branch, load your `.env` variables below, and click Deploy.

---

## 📖 Operational Commands

*   `python3 scripts/bootstrap.py` — Run setup and bootstrapper.
*   `PYTHONPATH=core pytest core/tests` — Execute the full standalone integration test suite.

---

## 🤝 Contributing
We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on coding styles, AST dynamic tool decoration standards, and the PR review checklist.

1. Fork the repo and create your feature branch: `git checkout -b feat/my-new-tool`
2. Decorate your custom tools: `@sovereign_tool(name="...", category="...")`
3. Verify with Pytest and submit a pull request!
