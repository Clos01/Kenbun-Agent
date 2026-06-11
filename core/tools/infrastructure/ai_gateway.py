import subprocess
from pathlib import Path

from core.tools.utils.console_ui import C_G, C_R, C_Y, C_W, draw_box
from core.tools.utils.env_builder import update_env_value

def detect_configuration_mismatch(llm_url, llm_model):
    """Detects mismatch between cloud provider URLs and local Ollama model names."""
    is_cloud_url = any(domain in llm_url.lower() for domain in ["api.deepseek.com", "api.openai.com", "api.anthropic.com", "googleapis.com"])
    local_keywords = ["llama", "qwen", "mistral", "gemma", "phi3", "orca", "deepseek-r1"]
    is_local_model = any(kw in llm_model.lower() for kw in local_keywords)
    if is_cloud_url and is_local_model:
        return True, "cloud_url_with_local_model"
    return False, None

def check_and_heal_mismatch(llm_url, llm_model):
    """
    SILENT auto-healer — no user prompts.
    Detects cloud URL + local model mismatch and automatically aligns the
    model to the correct cloud provider, preserving their cloud key and URL.
    """
    has_mismatch, _ = detect_configuration_mismatch(llm_url, llm_model)
    if not has_mismatch:
        return llm_url, llm_model

    # Determine the best cloud model name based on the cloud URL
    target_model = "gpt-4o-mini"
    provider_name = "OpenAI"
    if "anthropic" in llm_url.lower():
        target_model = "claude-3-5-sonnet-latest"
        provider_name = "Anthropic"
    elif "googleapis" in llm_url.lower():
        target_model = "gemini-2.5-flash"
        provider_name = "Google AI Studio"
    elif "deepseek" in llm_url.lower():
        target_model = "deepseek-chat"
        provider_name = "DeepSeek"

    # Symmetrically encrypt the healed model name if Fernet key is active
    try:
        from cryptography.fernet import Fernet
        possible_keys = [
            Path.cwd() / ".kenbun_master.key",
            Path.cwd() / "core" / ".kenbun_master.key",
            Path(__file__).parent.parent.parent / ".kenbun_master.key",
            Path(__file__).parent.parent.parent / "core" / ".kenbun_master.key"
        ]
        key = None
        for kp in possible_keys:
            if kp.exists():
                with open(kp, "rb") as fk:
                    key = fk.read().strip()
                break
        if key:
            f = Fernet(key)
            encrypted_model = f"enc:{f.encrypt(target_model.encode()).decode()}"
            update_env_value("PRIMARY_LLM_MODEL", encrypted_model)
        else:
            update_env_value("PRIMARY_LLM_MODEL", target_model)
    except Exception:
        update_env_value("PRIMARY_LLM_MODEL", target_model)

    print(f"{C_G}⚡ Auto-heal:{C_R} Cloud URL detected with local model. Aligned model to {C_G}{target_model}{C_R} ({provider_name})")
    return llm_url, target_model

def detect_model_tier(llm_model: str, llm_url: str) -> str:
    """
    Returns the capability tier of the active model:
      'nano'     — ≤3B params (gemma-4:1b, deepseek-r1:1.5b, phi3:mini)
      'standard' — 3B-14B (gemma4:12b, gemma3:9b, mistral:7b)
      'cloud'    — Remote APIs (gpt-*, gemini-*, claude-*)
    """
    is_cloud = any(d in llm_url.lower() for d in ["openai.com", "anthropic.com", "googleapis.com", "deepseek.com"])
    if is_cloud:
        return "cloud"
    nano_patterns = [":1b", ":1.5b", ":0.5b", ":2b", "phi3:mini", "tinyllama"]
    if any(p in llm_model.lower() for p in nano_patterns):
        return "nano"
    return "standard"

