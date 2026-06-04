# Contributing to Kenbun

First of all, thank you for your interest in contributing to Kenbun! We are building a high-performance, local-first agentic swarm designed for sovereign, low-latency intelligence.

To keep the repository stable, secure, and clean, we maintain a set of contribution guidelines that all developers must adhere to.

---

## 🏛️ Code of Conduct & Principles

*   **Local-First & Resource-Efficient:** Every feature should be built keeping CPU-only local execution bounds in mind (such as Proxmox/Portainer VMs running lightweight quantized models).
*   **Security First:** Never expose secrets, local API keys, absolute server paths, or personal network topologies (`192.168.x.x` variables should always be sanitized/masked in examples).
*   **Test-Driven Execution:** Code without testing is considered draft quality. All core logic changes should be validated by the smoke or unit test suites.

---

## ⚙️ Local Development Setup

To configure your environment and run the codebase locally:

1.  **Clone your Fork:**
    ```bash
    git clone https://github.com/<your-username>/Kenbun-Agent.git
    cd Kenbun-Agent
    ```

2.  **Establish a Virtual Environment:**
    Ensure you are using Python 3.11 or greater:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install Dependencies:**
    Install core dependencies along with ML and Test extras:
    ```bash
    pip install --upgrade pip setuptools wheel
    pip install -e .[ml,test]
    pip install -r core/requirements.txt
    ```

---

## 🧪 Testing Guidelines

Before submitting any Pull Request, you must run the fast-smoke testing suite to verify that your changes do not break core services:

```bash
cd core
PYTHONPATH=. pytest tests/ -m smoke
```

*   **Smoke Suite:** Fast checks running on imports, math routes, and basic state machines (`pytest tests/ -m smoke`).
*   **Unit Suite:** Pure-logic unit tests without external API dependencies (`pytest tests/ -m unit`).
*   **Adding Tests:** If you introduce new core utilities, add a corresponding `test_*.py` file under `core/tests/` using standard PyTest conventions.

---

## 🍴 Standard Git Workflow

To maintain a clean commit history and avoid conflicts, follow this workflow:

### 1. Create a Branch
Use descriptive branch prefixes based on the work being performed:
*   `feature/` — New features or agent integrations (e.g., `feature/speculative-decoding`).
*   `bugfix/` — Fixing a defect or incorrect behavior (e.g., `bugfix/token-leak`).
*   `perf/` — Memory optimizations, CPython GC tuning, vector store compactions (e.g., `perf/gc-heap-freeze`).
*   `docs/` — Documentation improvements or deployment guides (e.g., `docs/proxmox-setup`).

### 2. Format Commits
Follow the Conventional Commits structure:
*   `feat: add memoryview slicing for HNSW search`
*   `fix: resolve socket path traversal vulnerability`
*   `perf: implement obmalloc heap freezing`
*   `docs: update Proxmox VM core requirements`

---

## 🛑 Security & Leak Protections

We enforce a zero-tolerance policy on committed credentials. Prior to committing code:
*   Audit all edits to guarantee that no Gemini API keys, local database passwords, or IP addresses are present.
*   Enforce a zero-check policy on custom server configurations.
*   If your branch contains security risks, the automated CI scanning tools will reject it.
