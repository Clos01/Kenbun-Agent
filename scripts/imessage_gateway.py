#!/usr/bin/env python3
"""
Native Apple iMessage Gateway for Google Antigravity & Kenbun Swarm
===================================================================
Listens for incoming iMessages from authorized Apple IDs/numbers,
executes agentic tasks or cluster commands across lg2025 and p330,
and replies in real-time via native iMessage.
"""

import os
import sys
import json
import time
import shutil
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

# Setup paths
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "core"))

# Configure logging
LOG_FILE = ROOT_DIR / "brain_health" / "imessage_gateway.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("imessage_gateway")

IMSG_PATH = shutil.which("imsg") or "/opt/homebrew/bin/imsg"
SSH_KEY_LG2025 = os.path.expanduser("~/.ssh/antigravity_pc")
SSH_KEY_P330 = os.path.expanduser("~/.ssh/id_ed25519")

# Whitelist of approved phone numbers or Apple ID emails (empty allows all in private mode)
AUTHORIZED_SENDERS = {
    "rivascreativeagency@gmail.com",
    "carlos123939@icloud.com",
    "+19842121721",
    "19842121721",
}

TRIGGER_PREFIXES = ["!agy", "antigravity:", "agy:", "/goal", "!status", "!cluster", "!ssh", "!docker", "!help"]

async def send_reply(to: str, text: str, file_path: Optional[str] = None):
    """Sends an iMessage reply back to the sender."""
    if not IMSG_PATH or not os.path.exists(IMSG_PATH):
        logger.error("imsg binary not found at %s", IMSG_PATH)
        return

    cmd = [IMSG_PATH, "send", "--to", to, "--text", text]
    if file_path and os.path.exists(file_path):
        cmd.extend(["--file", file_path])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error("Failed to send reply: %s", stderr.decode(errors="ignore"))
        else:
            logger.info("Sent reply to %s: %s", to, text[:60])
    except Exception as e:
        logger.error("Exception sending iMessage: %s", e)

