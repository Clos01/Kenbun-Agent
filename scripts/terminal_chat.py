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
from pathlib import Path

# Color palettes (Limestone & Sakura themed)
C_P = "\033[95m" # Pink (Sakura)
C_G = "\033[92m" # Green (Limestone/Sage)
C_Y = "\033[93m" # Gold
C_C = "\033[96m" # Cyan
C_W = "\033[97m" # White
C_D = "\033[90m" # Grey
C_R = "\033[0m"  # Reset

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
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            # Strip quotes
                            val = parts[1].strip().strip('"').strip("'")
                            env[parts[0].strip()] = val
            break
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

def run_proposed_command(cmd):
    """Executes a proposed system shell command safely with stdout/stderr capture."""
    print(f"\n{C_Y}⚙️  Executing: {C_C}{cmd}{C_R}")
    try:
        # Run command with 45s timeout to prevent locking up
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=45
        )
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
    env = load_env_vars()
    
    # Extract configs
    llm_url = env.get("PRIMARY_LLM_URL", "http://localhost:11434/v1")
    llm_model = env.get("PRIMARY_LLM_MODEL", "llama3.2:3b")
    
    # Print beautiful banner
    print(f"\n{C_P}██╗  ██╗███████╗███╗   ██╗██████╗ ██╗   ██╗███╗   ██╗")
    print("██║ ██╔╝██╔════╝████╗  ██║██╔══██╗██║   ██║████╗  ██║")
    print("█████╔╝ █████╗  ██╔██╗ ██║██████╔╝██║   ██║██╔██╗ ██║")
    print("██╔═██╗ ██╔══╝  ██║╚██╗██║██╔══██╗██║   ██║██║╚██╗██║")
    print(f"██║  ██╗███████╗██║ ╚████║██████╔╝╚██████╔╝██║ ╚████║ {C_Y}🌸 AGENTIC SHELL v2.6.0")
    print(f"{C_P}╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═════╝  ╚═════╝ ╚═╝  ╚═══╝{C_R}")
    print(f"{C_G}┌─────────────────────────────────────────────────────────┐")
    print(f"│ 🌸 Active Agent:      {C_W}{llm_model:<34}{C_G}│")
    print(f"│ ⚡ Ollama Gateway URL: {C_W}{llm_url:<34}{C_G}│")
    print(f"│ ⚙️  Reflex Status:     {C_Y}ACTIVE (Human-in-the-Loop Safe)    {C_G}│")
    print(f"│                                                         │")
    print(f"│ {C_Y}Commands & Capabilities:{C_G}                                │")
    print(f"│   {C_C}/exit{C_G}     - Gracefully close Termchat                 │")
    print(f"│   {C_C}/reset{C_G}    - Clear dialogue history                    │")
    print(f"│   {C_C}/system{C_G}   - Dump active environment parameters        │")
    print(f"│   {C_C}/search{C_G}   - Direct search on UI-UX Pro Max database  │")
    print(f"│                                                         │")
    print(f"│ {C_P}Reflex Action Loop:{C_R}                                     │")
    print(f"│   Kenbun can propose shell scripts or VM command fixes  │")
    print(f"│   by responding in ````execute\\n<command>\\n``` blocks.   │")
    print(f"│   You can approve or deny command runs with {C_Y}[y/n]{C_P}.      │")
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
        "allowing you to analyze the result and continue your self-healing loop or system configuration!"
    )

    history = [
        {"role": "system", "content": system_prompt}
    ]

    username = os.environ.get("USER", "amontano")
    auto_trigger = False
    last_user_prompt = ""

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
                        print(f"\n{C_G}🏛️  Active Configuration Check:{C_R}")
                        for k, v in env.items():
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

                history.append({"role": "user", "content": user_input})
                last_user_prompt = user_input

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
                        
        except KeyboardInterrupt:
            print(f"\n\n{C_P}🌸 Dialogue interrupted. Type /exit to close termchat.{C_R}\n")
            auto_trigger = False
        except Exception as e:
            print(f"\n\n{C_Y}❌ Failed to query API: {e}{C_R}")
            print(f"{C_D}Please ensure the container stack is active and {llm_url} is accessible.{C_R}\n")
            auto_trigger = False

if __name__ == "__main__":
    main()