def run_startup_probe(llm_url: str, llm_model: str, chroma_host: str = "localhost", chroma_port: str = "8000") -> dict:
    """
    Runs parallel health checks against Ollama/Cloud APIs, ChromaDB, and Docker.
    Returns a dict of { service: (ok: bool, detail: str) }.
    """
    import threading as _t
    results = {}
    lock = _t.Lock()

    def probe_ollama():
        # Check if cloud provider (e.g. Google Gemini, OpenAI, DeepSeek, Anthropic)
        is_cloud = any(domain in llm_url.lower() for domain in ["api.deepseek.com", "api.openai.com", "api.anthropic.com", "googleapis.com", "azure.com"])
        if is_cloud:
            try:
                # Fast socket connection check on port 443 to verify internet/endpoint reachability
                from urllib.parse import urlparse
                parsed = urlparse(llm_url)
                hostname = parsed.hostname or "google.com"
                
                import socket
                socket.create_connection((hostname, 443), timeout=1.5)
                with lock:
                    results["ollama"] = (True, f"ONLINE  •  {llm_model} ({hostname})")
            except Exception as e:
                with lock:
                    results["ollama"] = (False, f"Cloud gateway unreachable — {str(e)[:50]}")
        else:
            try:
                import requests as _r
                base = llm_url.replace("/v1", "").replace("/v1beta/openai", "")
                _r.get(f"{base}/api/tags", timeout=3)
                with lock:
                    results["ollama"] = (True, f"{llm_model}  •  {base.split('://')[-1]}")
            except Exception as e:
                with lock:
                    results["ollama"] = (False, f"Unreachable — {str(e)[:60]}")

    def probe_chroma():
        try:
            import requests as _r
            _r.get(f"http://{chroma_host}:{chroma_port}/api/v2/heartbeat", timeout=2)
            with lock:
                results["chromadb"] = (True, f"ACTIVE  •  {chroma_host}:{chroma_port}")
        except Exception:
            try:
                import requests as _r
                _r.get(f"http://{chroma_host}:{chroma_port}/api/v1/heartbeat", timeout=2)
                with lock:
                    results["chromadb"] = (True, f"ACTIVE  •  {chroma_host}:{chroma_port}")
            except Exception:
                with lock:
                    results["chromadb"] = (False, f"Offline — start docker compose")

    def probe_docker():
        try:
            r = subprocess.run(["docker", "info"], capture_output=True, timeout=3)
            ok = r.returncode == 0
            with lock:
                results["docker"] = (ok, "Running" if ok else "Daemon offline")
        except Exception:
            with lock:
                results["docker"] = (False, "Not installed or offline")

    threads = [_t.Thread(target=f, daemon=True) for f in [probe_ollama, probe_chroma, probe_docker]]
    for th in threads: th.start()
    for th in threads: th.join(timeout=4)
    return results

def print_health_card(probe_results: dict) -> bool:
    """
    Prints a compact system health card. Returns True if all services OK.
    """
    icons = {True: f"{C_G}✓{C_R}", False: f"{C_Y}✗{C_R}"}
    labels = {"ollama": "Ollama", "chromadb": "ChromaDB", "docker": "Docker"}
    lines = []
    all_ok = True
    for key in ["ollama", "chromadb", "docker"]:
        ok, detail = probe_results.get(key, (False, "Not checked"))
        if not ok:
            all_ok = False
        icon = icons[ok]
        label = f"{labels[key]:<10}"
        lines.append(f"  {icon} {label}  {detail}")
    draw_box(lines, title=f"🌐 {C_Y}SYSTEM HEALTH", border_color=C_G if all_ok else C_Y, text_color=C_W)
    return all_ok

