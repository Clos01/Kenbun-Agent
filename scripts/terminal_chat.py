#!/usr/bin/env python3
"""
🌸 Kenbun Termchat & Reflex Shell (CLI Agent REPL)
Allows developers to chat with Kenbun-Agent's LLM, query design guides,
and authorize the local Ollama/Cloud LLM to execute safe shell commands
and repair system errors in real time.
"""
import os
import sys
import json
import re
import requests
import subprocess
import shutil
from pathlib import Path

# Color palettes (Limestone & Sakura themed)
C_P = "\033[95m" # Pink (Sakura)
C_G = "\033[92m" # Green (Limestone/Sage)
C_Y = "\033[93m" # Gold
C_C = "\033[96m" # Cyan
C_W = "\033[97m" # White
C_D = "\033[90m" # Grey
C_R = "\033[0m"  # Reset

# Global tracking variable for active memory directory
active_brain_health_dir = None

def decrypt_value(val):
    """Decrypts values that are encrypted with 'enc:' prefix using the repository master key."""
    if not val.startswith("enc:"):
        return val
    try:
        from cryptography.fernet import Fernet
        # Resolve key file path dynamically
        possible_keys = [
            Path.cwd() / ".kenbun_master.key",
            Path.cwd() / "core" / ".kenbun_master.key",
            Path(__file__).parent.parent / ".kenbun_master.key",
            Path(__file__).parent.parent / "core" / ".kenbun_master.key"
        ]
        key = None
        for kp in possible_keys:
            if kp.exists():
                with open(kp, "rb") as f:
                    key = f.read().strip()
                break
        
        if key:
            f = Fernet(key)
            # Decrypt value (strip 'enc:' prefix)
            return f.decrypt(val[4:].encode()).decode()
    except Exception:
        # Fallback to returning raw string if decryption fails or cryptography is missing
        pass
    return val

def update_env_value(key, new_value):
    """Safely updates a specific key-value pair in .env file, symmetrically encrypting it if needed."""
    possible_paths = [
        Path.cwd() / ".env",
        Path.cwd() / "core" / ".env",
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent.parent / "core" / ".env"
    ]
    target_path = None
    for path in possible_paths:
        if path.exists():
            target_path = path
            break
            
    if not target_path:
        target_path = Path.cwd() / ".env"
        
    lines = []
    updated = False
    
    # Read existing lines
    if target_path.exists():
        try:
            with open(target_path, "r") as f:
                lines = f.readlines()
        except PermissionError:
            print(f"\n{C_Y}❌ Permission Denied when trying to open {target_path}. Run with appropriate permissions.{C_R}")
            return False
            
    # Symmetrically encrypt the new value using the master key
    encrypted_val = new_value
    try:
        # Resolve the tools module to load secret_manager
        sys.path.insert(0, str(target_path.parent / "core"))
        from tools.utils.secret_manager import encrypt_value
        encrypted_val = "enc:" + encrypt_value(new_value)
    except Exception:
        pass
        
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}="):
            new_lines.append(f"{key}={encrypted_val}\n")
            updated = True
        else:
            new_lines.append(line)
            
    if not updated:
        new_lines.append(f"{key}={encrypted_val}\n")
        
    try:
        with open(target_path, "w") as f:
            f.writelines(new_lines)
        return True
    except Exception as e:
        print(f"\n{C_Y}❌ Failed to write back env configuration: {e}{C_R}")
        return False

