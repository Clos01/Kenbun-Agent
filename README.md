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
*   **Automated Code Review & Safety Linting**: Includes a multi-model validation engine that checks generated code changes for security vulnerabilities (e.g., SQL injections, hardcoded secret credentials) before committing.
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

When you first open the dashboard, it automatically runs a **System Diagnostics Check** to ensure your vector index (ChromaDB) and local inference engine (Ollama) are connected properly.

*Note on Zero-Config local models:* Kenbun automatically bundles a Dockerized Ollama container! When you run `docker compose up`, it will boot up the local engine and pull `llama3.2` and `deepseek-r1` in the background.

---

### 4️⃣ Step 4: Configure Your Environments (`.env`)
Configure your path settings and LLM providers inside the generated `.env` file:

**Option A: Local Offline Setup (Zero Cost / Private)**
```env
PROJECT_ROOT=/absolute/path/to/your/cloned/kenbun-agent
PROJECT_NAME=kenbun-agent

# Ollama Binding
PRIMARY_LLM_URL=http://localhost:11434/v1
PRIMARY_LLM_MODEL=llama3.2:3b
```

**Option B: Cloud Reasoning Integration**
```env
PROJECT_ROOT=/absolute/path/to/your/cloned/kenbun-agent
PROJECT_NAME=kenbun-agent
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

## 📖 Operational Commands

*   `python3 scripts/bootstrap.py` — Run setup and bootstrapper.
*   `PYTHONPATH=core pytest core/tests` — Execute the full standalone integration test suite.

---

## 🤝 Contributing
We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on coding styles, AST dynamic tool decoration standards, and the PR review checklist.

1. Fork the repo and create your feature branch: `git checkout -b feat/my-new-tool`
2. Decorate your custom tools: `@sovereign_tool(name="...", category="...")`
3. Verify with Pytest and submit a pull request!