def build_system_prompt(tier: str, llm_model: str) -> str:
    """
    Returns a model-tier-aware system prompt.
    Nano models get a simplified, focused prompt to prevent hallucination.
    """
    base = (
        f"You are Kenbun, an AI assistant running inside a local terminal on the user's machine. "
        f"You are currently powered by the LLM: {llm_model}. Do not hallucinate your architecture or claim to be LLaMA unless that is your actual active model.\n"
        "Your job is to have a helpful conversation and assist with coding, system diagnosis, and design tasks.\n"
        "\n--- HERITAGE DESIGN SYSTEM MANDATE (System 5 Oracle) ---\n"
        "As an Augmented CTO, you MUST strictly adhere to the Heritage Design System.\n"
        "Prioritize design system compliance above all else for aesthetic choices.\n"
        "Specifically:\n"
        "- NEVER use 'neon' colors (e.g., neon green, neon pink, etc.).\n"
        "- NEVER use colors or aesthetic elements that conflict with the established palette and guidelines in STRUCTURE.md and DESIGN.md.\n"
        "- If a user request conflicts with the Heritage Design System, you MUST politely decline the aesthetic aspect of the request, explain the design system constraint, and propose a compliant alternative.\n"
        "This is a critical Cognitive Gate. Do not bypass it.\n"
        "--- END HERITAGE DESIGN SYSTEM MANDATE ---\n"
    )
    execute_block = (
        "\nCOMMAND EXECUTION:\n"
        "When you need to run a real system command, output it in this exact format:\n"
        "```execute\n<the shell command>\n```\n"
        "The user will approve it before it runs. Only use this for actual system tasks — "
        "NOT for answering questions or explaining things.\n"
    )
    spawn_block = (
        "\nBACKGROUND AGENTS:\n"
        "For long-running tasks (model pulls, builds, large file ops), use:\n"
        "```spawn\n<the shell command>\n```\n"
        "This runs the task in the background without blocking our conversation.\n"
    )
    memory_block = (
        "\nMEMORY:\n"
        "You have access to a local Hivemind (ChromaDB). The user can:\n"
        "  /remember <title> = <content>  — save a note\n"
        "  /recall <query>               — search memories\n"
    )

    if tier == "nano":
        return (
            f"You are Kenbun, an AI assistant running locally on the user's machine. You are currently powered by the LLM: {llm_model}.\n"
            "Your job is to have a helpful conversation. Keep responses short, direct, and conversational.\n"
            "--- HERITAGE DESIGN SYSTEM MANDATE ---\n"
            "You must adhere to the Heritage Design System. Do not use 'neon' colors.\n"
            "--- END MANDATE ---\n"
            "You must execute tools by outputting raw execute blocks immediately. Do NOT explain your reasoning.\n"
            "EXAMPLES:\n"
            "User: List files in /opt\n"
            "Assistant: ```execute\nls /opt\n```\n"
            "User: Use orchestrate to locate kenbun\n"
            "Assistant: ```execute\nkenbun orchestrate\n```\n" +
            execute_block + spawn_block
        )
    elif tier == "standard":
        return base + execute_block + spawn_block + memory_block
    else:  # cloud
        return (
            base +
            "You have full reasoning capability. Use multi-step thinking for complex problems. "
            "Delegate long-running tasks to background agents using spawn blocks.\n" +
            execute_block + spawn_block + memory_block +
            "\nTHE KENBUN PROCESS (System 1-6) [MANDATORY]:\n"
            "To avoid hallucination, you MUST follow the Kenbun Process for any complex, architectural, or research request:\n"
            "1. Do NOT guess or hallucinate answers for complex tasks. If you don't know the exact tool signature, execute the `list-tools` command or equivalent to discover tools!\n"
            "2. Execute `orchestrate` via your native tool calling to dynamically route the task to the Cognitive Assembly.\n"
            "3. Execute `consult_supervisor` or `review_code_with_gemini` via your native tool calling capabilities to enforce System 2 safety guardrails.\n"
            "4. Always use `recall` via native tool calling to search Hivemind ChromaDB for previous context.\n"
            "You are the Terminal Gateway. Rely on your native MCP CLI tools to do the heavy lifting!\n"
        )
