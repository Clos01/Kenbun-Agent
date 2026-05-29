#!/usr/bin/env python3
"""
🌸 Kenbun Termchat (CLI Chat Interface)
Allows developers to chat directly with Kenbun-Agent's configured LLM 
and query design system concepts directly from the terminal.
"""
import os
import sys
import json
import re
import requests
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
        import subprocess
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
    print(f"██║  ██╗███████╗██║ ╚████║██████╔╝╚██████╔╝██║ ╚████║ {C_Y}🌸 TERMCHAT v2.5.0")
    print(f"{C_P}╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═════╝  ╚═════╝ ╚═╝  ╚═══╝{C_R}")
    print(f"{C_G}┌─────────────────────────────────────────────────────────┐")
    print(f"│ 🌸 Connected Engine:  {C_W}{llm_model:<34}{C_G}│")
    print(f"│ ⚡ API Gateway URL:   {C_W}{llm_url:<34}{C_G}│")
    print(f"│                                                         │")
    print(f"│ {C_Y}Available Slash Commands:{C_G}                               │")
    print(f"│   {C_C}/exit{C_G}     - Gracefully close Termchat                 │")
    print(f"│   {C_C}/reset{C_G}    - Clear dialogue history                    │")
    print(f"│   {C_C}/search{C_G}   - Direct search on UI-UX Pro Max database  │")
    print(f"│   {C_C}/system{C_G}   - Dump active environment parameters        │")
    print(f"└─────────────────────────────────────────────────────────┘{C_R}\n")

    history = [
        {"role": "system", "content": "You are Kenbun, a sovereign design intelligence and AI coding companion. Keep answers professional, concise, and structured in clean markdown layouts."}
    ]

    # Handle standard loop
    username = os.environ.get("USER", "amontano")
    
    while True:
        try:
            # Elegant prompt format
            user_input = input(f"{C_P}{username}@kenbun-termchat{C_R}:{C_G}~{C_R}$ ").strip()
            if not user_input:
                continue
                
            # Handle Slash Commands
            if user_input.startswith("/"):
                cmd_parts = user_input.split(" ", 1)
                cmd = cmd_parts[0].lower()
                
                if cmd == "/exit":
                    print(f"\n{C_P}🌸 Sayonara! Terminating session...{C_R}\n")
                    break
                    
                elif cmd == "/reset":
                    history = [history[0]]
                    print(f"\n{C_Y}🧹 Chat history successfully purged.{C_R}\n")
                    continue
                    
                elif cmd == "/system":
                    print(f"\n{C_G}🏛️  Active Environment Variables:{C_R}")
                    for k, v in env.items():
                        # Hide keys for safety
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

            # Standard chat flow
            history.append({"role": "user", "content": user_input})
            
            # Prepare streaming request to OpenAI-compatible endpoint (Ollama/LM Studio/API)
            headers = {"Content-Type": "application/json"}
            
            # Add API key if present
            if "OPENAI_API_KEY" in env and "openai" in llm_url.lower():
                headers["Authorization"] = f"Bearer {env['OPENAI_API_KEY']}"
            elif "DEEPSEEK_API_KEY" in env and "deepseek" in llm_url.lower():
                headers["Authorization"] = f"Bearer {env['DEEPSEEK_API_KEY']}"
            elif "GEMINI_API_KEY" in env and "gemini" in llm_url.lower():
                headers["Authorization"] = f"Bearer {env['GEMINI_API_KEY']}"

            payload = {
                "model": llm_model,
                "messages": history,
                "temperature": 0.3,
                "stream": True
            }
            
            endpoint = f"{llm_url}/chat/completions"
            print(f"\n{C_P}Kenbun 🌸:{C_R} ", end="", flush=True)
            
            # Streams results natively in the terminal
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
            
            # Add assistant response to history
            history.append({"role": "assistant", "content": full_reply})
            
        except KeyboardInterrupt:
            print(f"\n\n{C_P}🌸 Session interrupted. Type /exit to close termchat.{C_R}\n")
        except Exception as e:
            print(f"\n\n{C_Y}❌ Failed to query API: {e}{C_R}")
            print(f"{C_D}Please ensure the container stack is active and {llm_url} is accessible.{C_R}\n")

if __name__ == "__main__":
    main()