def load_env_vars():
    """Manually parse .env file to load active configurations securely."""
    env = {}
    possible_paths = [
        Path.cwd() / ".env",
        Path.cwd() / "core" / ".env",
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent.parent / "core" / ".env"
    ]
    for path in possible_paths:
        if path.exists():
            try:
                with open(path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            parts = line.split("=", 1)
                            if len(parts) == 2:
                                key = parts[0].strip()
                                val = parts[1].strip().strip('"').strip("'")
                                # Decrypt immediately on load!
                                env[key] = decrypt_value(val)
                break
            except PermissionError:
                # Catch permission errors gracefully during pre-flight diagnostics
                pass
    return env

def get_design_suggestions(query):
    """Fallback search using scripts/search.py if available."""
    search_script = Path(__file__).parent / "search.py"
    if not search_script.exists():
        search_script = Path(__file__).parent.parent / "src" / "ui-ux-pro-max" / "scripts" / "search.py"
    
    if search_script.exists():
        try:
            res = subprocess.run(
                ["python3", str(search_script), query, "-n", "2"],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
    return None

def get_active_project_root():
    """Robust helper matching config.py path discovery."""
    if os.getenv("PROJECT_ROOT"):
        return Path(os.getenv("PROJECT_ROOT"))
    docker_path = Path("/app")
    if docker_path.exists() and (docker_path / "tools").exists():
        return docker_path
    current = Path(__file__).resolve().parent.parent
    return current

def gather_system_telemetry():
    """Gathers real-time diagnostic and environment telemetry (Zero-overhead)."""
    telemetry = []
    
    # 1. Check Docker socket permissions
    sock_path = "/var/run/docker.sock"
    has_sock = os.path.exists(sock_path)
    has_access = os.access(sock_path, os.W_OK) if has_sock else False
    
    telemetry.append(f"Docker Socket: Exists={has_sock}, WriteAccess={has_access}")
    
    # 2. Check Docker daemon status quickly
    docker_bin = shutil.which("docker")
    if docker_bin:
        try:
            res = subprocess.run([docker_bin, "info"], capture_output=True, text=True, timeout=2)
            telemetry.append(f"Docker Daemon Status: Active={res.returncode == 0}")
        except Exception:
            telemetry.append("Docker Daemon Status: Unresponsive/Offline")
    else:
        telemetry.append("Docker Daemon Status: CLI Not Installed")
        
    # 3. Check active containers
    if docker_bin:
        try:
            res = subprocess.run([docker_bin, "ps", "--format", "{{.Names}}: {{.Status}}"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout.strip():
                containers = res.stdout.strip().replace("\n", ", ")
                telemetry.append(f"Active Containers: [{containers}]")
            else:
                telemetry.append("Active Containers: None running")
        except Exception:
            pass
            
    # 4. Check active ports
    try:
        # Check if UFW is active
        ufw_check = subprocess.run(["sudo", "-n", "ufw", "status"], capture_output=True, text=True, timeout=1)
        if ufw_check.returncode == 0:
            status = "active" if "active" in ufw_check.stdout.lower() else "inactive"
            telemetry.append(f"UFW Firewall: Status={status}")
    except Exception:
        pass
        
    return "\n".join(telemetry)

def detect_configuration_mismatch(llm_url, llm_model):
    """Detects mismatch between cloud provider URLs and local Ollama model names."""
    is_cloud_url = any(domain in llm_url.lower() for domain in ["api.deepseek.com", "api.openai.com", "api.anthropic.com", "googleapis.com"])
    
    # Local model indicators
    local_keywords = ["llama", "qwen", "mistral", "gemma", "phi3", "orca", "deepseek-r1:1.5b", "deepseek-r1:8b", "deepseek-r1:70b"]
    is_local_model = any(kw in llm_model.lower() for kw in local_keywords)
    
    # Mismatch is active when calling a Cloud Provider but specifying a Local model
    if is_cloud_url and is_local_model:
        return True, "cloud_url_with_local_model"
    return False, None

def check_and_heal_mismatch(llm_url, llm_model):
    """Audits configuration mismatch and prompts the developer for dynamic self-healing fixes."""
    has_mismatch, reason = detect_configuration_mismatch(llm_url, llm_model)
    if not has_mismatch:
        return llm_url, llm_model
        
    print(f"\n{C_Y}┌─────────────────────────────────────────────────────────┐")
    print(f"│ ⚠️  {C_Y}CONFIGURATION MISMATCH AUDIT TRIGGERED{C_G}               │")
    print(f"├─────────────────────────────────────────────────────────┤")
    print(f"│ Kenbun has detected a routing conflict in your config:  │")
    print(f"│                                                         │")
    print(f"│ ⚡ Active Provider URL: {C_W}{llm_url[:31]:<31}{C_G} │")
    print(f"│ 🌸 Active model:        {C_W}{llm_model[:31]:<31}{C_G} │")
    print(f"├─────────────────────────────────────────────────────────┤")
    print(f"│ Cloud gateways (like api.deepseek.com) cannot execute   │")
    print(f"│ local model weights (like {llm_model}).                  │")
    print(f"│                                                         │")
    print(f"│ Select an Autonomic Self-Healing patch:                 │")
    print(f"│ {C_C}[1] Switch Model{C_G} - Swap model to target cloud model    │")
    print(f"│                  (e.g., 'deepseek-chat' for DeepSeek)   │")
    print(f"│ {C_C}[2] Switch URL{C_G}   - Route back to local Ollama server    │")
    print(f"│                  (http://localhost:11434/v1)            │")
    print(f"│ {C_C}[3] Bypass{C_G}       - Ignore and boot anyway               │")
    print(f"└─────────────────────────────────────────────────────────┘{C_R}")
    
    while True:
        try:
            choice = input(f"{C_C}Select self-healing action [1-3]: {C_R}").strip()
            if choice == "1":
                # Determine ideal cloud model name
                target_model = "deepseek-chat"
                if "openai" in llm_url.lower():
                    target_model = "gpt-4o-mini"
                elif "anthropic" in llm_url.lower():
                    target_model = "claude-3-5-sonnet-latest"
                elif "googleapis" in llm_url.lower():
                    target_model = "gemini-2.5-flash"
                
                print(f"\n⚙️  Applying Autopilot patch: Setting model to '{target_model}'...")
                if update_env_value("PRIMARY_LLM_MODEL", target_model):
                    print(f"✓ Model successfully corrected in '.env'.")
                    return llm_url, target_model
                break
            elif choice == "2":
                target_url = "http://localhost:11434/v1"
                print(f"\n⚙️  Applying Autopilot patch: Re-routing URL to local Ollama stack...")
                if update_env_value("PRIMARY_LLM_URL", target_url):
                    print(f"✓ Gateway URL successfully re-routed in '.env'.")
                    return target_url, llm_model
                break
            elif choice == "3" or not choice:
                print(f"\n⚠️ Bypassing mismatch safeguards. Booting stack in raw mode...")
                break
            else:
                print(f"{C_Y}⚠️ Invalid option. Select 1, 2, or 3.{C_R}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n⚠️ Mismatch audit interrupted. Proceeding with raw config.")
            break
            
    return llm_url, llm_model

def check_and_migrate_project_memory(old_dirs):
    """Detects if a new workspace project was created, and attaches active memories/WAL DB to it."""
    global active_brain_health_dir
    if not active_brain_health_dir:
        return
        
    cwd = Path.cwd().resolve()
    current_dirs = {p for p in cwd.iterdir() if p.is_dir()}
    new_dirs = current_dirs - old_dirs
    
    if not new_dirs:
        return
        
    for nd in new_dirs:
        # Ignore standard hidden dirs
        if nd.name.startswith(".") or nd.name == "venv" or nd.name == "node_modules":
            continue
            
        print(f"\n{C_G}┌─────────────────────────────────────────────────────────┐")
        print(f"│ 📂 {C_Y}NEW PROJECT WORKSPACE DETECTED{C_G}                        │")
        print(f"├─────────────────────────────────────────────────────────┤")
        print(f"│ Folder: {C_W}{nd.name[:45]:<45}{C_G} │")
        print(f"├─────────────────────────────────────────────────────────┤")
        print(f"│ Would you like to bind this chat's active memories and   │")
        print(f"│ intelligence database directly to this new project?     │")
        print(f"└─────────────────────────────────────────────────────────┘{C_R}")
        
        confirm = input(f"{C_Y}Bind memories to '{nd.name}'? [Y/n]: {C_R}").strip().lower()
        if confirm != "n":
            # 1. Create target brain_health dir inside new folder
            target_bh = nd / "brain_health"
            target_bh.mkdir(parents=True, exist_ok=True)
            
            try:
                # Copy WAL database files if they exist
                for f_name in ["kenbun_intelligence.db", "chat_sessions.json"]:
                    old_f = active_brain_health_dir / f_name
                    if old_f.exists():
                        shutil.copy2(old_f, target_bh / f_name)
                        
                print(f"\n{C_G}✓ Successfully migrated active memories and database to:{C_R}")
                print(f"  {C_C}{target_bh.resolve()}{C_R}\n")
                
                # 2. Change active directory context and reload variables!
                os.chdir(str(nd))
                active_brain_health_dir = target_bh
                
                # Proactively create a .kenbun workspace marker
                (nd / ".kenbun").mkdir(exist_ok=True)
                break
            except Exception as e:
                print(f"\n{C_Y}❌ Failed to migrate memories: {e}{C_R}\n")

def run_proposed_command(cmd):
    """Executes a proposed system shell command safely with stdout/stderr capture."""
    print(f"\n{C_Y}⚙️  Executing: {C_C}{cmd}{C_R}")
    
    # Store directory list state before execution
    cwd = Path.cwd().resolve()
    old_dirs = {p for p in cwd.iterdir() if p.is_dir()}
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=45
        )
        
        # Check if a new folder was created and prompt for memory migration!
        check_and_migrate_project_memory(old_dirs)
        
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if not output.strip():
            output = "[Success: Command executed with zero stdout/stderr output]"
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return -1, "[Timeout Error: The system command exceeded the 45-second execution limit]"
    except Exception as e:
        return -1, f"[Execution Error: Failed to start command: {e}]"

def main():
    global active_brain_health_dir
    env = load_env_vars()
    
    # Extract configs
    llm_url = env.get("PRIMARY_LLM_URL", "http://localhost:11434/v1")
    llm_model = env.get("PRIMARY_LLM_MODEL", "llama3.2:3b")
    
    # Resolve initial brain health dir per v2.8.0 specification
    cwd = Path.cwd().resolve()
    system_root = get_active_project_root()
    if cwd != system_root and ((cwd / ".git").exists() or (cwd / ".kenbun").exists()):
        active_brain_health_dir = cwd / "brain_health"
    else:
        active_brain_health_dir = system_root / "brain_health"
    active_brain_health_dir.mkdir(parents=True, exist_ok=True)
    
    # Audit and dynamically self-heal cloud/local mismatches before displaying banner
    llm_url, llm_model = check_and_heal_mismatch(llm_url, llm_model)
    
    # Proactive URL Normalization for standard local/tailscale APIs (Ollama compatibility endpoint)
    if ("localhost" in llm_url or "127.0.0.1" in llm_url or ".ts.net" in llm_url or "100." in llm_url or "192.168." in llm_url) and not llm_url.endswith("/v1"):
        if not llm_url.endswith("/"):
            llm_url += "/"
        llm_url += "v1"
        
    # Print beautiful banner
    print(f"\n{C_P}██╗  ██╗███████╗███╗   ██╗██████╗ ██╗   ██╗███╗   ██╗")
    print("██║ ██╔╝██╔════╝████╗  ██║██╔══██╗██║   ██║████╗  ██║")
    print("█████╔╝ █████╗  ██╔██╗ ██║██████╔╝██║   ██║██╔██╗ ██║")
    print("██╔═██╗ ██╔══╝  ██║╚██╗██║██╔══██╗██║   ██║██║╚██╗██║")
    print(f"██║  ██╗███████╗██║ ╚████║██████╔╝╚██████╔╝██║ ╚████║ {C_Y}🌸 COGNITIVE AGENT SHELL v2.8.5")
    print(f"{C_P}╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═════╝  ╚═════╝ ╚═╝  ╚═══╝{C_R}")
    print(f"{C_G}┌─────────────────────────────────────────────────────────┐")
    print(f"│ 🌸 Active Agent:      {C_W}{llm_model:<34}{C_G}│")
    print(f"│ ⚡ Ollama Gateway URL: {C_W}{llm_url:<34}{C_G}│")
    print(f"│ 🧠 RAG Rerouter:      {C_G}ACTIVE (Telemetry & Grounding)     │")
    print(f"│ ⚙️  Reflex Status:     {C_Y}ACTIVE (Human-in-the-Loop Safe)    {C_G}│")
    print(f"│                                                         │")
    print(f"│ {C_Y}Commands & Capabilities:{C_G}                                │")
    print(f"│   {C_C}/exit{C_G}     - Gracefully close Termchat                 │")
    print(f"│   {C_C}/reset{C_G}    - Clear dialogue history                    │")
    print(f"│   {C_C}/system{C_G}   - Dump active environment parameters        │")
    print(f"│   {C_C}/search{C_G}   - Direct search on UI-UX Pro Max database  │")
    print(f"└─────────────────────────────────────────────────────────┘{C_R}\n")

    system_prompt = (
        "You are Kenbun, an autonomous local AI system diagnostician, coding engineer, and design expert. "
        "You run natively inside the user's terminal on their Linux/macOS host machine.\n\n"
        "REFLEX SHELL LOOP (YOUR SUPERPOWER):\n"
        "You have the capability to execute system commands, check container statuses, install missing dependencies, "
        "read/write local files, inspect ports, or run diagnostics. "
        "To execute a system shell command, you MUST respond using this exact markdown block:\n"
        "```execute\n"
        "<system command to execute>\n"
        "```\n"
        "Keep commands safe, highly relevant, and direct. The user must manually approve each command via a y/N prompt before it executes. "
        "Once executed, the terminal client will automatically feed back the command's stdout/stderr and exit code directly into your context, "
        "allowing you to analyze the result and continue your self-healing loop or system configuration!\n\n"
        "AST HARVESTED TOOL RUNNER:\n"
        "You can execute any of Kenbun's harvested agent tools globally by running standard 'kenbun <command>' wrappers directly via the execute block. "
        "If the user asks you to create a new project directory (e.g. `mkdir my-new-project`), once created, your terminal chat client will automatically "
        "detect the folder birth, prompt the user for approval, and seamlessly MIGRATE and ATTACH all your active chat memories, SQLite databases, "
        "and logs straight inside the new project's local 'brain_health' directory!"
    )

    history = [
        {"role": "system", "content": system_prompt}
    ]

    username = os.environ.get("USER", "amontano")
    auto_trigger = False

    while True:
        try:
            # If auto_trigger is set, the system feeds back command output automatically without waiting for user input
            if auto_trigger:
                user_input = ""
                auto_trigger = False
            else:
                user_input = input(f"{C_P}{username}@kenbun-agent{C_R}:{C_G}~{C_R}$ ").strip()
                if not user_input:
                    continue
                
                # Handle Slash Commands
                if user_input.startswith("/"):
                    cmd_parts = user_input.split(" ", 1)
                    cmd = cmd_parts[0].lower()
                    
                    if cmd == "/exit":
                        print(f"\n{C_P}🌸 Sayonara! Terminating agent session...{C_R}\n")
                        break
                        
                    elif cmd == "/reset":
                        history = [history[0]]
                        print(f"\n{C_Y}🧹 Dialogue history purged.{C_R}\n")
                        continue
                        
                    elif cmd == "/system":
                        # Fetch fresh config from loaded env
                        fresh_env = load_env_vars()
                        print(f"\n{C_G}🏛  Active Configuration Check:{C_R}")
                        for k, v in fresh_env.items():
                            if "KEY" in k or "SECRET" in k or "TOKEN" in k:
                                v = "******** (Masked Securely)"
                            print(f"  • {C_C}{k:<24}{C_R}= {v}")
                        print()
                        continue
                        
                    elif cmd == "/search":
                        if len(cmd_parts) < 2:
                            print(f"\n{C_Y}⚠️ Usage: /search <design topic / style / palette>{C_R}\n")
                            continue
                        query = cmd_parts[1]
                        print(f"\n{C_G}🔍 Searching UI-UX Pro Max database for: '{query}'...{C_R}")
                        res = get_design_suggestions(query)
                        if res:
                            print(f"\n{C_W}{res}{C_R}\n")
                        else:
                            print(f"\n{C_Y}❌ No matches or search scripts found.{C_R}\n")
                        continue
                        
                    else:
                        print(f"\n{C_Y}❌ Unknown command: {cmd}. Available commands: /exit, /reset, /search, /system{C_R}\n")
                        continue

                # ========================================================
                # 🧠 INTENT-BASED DYNAMIC RAG & TELEMETRY PRE-FLIGHT
                # ========================================================
                grounding_context = []
                
                # A. Design / UI / Style Intent Grounding
                design_keywords = ["color", "palette", "font", "css", "theme", "design", "style", "ui", "ux", "brutalism", "minimalism", "bento", "chart"]
                if any(kw in user_input.lower() for kw in design_keywords):
                    print(f"{C_D}🔍 RAG: Fetching canonical UI-UX Pro Max tokens for query...{C_R}", end="\r")
                    suggestions = get_design_suggestions(user_input)
                    if suggestions:
                        grounding_context.append(f"[DESIGN SYSTEM GROUNDING (Canonical UI-UX Pro Max reference)]:\n{suggestions}")
                
                # B. Diagnostic / System Intent Grounding
                system_keywords = ["docker", "status", "port", "compose", "ip", "run", "daemon", "permission", "error", "fail", "ufw", "firewall", "logs", "active"]
                if any(kw in user_input.lower() for kw in system_keywords):
                    print(f"{C_D}⚙️  RAG: Collecting real-time VM system & container telemetry...{C_R}", end="\r")
                    telemetry = gather_system_telemetry()
                    if telemetry:
                        grounding_context.append(f"[REAL-TIME SYSTEM DIAGNOSTIC TELEMETRY (Current VM status)]:\n{telemetry}")

                # Compile final grounded input
                final_input = user_input
                if grounding_context:
                    # Clean the terminal line where progress was printed
                    print(" " * 80, end="\r") 
                    context_str = "\n\n".join(grounding_context)
                    final_input = f"{context_str}\n\n[USER INSTRUCTION]:\n{user_input}"

                history.append({"role": "user", "content": final_input})

            # Prepare streaming request
            headers = {"Content-Type": "application/json"}
            if "OPENAI_API_KEY" in env and "openai" in llm_url.lower():
                headers["Authorization"] = f"Bearer {env['OPENAI_API_KEY']}"
            elif "DEEPSEEK_API_KEY" in env and "deepseek" in llm_url.lower():
                headers["Authorization"] = f"Bearer {env['DEEPSEEK_API_KEY']}"
            elif "GEMINI_API_KEY" in env and "gemini" in llm_url.lower():
                headers["Authorization"] = f"Bearer {env['GEMINI_API_KEY']}"

            payload = {
                "model": llm_model,
                "messages": history,
                "temperature": 0.2,
                "stream": True
            }
            
            endpoint = f"{llm_url}/chat/completions"
            print(f"\n{C_P}Kenbun 🌸:{C_R} ", end="", flush=True)
            
            response = requests.post(endpoint, json=payload, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            full_reply = ""
            for line in response.iter_lines():
                if line:
                    decoded = line.decode("utf-8").strip()
                    if decoded.startswith("data: "):
                        data_str = decoded[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data_json = json.loads(data_str)
                            chunk = data_json["choices"][0]["delta"].get("content", "")
                            print(chunk, end="", flush=True)
                            full_reply += chunk
                        except Exception:
                            pass
            print("\n")
            
            # Register response
            history.append({"role": "assistant", "content": full_reply})
            
            # Check for execute blocks: ```execute\n<command>\n```
            execute_blocks = re.findall(r"```execute\n(.*?)\n```", full_reply, re.DOTALL)
            if execute_blocks:
                for block in execute_blocks:
                    cmd = block.strip()
                    print(f"{C_G}┌─────────────────────────────────────────────────────────┐")
                    print(f"│ 🚨 {C_Y}PROPOSED REFLEX ACTION DETECTED{C_G}                       │")
                    print(f"├─────────────────────────────────────────────────────────┤")
                    # Safe layout printing
                    lines = [cmd[i:i+53] for i in range(0, len(cmd), 53)]
                    for l in lines:
                        print(f"│ {C_W}{l:<53}{C_G} │")
                    print(f"└─────────────────────────────────────────────────────────┘{C_R}")
                    
                    confirm = input(f"{C_Y}Authorize execution of this command? [y/N]: {C_R}").strip().lower()
                    if confirm == "y":
                        code, out = run_proposed_command(cmd)
                        print(f"\n{C_G}─── Output (Exit Code: {code}) ────────────────────────────────{C_R}")
                        print(f"{C_W}{out.strip()}{C_R}")
                        print(f"{C_G}────────────────────────────────────────────────────────────{C_R}\n")
                        
                        # Feed the action result back to the LLM and trigger another turn immediately!
                        feedback = f"[SYSTEM OUT (Command: '{cmd}', Exit Code: {code})]\n{out}"
                        history.append({"role": "user", "content": feedback})
                        auto_trigger = True
                        break # Executed one, loop again to let the LLM think about this step's output
                    else:
                        print(f"\n{C_Y}⚠️ Command execution rejected by user. Bypassing.{C_R}\n")
                        feedback = f"[SYSTEM NOTICE: The user explicitly REJECTED the execution of command: '{cmd}']"
                        history.append({"role": "user", "content": feedback})
                        
        except requests.exceptions.HTTPError as http_err:
            response_obj = http_err.response
            err_msg = ""
            if response_obj is not None:
                try:
                    err_msg = response_obj.text
                    err_json = response_obj.json()
                    if isinstance(err_json, dict):
                        err_msg = err_json.get("error", err_json.get("message", response_obj.text))
                        if isinstance(err_msg, dict):
                            err_msg = err_msg.get("message", str(err_msg))
                except Exception:
                    err_msg = response_obj.text
            
            # Cleanly print the client error box
            print(f"\n{C_Y}┌─────────────────────────────────────────────────────────┐")
            print(f"│ ❌ {C_R}API SERVER ERROR (HTTP {response_obj.status_code if response_obj else 'Unknown'})                   {C_Y}│")
            print(f"├─────────────────────────────────────────────────────────┤")
            # Format and wrap error message cleanly
            err_wrap = err_msg or str(http_err)
            err_lines = [err_wrap[i:i+53] for i in range(0, len(err_wrap), 53)]
            for el in err_lines:
                print(f"│ {C_W}{el:<53}{C_Y} │")
            print(f"└─────────────────────────────────────────────────────────┘{C_R}\n")
            
            # Check for missing model trigger (Self-Healing Autopilot)
            if err_msg and ("not found" in err_msg.lower() or "does not exist" in err_msg.lower() or "mismatch" in err_msg.lower()):
                print(f"\n{C_G}┌─────────────────────────────────────────────────────────┐")
                print(f"│ 🛠️  {C_Y}AUTONOMIC SELF-HEALING: MODEL NOT FOUND{C_G}              │")
                print(f"├─────────────────────────────────────────────────────────┤")
                print(f"│ Kenbun has detected that '{llm_model}' is not pulled.  │")
                print(f"│ Proposing automatic model pull...                       │")
                print(f"└─────────────────────────────────────────────────────────┘{C_R}")
                
                # Propose dynamic pull command inside compose container or host
                pull_cmd = f"docker exec -i portable_ollama ollama pull {llm_model} || ollama pull {llm_model}"
                print(f"\n{C_G}┌─────────────────────────────────────────────────────────┐")
                print(f"│ 🚨 {C_Y}PROPOSED SELF-HEALING ACTION{C_G}                          │")
                print(f"├─────────────────────────────────────────────────────────┤")
                print(f"│ {C_W}{pull_cmd[:53]:<53}{C_G} │")
                if len(pull_cmd) > 53:
                    print(f"│ {C_W}{pull_cmd[53:106]:<53}{C_G} │")
                print(f"└─────────────────────────────────────────────────────────┘{C_R}")
                
                confirm = input(f"{C_Y}Authorize model pull execution? [y/N]: {C_R}").strip().lower()
                if confirm == "y":
                    code, out = run_proposed_command(pull_cmd)
                    print(f"\n{C_G}─── Output (Exit Code: {code}) ────────────────────────────────{C_R}")
                    print(f"{C_W}{out.strip()}{C_R}")
                    print(f"{C_G}────────────────────────────────────────────────────────────{C_R}\n")
                    print(f"{C_G}✓ Model pull completed. Please retry your message!{C_R}\n")
                    # Pop the last user message to let the user clean retry
                    if history and history[-1]["role"] == "user":
                        history.pop()
            auto_trigger = False
            
        except KeyboardInterrupt:
            print(f"\n\n{C_P}🌸 Dialogue interrupted. Type /exit to close termchat.{C_R}\n")
            auto_trigger = False
        except Exception as e:
            # Format generic connection failures cleanly
            print(f"\n{C_Y}┌─────────────────────────────────────────────────────────┐")
            print(f"│ ❌ {C_R}API CONNECTION FAILURE                                {C_Y}│")
            print(f"├─────────────────────────────────────────────────────────┤")
            e_lines = [str(e)[i:i+53] for i in range(0, len(str(e)), 53)]
            for el in e_lines:
                print(f"│ {C_W}{el:<53}{C_Y} │")
            print(f"├─────────────────────────────────────────────────────────┤")
            print(f"│ Recommended Actions:                                    │")
            print(f"│ ➔ Verify the LLM Server URL is correct and active.     │")
            print(f"│ ➔ Run: docker compose up -d --build (if using Ollama)   │")
            print(f"└─────────────────────────────────────────────────────────┘{C_R}\n")
            auto_trigger = False

if __name__ == "__main__":
    main()
