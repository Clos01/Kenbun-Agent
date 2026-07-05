# Kenbun Security Policy & Architecture

Kenbun is designed as a sovereign, local-first intelligence engine. Security is enforced at both the infrastructure (Docker sandboxing) and cognitive (System 2 auditing) layers to prevent host system exposure, privilege escalation, or credential leaks.

---

## 🛡️ 1. Jailed Execution Sandbox (System 1)

All commands, file writes, and code execution evaluations proposed by the agent run inside an isolated, ephemeral Docker sandbox container (`hermes_sandbox_jail`). The jail is configured with the following hardening measures:

1. **Non-Root Execution:** The sandbox executes tasks under a dedicated unprivileged user `hermes_jail` (UID `2000`). Root access is fully disabled.
2. **Dropped Capabilities:** All Docker kernel capabilities are dropped (`cap_drop: [ALL]`) to prevent container breakouts, driver manipulation, or low-level kernel exploits.
3. **No Privilege Escalation:** The kernel flag `no-new-privileges:true` is strictly enforced to block any setuid binaries or elevation attempts.
4. **Read-Only Root Filesystem:** The container's root filesystem is mounted as read-only (`read_only: true`), with `/tmp` mounted as an ephemeral in-memory filesystem (`tmpfs`).
5. **Filesystem Isolation:** The container has read-write access only to the mapped `/home/hermes_jail/workspace` directory. Host filesystems, network configurations, and host sockets are completely hidden and inaccessible.
6. **Strict Resource Constraints:** To prevent Denial of Service (DoS) attacks via fork bombs or memory exhaustion, the container is strictly limited:
   - Max Memory: `512MB` (with swap disabled)
   - Max CPU: `0.5 cores`
   - Max PIDs: `100` (`pids_limit`)
7. **Network Isolation:** By default, the sandbox runs with no network access (`network_mode: none`) to prevent data exfiltration and Server-Side Request Forgery (SSRF).
8. **Hardened Runtime Support:** For high-risk environments, Kenbun supports running the sandbox via **gVisor** (`runsc`) or **Kata Containers** to provide strong kernel-level isolation.

---

## 🧠 2. Cognitive Guardrails & Auditing (System 2 & 2c)

Before any code changes or command proposals are executed, they must pass through local auditing filters:

1. **System 2c (Guardrail Agent):** Fast, deterministic, AST-based security checks running locally. It scans code for path traversal, hardcoded secrets, and unsafe imports.
2. **System 2 (Supervisor Agent):** Activates a consensus-driven local model ensemble (via LM Studio) to check proposed changes for security risks (e.g. SQL injection, command injection) and structural regressions.
3. **Zero-Secret Hardening:** Sensitive keys are never hardcoded or stored in cleartext logs. They are encrypted using AES via the internal `secret_manager.py` utility and bound to a gitignored master key file (`.kenbun_master.key`).

---

## 🎛️ 3. Execution Control & Approval Modes

Execution of shell commands or API requests is governed by the configuration file located at `~/.kenbun/config.yaml`.
This supports three standard execution modes:
- **TTY Manual Approval:** The terminal chat prompts the developer to type `y` to authorize each action.
- **Smart Ensemble Court:** Local System 2 models vote on whether to auto-approve the execution based on safety context.
- **Fail-Closed Hook Scripts:** Executes a custom shell script to check tool parameters. If the check fails or times out, the command is immediately aborted.

---

## 🚨 Reporting Vulnerabilities

If you discover a security issue or vulnerability in Kenbun-Agent, please do not open a public issue. Instead, report it privately to the security team at **security@sovereignassembly.org**.