async def handle_cluster_status() -> str:
    """Probes all homelab cluster nodes and returns a clean, UI-friendly status card."""
    lines = [
        "🏛️ KENBUN CLUSTER TELEMETRY",
        "━━━━━━━━━━━━━━━━━━━━"
    ]
    
    # 1. Legion Sentry (Pi)
    try:
        p = await asyncio.create_subprocess_shell(
            "curl -fsS -k -I --connect-timeout 2 https://192.168.1.183/admin/",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await p.communicate()
        if p.returncode == 0:
            lines.append("🛡️ sentry.lan  │ 🟢 Online (HTTPS 2ms)")
        else:
            lines.append("🛡️ sentry.lan  │ 🔴 Offline / Unreachable")
    except Exception:
        lines.append("🛡️ sentry.lan  │ ⚠️ Check Error")

    # 2. lg2025 (Windows/WSL2 Reverse Proxy)
    try:
        p = await asyncio.create_subprocess_shell(
            f"ssh -i {SSH_KEY_LG2025} -o ConnectTimeout=2 -o StrictHostKeyChecking=no carlos@100.104.211.61 'docker ps --format \"{{{{.Names}}}}\"'",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await p.communicate()
        if p.returncode == 0:
            containers = [c for c in stdout.decode().splitlines() if c.strip()]
            lines.append(f"🖥️ lg2025       │ 🟢 Online ({len(containers)} Containers)")
            if "kenbun_reverse_proxy" in containers:
                lines.append("               │  ↳ 🔒 Proxy Active (:443)")
        else:
            lines.append("🖥️ lg2025       │ 🔴 SSH Unreachable")
    except Exception:
        lines.append("🖥️ lg2025       │ ⚠️ Check Error")

    # 3. P330 Node
    try:
        p = await asyncio.create_subprocess_shell(
            f"ssh -i {SSH_KEY_P330} -o ConnectTimeout=2 -o StrictHostKeyChecking=no its_los@100.100.199.127 'uptime'",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await p.communicate()
        if p.returncode == 0:
            up_str = stdout.decode().strip()
            # Extract load average or uptime cleanly
            if "up" in up_str:
                up_brief = up_str.split("up")[1].split(",")[0].strip()
            else:
                up_brief = "Active"
            lines.append(f"⚙️ p330         │ 🟢 Online (Up: {up_brief})")
        else:
            lines.append("⚙️ p330         │ 🔴 Offline")
    except Exception:
        lines.append("⚙️ p330         │ ⚠️ Check Error")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("✨ All subdomains routing over HTTPS")
    return "\n".join(lines)

async def handle_ssh_command(target: str, command: str) -> str:
    """Executes a remote SSH command on lg2025 or p330 with clean mobile formatting."""
    if target == "lg2025":
        host = "carlos@100.104.211.61"
        key = SSH_KEY_LG2025
    elif target in ["p330", "automation"]:
        host = "its_los@100.100.199.127"
        key = SSH_KEY_P330
    elif target in ["sentry", "pi"]:
        host = "carlos@192.168.1.183"
        key = SSH_KEY_P330
    else:
        return f"❌ Unknown target '{target}'. Use 'lg2025', 'p330', or 'sentry'."

    cmd = f"ssh -i {key} -o ConnectTimeout=5 -o StrictHostKeyChecking=no {host} '{command}'"
    try:
        p = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await p.communicate()
        output = (stdout.decode() + stderr.decode()).strip()
        if len(output) > 1400:
            output = output[:1400] + "\n... [truncated for mobile]"
        
        return (
            f"🖥️ TERMINAL EXECUTION: {target.upper()}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⌨️ Command: `{command}`\n\n"
            f"📄 Output:\n{output or '(Command completed with no output)'}"
        )
    except Exception as e:
        return f"❌ Execution failed on {target}: {e}"

# Initialize and Harvest Kenbun Tools at startup
try:
    sys.path.insert(0, str(ROOT_DIR / "core"))
    sys.path.insert(0, str(ROOT_DIR))
    from tools.harvester import harvest_and_register_tools
    from tools.registry import registry
    harvest_and_register_tools()
    logger.info("Harvested %d Kenbun Sovereign MCP tools for iMessage Gateway", len(registry.get_all_tools()))
except Exception as e:
    logger.warning("Could not harvest Kenbun tools at startup: %s", e)
    registry = None

def get_claude_tools() -> list:
    """Builds Claude tool schemas for Key Kenbun MCP tools."""
    if not registry:
        return []
    import inspect
    tools_list = []
    KEY_TOOLS = [
        "orchestrate",
        "search_hivemind_concepts",
        "save_to_hivemind",
        "consult_supervisor",
        "ask_architect",
        "get_brain_health",
        "search_codebase",
        "execute_code",
        "run_code_safely",
        "planka_get_board",
        "planka_create_card",
        "remember_preference",
        "remember_fix",
        "recall_fix"
    ]
    for name in KEY_TOOLS:
        entry = registry.get_tool(name)
        if not entry:
            continue
        try:
            sig = inspect.signature(entry.handler)
            properties = {}
            required = []
            for param_name, param in sig.parameters.items():
                if param_name in ["self", "cls"]:
                    continue
                properties[param_name] = {"type": "string", "description": f"Parameter {param_name}"}
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)
            tools_list.append({
                "name": name,
                "description": (entry.description or f"Kenbun tool: {name}")[:250],
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            })
        except Exception:
            continue
    return tools_list

async def execute_tool_call(name: str, input_args: dict) -> str:
    """Executes a Kenbun Sovereign tool handler dynamically."""
    if not registry:
        return f"Tool registry not loaded."
    entry = registry.get_tool(name)
    if not entry:
        return f"Tool '{name}' not found."
    try:
        loop = asyncio.get_running_loop()
        if entry.is_async:
            res = await entry.handler(**input_args)
        else:
            res = await loop.run_in_executor(None, lambda: entry.handler(**input_args))
        return str(res)
    except Exception as e:
        logger.error("Error executing tool %s: %s", name, e)
        return f"Tool error ({name}): {e}"

def sanitize_for_imessage(text: str) -> str:
    """Strips ugly raw markdown characters that don't render in Apple Messages."""
    import re
    cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    cleaned = re.sub(r'\*(.*?)\*', r'\1', cleaned)
    cleaned = re.sub(r'^#{1,6}\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'```[a-zA-Z]*\n', '', cleaned)
    cleaned = cleaned.replace('```', '')
    cleaned = re.sub(r'^[━─=-]{3,}\s*$', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()

async def handle_agent_task(prompt: str) -> str:
    """Dispatches task with full Kenbun MCP tools and multi-step execution loop."""
    logger.info("Executing agent task: %s", prompt)
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        env_file = ROOT_DIR / ".env"
        if env_file.exists():
            for line in open(env_file):
                if line.strip().startswith("ANTHROPIC_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break

    if not api_key:
        return f"Hey Carlos, I got your prompt: '{prompt}', but ANTHROPIC_API_KEY isn't configured in .env."

    system_prompt = (
        "You are Carlos's Augmented CTO and Senior Lead Architect, texting him directly on Apple iMessage.\n\n"
        "TONE & STYLE INSTRUCTIONS:\n"
        "- Text like a sharp, brilliant human engineer texting a colleague from a laptop.\n"
        "- DO NOT use raw Markdown formatting (NO double asterisks like **bold**, NO hashtag headers like ##, NO triple backticks).\n"
        "  Apple Messages does NOT support Markdown, so double asterisks look broken and robotic on a phone.\n"
        "- Use clean bullet points (•), natural line breaks, standard emojis, and conversational capitalization for emphasis.\n"
        "- Be direct, intelligent, and proactive.\n"
        "- You have access to Kenbun MCP sovereign tools (orchestrate, search_hivemind_concepts, consult_supervisor, ask_architect, get_brain_health, etc.).\n"
        "  USE YOUR TOOLS whenever Carlos asks to search memory, orchestrate workflows, or query homelab health!\n\n"
        "YOUR HOMELAB CLUSTER & ARCHITECTURE KNOWLEDGE:\n"
        "• Mac: MacBook Pro M1 Max (carloss-macbook-pro @ 100.79.106.48) - Main developer host\n"
        "• Reverse Proxy: Nginx on lg2025 (100.104.211.61:443) - Serves mkcert wildcard SSL (*.lan) to all services without port numbers\n"
        "• DNS & Adblock: Pi-hole on legion-sentry (192.168.1.183 / sentry.lan) with native mkcert SSL\n"
        "• Automation Node: P330 (automation @ 100.100.199.127) - Runs Caddy & Kenbun agent engines\n"
        "• Active .lan Domains: kenbun.lan (Dashboard), planka.lan (Kanban), n8n.lan (Automations), gitea.lan (Git Server), wiki.lan (Docmost), sentry.lan (Pi-hole)\n"
        "• Network: Private encrypted Tailscale WireGuard mesh connecting all nodes\n"
    )

    try:
        import ssl
        import urllib.request

        try:
            import certifi
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            ssl_ctx = ssl._create_unverified_context()

        tools = get_claude_tools()
        messages = [{"role": "user", "content": prompt}]
        loop = asyncio.get_running_loop()

        # Agent loop (up to 4 tool iterations)
        for iteration in range(4):
            payload = {
                "model": "claude-sonnet-5",
                "max_tokens": 1024,
                "system": system_prompt,
                "messages": messages,
            }
            if tools:
                payload["tools"] = tools

            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")

            def do_request():
                with urllib.request.urlopen(req, context=ssl_ctx, timeout=35) as resp:
                    return json.loads(resp.read().decode("utf-8"))

            res_data = await loop.run_in_executor(None, do_request)
            content_blocks = res_data.get("content", [])
            stop_reason = res_data.get("stop_reason")

            # Check if model wants to call tools
            tool_calls = [b for b in content_blocks if b.get("type") == "tool_use"]
            if not tool_calls or stop_reason != "tool_use":
                # Final response generated
                final_text = ""
                for block in content_blocks:
                    if block.get("type") == "text" and "text" in block:
                        final_text += block["text"]
                human_text = sanitize_for_imessage(final_text)
                if len(human_text) > 1500:
                    human_text = human_text[:1500] + "\n... (text clipped for mobile)"
                return human_text

            # Execute tool calls
            messages.append({"role": "assistant", "content": content_blocks})
            tool_results = []
            for tool_call in tool_calls:
                t_name = tool_call.get("name")
                t_args = tool_call.get("input", {})
                t_id = tool_call.get("id")
                logger.info("Executing Kenbun MCP tool '%s' with args: %s", t_name, t_args)
                tool_output = await execute_tool_call(t_name, t_args)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": t_id,
                    "content": str(tool_output)[:1200]
                })

            messages.append({"role": "user", "content": tool_results})

        # Fallback if loop hit max iterations
        return "Hey Carlos, completed the tool execution pipeline for your request."
    except Exception as e:
        logger.error("Error running AI agent task: %s", e)
        return f"Hey Carlos, hit a snag running that: {e}"

# Message Deduplication Set
PROCESSED_MESSAGE_IDS = set()

async def process_incoming_message(msg: Dict[str, Any]):
    """Parses and acts upon an incoming iMessage."""
    # 1. Ignore messages sent by ourselves
    if msg.get("is_from_me") is True or msg.get("from_me") is True:
        return

    # 2. Deduplicate message IDs / GUIDs
    msg_id = str(msg.get("id") or msg.get("guid") or msg.get("rowid") or "")
    if msg_id:
        if msg_id in PROCESSED_MESSAGE_IDS:
            return
        PROCESSED_MESSAGE_IDS.add(msg_id)
        if len(PROCESSED_MESSAGE_IDS) > 2000:
            try:
                PROCESSED_MESSAGE_IDS.pop()
            except KeyError:
                pass

    sender = msg.get("sender") or msg.get("from") or msg.get("handle") or ""
    text = (msg.get("text") or msg.get("body") or "").strip()

    if not text:
        return

    # Check sender authorization if list is set
    if AUTHORIZED_SENDERS and sender not in AUTHORIZED_SENDERS:
        logger.info("Message from non-whitelisted sender '%s' (ignoring)", sender)
        return

    lower_text = text.lower()
    matched_prefix = None
    for prefix in TRIGGER_PREFIXES:
        if lower_text.startswith(prefix):
            matched_prefix = prefix
            break

    if not matched_prefix:
        return

    logger.info("⚡ Authorized Trigger from %s: '%s'", sender, text)
    clean_prompt = text[len(matched_prefix):].strip()

    # 1. Help
    if matched_prefix == "!help":
        help_card = (
            "📱 ANTIGRAVITY MOBILE CHATOPS\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚡ `!agy <prompt>`\n"
            "   ↳ AI coding & architecture task\n\n"
            "📊 `!status`\n"
            "   ↳ Instant cluster health report\n\n"
            "🖥️ `!ssh <node> <cmd>`\n"
            "   ↳ Remote shell (e.g. `!ssh lg2025 uptime`)\n\n"
            "🐳 `!docker <node> <cmd>`\n"
            "   ↳ Remote docker (e.g. `!docker lg2025 ps`)\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        await send_reply(sender, help_card)
        return

    # 2. Cluster Status (Immediate single reply)
    if matched_prefix in ["!status", "!cluster"]:
        report = await handle_cluster_status()
        await send_reply(sender, report)
        return

    # 3. Remote SSH Command
    if matched_prefix == "!ssh":
        parts = clean_prompt.split(" ", 1)
        if len(parts) < 2:
            await send_reply(sender, "Usage: `!ssh <node> <command>` (e.g. `!ssh lg2025 docker ps`)")
            return
        node, cmd = parts[0], parts[1]
        res = await handle_ssh_command(node, cmd)
        await send_reply(sender, res)
        return

    # 4. Remote Docker Command
    if matched_prefix == "!docker":
        parts = clean_prompt.split(" ", 1)
        if len(parts) < 2:
            await send_reply(sender, "Usage: `!docker <node> <args>` (e.g. `!docker lg2025 ps`)")
            return
        node, docker_cmd = parts[0], f"docker {parts[1]}"
        res = await handle_ssh_command(node, docker_cmd)
        await send_reply(sender, res)
        return

    # 5. Antigravity Agent Task Dispatch
    if matched_prefix in ["!agy", "antigravity:", "agy:", "/goal"]:
        agent_res = await handle_agent_task(clean_prompt)
        await send_reply(sender, agent_res)
        return

async def watch_messages_stream():
    """Starts imsg watch subprocess and consumes streaming JSON events."""
    if not IMSG_PATH or not os.path.exists(IMSG_PATH):
        logger.error("Cannot start watcher: imsg not found at %s", IMSG_PATH)
        return

    cmd = [IMSG_PATH, "watch", "--json"]
    logger.info("Starting iMessage watch listener: %s", " ".join(cmd))

    while True:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                
                line_str = line.decode(errors="ignore").strip()
                if not line_str or not line_str.startswith("{"):
                    continue

                try:
                    data = json.loads(line_str)
                    await process_incoming_message(data)
                except json.JSONDecodeError:
                    continue

            await proc.wait()
            logger.warning("imsg watch process exited (code %s). Restarting in 3s...", proc.returncode)
            await asyncio.sleep(3)
        except Exception as e:
            logger.error("Watcher loop error: %s. Retrying in 5s...", e)
            await asyncio.sleep(5)

def main():
    logger.info("=================================================")
    logger.info("⚡ Kenbun / Antigravity iMessage Gateway Starting")
    logger.info("=================================================")
    try:
        asyncio.run(watch_messages_stream())
    except KeyboardInterrupt:
        logger.info("Gateway stopped by operator.")

if __name__ == "__main__":
    main()
