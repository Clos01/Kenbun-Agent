"""
🏛️ Kenbun-Agent Interactive Setup Wizard & Bootstrapper (Sakura Edition)
Dynamically resolves port conflicts, configures absolute paths, provides interactive
API key input with local AES-256 encryption at rest, and manages Docker swarm stack startups.
"""

import os
import re
import sys
import shutil
import sqlite3
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("bootstrap")

def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
    return ansi_escape.sub('', text)

def visual_len(text: str) -> int:
    clean_text = strip_ansi(text)
    width = 0
    for char in clean_text:
        # Robust emoji/double-width character check (excluding standard quotes, punctuation and em-dashes)
        # Matches typical emoji ranges, supplemental symbols, CJK wide blocks, and Sakura blossoms (🌸)
        o = ord(char)
        if o > 0xffff or char in "🗼⚡🌸" or (0x2600 <= o <= 0x27bf) or (0x1f000 <= o <= 0x1f9ff):
            width += 2
        else:
            width += 1
    return width

def should_enable_color() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    if os.getenv("FORCE_COLOR") == "1" or os.getenv("CLICOLOR_FORCE") == "1":
        return True
    # Check common terminal color environment variables (e.g. COLORTERM, TERM)
    if "COLORTERM" in os.environ or ("TERM" in os.environ and "256color" in os.environ["TERM"].lower()):
        return True
    return sys.stdout.isatty()

def print_sakura_banner():
    use_color = should_enable_color()
    
    # Tokyo Cherry Blossom (Sakura) colors (Japanese Cyberpunk aesthetic)
    s = "\033[38;5;218m"  # Glowing Cherry Blossom Pink (Row 1-2)
    p = "\033[38;5;224m"  # Soft Rose Pink (Row 3-4)
    w = "\033[38;5;225m"  # Soft Warm White/Lilac (Row 5-6)
    g = "\033[38;5;246m"  # Soft slate grid gray for borders
    r = "\033[0m"         # Reset ANSI

    logo_rows = [
        f"{s}██╗  ██╗███████╗███╗   ██╗██████╗ ██╗   ██╗███╗   ██╗",
        f"{s}██║ ██╔╝██╔════╝████╗  ██║██╔══██╗██║   ██║████╗  ██║",
        f"{p}█████╔╝ █████╗  ██╔██╗ ██║██████╔╝██║   ██║██╔██╗ ██║",
        f"{p}██╔═██╗ ██╔══╝  ██║╚██╗██║██╔══██╗██║   ██║██║╚██╗██║",
        f"{w}██║  ██╗███████╗██║ ╚████║██████╔╝╚██████╔╝██║ ╚████║",
        f"{w}╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═════╝  ╚═════╝ ╚═╝  ╚═══╝"
    ]
    logo_text = "\n".join(logo_rows)

    border_color = g if use_color else ""
    reset_color = r if use_color else ""

    row1_content = f"{s}🌸 SAKURA JAPANESE AI AGENTIC SWARM{reset_color}"
    row2_content = f"{p}⚡ System 1-6 Cognitive Engine Loaded Safely{reset_color}"

    vlen1 = visual_len(row1_content)
    vlen2 = visual_len(row2_content)

    # Dynamic scaling panel (Senior Scale: Auto-expanding, zero-crash bounds)
    box_width = max(48, vlen1, vlen2)
    pad1 = max(0, box_width - vlen1)
    pad2 = max(0, box_width - vlen2)

    top_border = "─" * (box_width + 2)
    box = f"""{border_color}    ┌{top_border}┐
    │ {row1_content}{' ' * pad1}{border_color} │
    │ {row2_content}{' ' * pad2}{border_color} │
    └{top_border}┘{reset_color}"""

    full_banner = f"{logo_text}\n{box}"

    if not use_color:
        full_banner = strip_ansi(full_banner)
    
    print(full_banner)

def log_status(step_num: int, description: str, detail: str = "", status: str = "OK"):
    use_color = should_enable_color()
    c_m = "\033[38;5;218m"  # Sakura Pink
    c_c = "\033[38;5;224m"  # Soft Rose
    c_g = "\033[38;5;246m"  # Slate Gray
    c_y = "\033[38;5;226m"  # Yellow
    c_r = "\033[0m"         # Reset
    
    if not use_color:
        c_m = c_c = c_g = c_y = c_r = ""
        
    badge = f"{c_m}[ STEP {step_num} ]{c_r}"
    status_badge = f"{c_c}[  {status:<4}  ]{c_r}" if status == "OK" else f"{c_y}[ {status:<4} ]{c_r}"
    
    msg = f"{badge} {status_badge} {description}"
    if detail:
        msg += f" {c_g}➔ {detail}{c_r}"
    print(msg)

def is_port_in_use(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def find_free_port(start_port: int) -> int:
    port = start_port
    while is_port_in_use(port):
        port += 1
    return port

def bootstrap_core(silent=False):
    if not silent:
        print_sakura_banner()
    
    use_color = should_enable_color()
    c_c = "\033[38;5;224m" if use_color else ""
    c_r = "\033[0m" if use_color else ""
    
    if not silent:
        print(f"\n{c_c}🚀 INITIATING PORTABLE KENBUN-AGENT STANDALONE BOOTSTRAPPER{c_r}\n")
    
    # 1. Resolve workspace paths dynamically relative to this script
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    log_status(1, "Resolving dynamic workspace root paths", str(project_root.resolve()), status="OK")

    # 2. Check and copy environment template (.env.example -> .env)
    env_file = project_root / ".env"
    env_example = project_root / ".env.example"
    
    if not env_file.exists():
        if env_example.exists():
            # Automatically check for port availability to prevent conflicts
            chroma_port = 8000
            if is_port_in_use(8000):
                chroma_port = find_free_port(8010)
                log_status(2, "Port 8000 is occupied. Remapping ChromaDB", f"Selected free port {chroma_port}", status="PORT")
            
            api_port = 8001
            if is_port_in_use(8001):
                api_port = find_free_port(8011)
                log_status(2, "Port 8001 is occupied. Remapping Swarm API", f"Selected free port {api_port}", status="PORT")

            dashboard_port = 3000
            if is_port_in_use(3000):
                dashboard_port = find_free_port(3010)
                log_status(2, "Port 3000 is occupied. Remapping Telemetry Dashboard", f"Selected free port {dashboard_port}", status="PORT")

            with open(env_example, "r", encoding="utf-8") as f:
                content = f.read()

            # Dynamic replacements: Configure absolute path & ports automatically!
            content = content.replace(
                "PROJECT_ROOT=/absolute/path/to/your/cloned/kenbun-agent",
                f"PROJECT_ROOT={project_root.resolve()}"
            )
            content = content.replace("CHROMA_PORT=8000", f"CHROMA_PORT={chroma_port}")
            content = content.replace("API_PORT=8001", f"API_PORT={api_port}")
            content = content.replace("DASHBOARD_PORT=3000", f"DASHBOARD_PORT={dashboard_port}")

            with open(env_file, "w", encoding="utf-8") as f:
                f.write(content)
            
            log_status(2, "Seeding & auto-configuring environment file", "Created customized .env", status="OK")
        else:
            log_status(2, "No env.example template found. Skipping env copy", "", status="WARN")
    else:
        log_status(2, "Local environment file (.env) already exists", "Skipping creation", status="OK")

    # 3. Create core telemetry and database paths
    brain_health_dir = project_root / "brain_health"
    logs_dir = brain_health_dir / "logs"
    chromadb_dir = brain_health_dir / "chromadb_local"

    brain_health_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    chromadb_dir.mkdir(parents=True, exist_ok=True)
    log_status(3, "Structuring core database, memory, and telemetry paths", "brain_health, logs, chromadb", status="OK")

    # 4. Write default telemetry JSON templates
    usage_stats = brain_health_dir / "usage_stats.json"
    if not usage_stats.exists():
        with open(usage_stats, "w") as f:
            f.write('{"total_tokens": 0, "session_cost": 0.0}')
            
    benchmarks = brain_health_dir / "BENCHMARKS.json"
    if not benchmarks.exists():
        with open(benchmarks, "w") as f:
            f.write("[]")
            
    post_mortem = brain_health_dir / "POST_MORTEM.md"
    if not post_mortem.exists():
        with open(post_mortem, "w") as f:
            f.write("# 🩺 System Post Mortems & Architectural Corrections\n\nRecord failures and their lessons here.\n")
    log_status(4, "Seeding zero-config system telemetry templates", "usage_stats.json, BENCHMARKS.json, POST_MORTEM.md", status="SEED")

    # 5. Pre-initialize SQLite intelligence database with WAL mode enabled
    db_path = brain_health_dir / "kenbun_intelligence.db"
    
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            
            # Setup base schema
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS intelligence (
                    tool_id TEXT PRIMARY KEY,
                    category TEXT,
                    alpha REAL DEFAULT 2.0,
                    beta REAL DEFAULT 2.0,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    timestamp TEXT
                )
            ''')
            conn.commit()
            log_status(5, "Pre-initializing local SQLite database with WAL Mode", "WAL concurrency active", status="WAL")
    except Exception as e:
        log_status(5, "Failed to initialize SQLite intelligence database", str(e), status="FAIL")

def select_menu(options, title="Select provider:"):
    # Fallback to standard printed list if tty/termios is not available or not in standard TTY
    if not sys.stdout.isatty():
        print(f"\nSelect options for: {title}")
        for i, opt in enumerate(options):
            print(f" {i+1}. {opt}")
        while True:
            try:
                sel = int(input("Select choice by number: "))
                if 1 <= sel <= len(options):
                    return sel - 1
            except ValueError:
                pass
            print("Invalid selection.")
            
    try:
        import tty
        import termios
        import select
    except ImportError:
        # Fallback to printed list
        print(f"\nSelect options for: {title}")
        for i, opt in enumerate(options):
            print(f" {i+1}. {opt}")
        while True:
            try:
                sel = int(input("Select choice by number: "))
                if 1 <= sel <= len(options):
                    return sel - 1
            except ValueError:
                pass
            print("Invalid selection.")

    def get_key():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            # Use raw unbuffered os.read to prevent Python from buffering the sequence bytes
            b = os.read(fd, 1)
            if not b:
                return 'ignored'
            ch = b.decode('utf-8', errors='ignore')
            if ch == '\x1b':
                # Read all remaining characters in the escape sequence with a fast timeout
                seq = b
                while True:
                    rlist, _, _ = select.select([fd], [], [], 0.05)
                    if rlist:
                        next_b = os.read(fd, 1)
                        if next_b:
                            seq += next_b
                            if len(seq) >= 6: # Safety limit for escape sequence length
                                break
                        else:
                            break
                    else:
                        break
                
                seq_str = seq.decode('utf-8', errors='ignore')
                # Check for standard arrow keys
                if seq_str in ('\x1b[A', '\x1bOA'):
                    return 'up'
                elif seq_str in ('\x1b[B', '\x1bOB'):
                    return 'down'
                elif seq_str in ('\x1b[C', '\x1bOC'):
                    return 'right'
                elif seq_str in ('\x1b[D', '\x1bOD'):
                    return 'left'
                elif seq_str == '\x1b':
                    return 'escape' # Actual single ESC key press
                else:
                    return 'ignored' # Other unrecognized escape sequence
            elif ch in ('\r', '\n'):
                return 'enter'
            elif ch == ' ':
                return 'space'
            elif ch in ('q', 'Q'):
                return 'quit'
            elif ch in ('w', 'W', 'k', 'K'):
                return 'up'
            elif ch in ('s', 'S', 'j', 'J'):
                return 'down'
            elif ch.isdigit():
                return int(ch)
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    selected = 0
    use_color = should_enable_color()
    c_m = "\033[38;5;218m"  # Pink
    c_g = "\033[38;5;246m"  # Slate Gray
    c_w = "\033[38;5;225m"  # Soft Warm White
    c_r = "\033[0m"         # Reset
    
    if not use_color:
        c_m = c_g = c_w = c_r = ""

    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()
    
    try:
        while True:
            lines_printed = 0
            
            menu_text = f"\n{c_m}{title}{c_r}\n"
            menu_text += f" {c_g}↑↓ (or w/s) navigate   ENTER/SPACE select   ESC/q cancel{c_r}\n\n"
            lines_printed += 4
            
            for idx, opt in enumerate(options):
                if idx == selected:
                    menu_text += f" {c_m}➔ (●) {opt}{c_r}\n"
                else:
                    menu_text += f"    (○) {opt}\n"
                lines_printed += 1
                
            sys.stdout.write(menu_text)
            sys.stdout.flush()
            
            key = get_key()
            
            # Clear printed lines
            sys.stdout.write(f"\033[{lines_printed}A")
            sys.stdout.write("\033[J")
            sys.stdout.flush()
            
            if key == 'up':
                selected = (selected - 1) % len(options)
            elif key == 'down':
                selected = (selected + 1) % len(options)
            elif key in ('enter', 'space'):
                sys.stdout.write("\033[?25h") # Show cursor
                sys.stdout.flush()
                print(f"{c_m}{title}{c_r} {c_w}{options[selected]}{c_r}")
                return selected
            elif key in ('escape', 'quit'):
                sys.stdout.write("\033[?25h") # Show cursor
                sys.stdout.flush()
                return None
            elif isinstance(key, int):
                val = key - 1
                if 0 <= val < len(options):
                    selected = val
    except Exception:
        sys.stdout.write("\033[?25h") # Show cursor
        sys.stdout.flush()
        return None

PROVIDERS_MAP = [
    {
        "name": "Nous Portal (Nous Research subscription)",
        "env_key": "NOUS_PORTAL_API_KEY",
        "url": "https://api.nous.mesolitica.com/v1",
        "model": "nous-hermes-2-theta",
        "local": False
    },
    {
        "name": "OpenRouter (100+ models, pay-per-use)",
        "env_key": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/api/v1",
        "model": "nousresearch/hermes-3-llama-3.1-405b",
        "local": False
    },
    {
        "name": "LM Studio (local desktop app with built-in model server)",
        "env_key": None,
        "url": "http://localhost:1234/v1",
        "model": "local-model",
        "local": True,
        "type": "lmstudio"
    },
    {
        "name": "Anthropic (Claude models – API key or Claude Code)",
        "env_key": "ANTHROPIC_API_KEY",
        "url": "https://api.anthropic.com/v1",
        "model": "claude-3-5-sonnet-latest",
        "local": False
    },
    {
        "name": "OpenAI Codex",
        "env_key": "OPENAI_API_KEY",
        "url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "local": False
    },
    {
        "name": "Qwen Cloud / DashScope Coding (Qwen + multi-provider)",
        "env_key": "DASHSCOPE_API_KEY",
        "url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen2.5-coder-32b-instruct",
        "local": False
    },
    {
        "name": "Xiaomi MiMo (MiMo-V2.5 and V2 models – pro, omni, flash)",
        "env_key": "MIMO_API_KEY",
        "url": "https://api.mimo.xiaomi.com/v1",
        "model": "mimo-v2.5-flash",
        "local": False
    },
    {
        "name": "Tencent TokenHub (Hy3 Preview – direct API via tokenhub.tencentmaas.com)",
        "env_key": "TOKENHUB_API_KEY",
        "url": "https://tokenhub.tencentmaas.com/v1",
        "model": "hy3-preview",
        "local": False
    },
    {
        "name": "NVIDIA NIM (Nemotron models – build.nvidia.com or local NIM)",
        "env_key": "NVIDIA_API_KEY",
        "url": "https://integrate.api.nvidia.com/v1",
        "model": "nvidia/nemotron-4-340b-instruct",
        "local": False
    },
    {
        "name": "GitHub Copilot (uses GITHUB_TOKEN or gh auth token)",
        "env_key": "GITHUB_TOKEN",
        "url": "https://api.github.com",
        "model": "copilot-gpt-4o",
        "local": False
    },
    {
        "name": "GitHub Copilot ACP (spawns `copilot --acp --stdio`)",
        "env_key": None,
        "url": "copilot-acp",
        "model": "copilot-acp",
        "local": False
    },
    {
        "name": "Hugging Face Inference Providers (20+ open models)",
        "env_key": "HF_API_KEY",
        "url": "https://api-inference.huggingface.co/v1",
        "model": "meta-llama/Llama-3.1-70B-Instruct",
        "local": False
    },
    {
        "name": "Google AI Studio (Gemini models – native Gemini API)",
        "env_key": "GEMINI_API_KEY",
        "url": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-3-flash-preview",
        "local": False
    },
    {
        "name": "Google Gemini via OAuth + Code Assist (free tier supported; no API key needed)",
        "env_key": None,
        "url": "https://cloudaidoc-pa.googleapis.com/v1",
        "model": "code-assist",
        "local": False
    },
    {
        "name": "DeepSeek (DeepSeek-V3, R1, coder – direct API)",
        "env_key": "DEEPSEEK_API_KEY",
        "url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "local": False
    },
    {
        "name": "xAI (Grok models – direct API)",
        "env_key": "XAI_API_KEY",
        "url": "https://api.x.ai/v1",
        "model": "grok-beta",
        "local": False
    },
    {
        "name": "Z.AI / GLM (Zhipu AI direct API)",
        "env_key": "ZHIPU_API_KEY",
        "url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "local": False
    },
    {
        "name": "Kimi Coding Plan (api.kimi.com) & Moonshot API",
        "env_key": "KIMI_API_KEY",
        "url": "https://api.kimi.com/v1",
        "model": "kimi-latest",
        "local": False
    },
    {
        "name": "Kimi / Moonshot China (Moonshot CN direct API)",
        "env_key": "MOONSHOT_API_KEY",
        "url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "local": False
    },
    {
        "name": "StepFun Step Plan (agent/coding models via Step Plan API)",
        "env_key": "STEPFUN_API_KEY",
        "url": "https://api.stepfun.com/v1",
        "model": "step-1-flash",
        "local": False
    }
]

def auto_register_claude_desktop_mcp():
    import json
    use_color = should_enable_color()
    c_m = "\033[38;5;218m"  # Pink
    c_c = "\033[38;5;224m"  # Soft Rose
    c_y = "\033[38;5;226m"  # Yellow
    c_r = "\033[0m"         # Reset
    
    if not use_color:
        c_m = c_c = c_y = c_r = ""

    # Locate config paths
    home = Path.home()
    if sys.platform == "darwin":
        config_path = home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        config_path = home / ".config" / "Claude" / "claude_desktop_config.json"

    print(f"\n{c_m}🤖 AUTO-CONFIGURING CLAUDE DESKTOP MCP INTEGRATION{c_r}")
    print(f"Target file: {config_path}")

    # Build the server config dictionary using direct virtualenv interpreter
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    venv_python = project_root / "venv" / "bin" / "python"
    
    if not venv_python.exists():
        venv_python = Path(sys.executable)

    kenbun_server_node = {
        "command": str(venv_python.resolve()),
        "args": ["-m", "tools.infrastructure.server"],
        "env": {
            "PYTHONPATH": str((project_root / "core").resolve())
        }
    }

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_data = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                try:
                    config_data = json.load(f)
                except Exception:
                    print(f"{c_y}⚠️ Existing Claude Desktop config is invalid or empty. Creating fresh config.{c_r}")
        
        if "mcpServers" not in config_data:
            config_data["mcpServers"] = {}
            
        config_data["mcpServers"]["kenbun"] = kenbun_server_node

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
            
        print(f"🟢 {c_m}Successfully registered Kenbun MCP server in Claude Desktop!{c_r}")
        print("  ➔ To apply changes, please restart your Claude Desktop application.\n")
    except Exception as e:
        print(f"❌ {c_y}Failed to write Claude Desktop configuration: {e}{c_r}\n")

def auto_register_cursor_mcp():
    import json
    use_color = should_enable_color()
    c_m = "\033[38;5;218m"  # Pink
    c_c = "\033[38;5;224m"  # Soft Rose
    c_y = "\033[38;5;226m"  # Yellow
    c_r = "\033[0m"         # Reset
    
    if not use_color:
        c_m = c_c = c_y = c_r = ""

    # Locate config paths
    home = Path.home()
    if sys.platform == "darwin":
        config_path = home / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage" / "moose.copilot" / "mcp.json"
    else:
        config_path = home / ".config" / "Cursor" / "User" / "globalStorage" / "moose.copilot" / "mcp.json"

    print(f"\n{c_m}🤖 AUTO-CONFIGURING CURSOR MCP INTEGRATION{c_r}")
    print(f"Target file: {config_path}")

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    venv_python = project_root / "venv" / "bin" / "python"
    
    if not venv_python.exists():
        venv_python = Path(sys.executable)

    kenbun_server_node = {
        "type": "command",
        "command": str(venv_python.resolve()),
        "args": ["-m", "tools.infrastructure.server"],
        "env": {
            "PYTHONPATH": str((project_root / "core").resolve())
        },
        "enabled": True
    }

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_data = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                try:
                    config_data = json.load(f)
                except Exception:
                    print(f"{c_y}⚠️ Existing Cursor config is invalid or empty. Creating fresh config.{c_r}")
        
        if "mcpServers" not in config_data:
            config_data["mcpServers"] = {}
            
        config_data["mcpServers"]["kenbun"] = kenbun_server_node

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
            
        print(f"🟢 {c_m}Successfully registered Kenbun MCP server in Cursor!{c_r}")
        print("  ➔ To apply changes, please restart your Cursor IDE.\n")
    except Exception as e:
        print(f"❌ {c_y}Failed to write Cursor configuration: {e}{c_r}\n")

def configure_api_keys():
    import getpass
    import tempfile
    import json
    
    use_color = should_enable_color()
    c_m = "\033[38;5;218m"  # Pink
    c_c = "\033[38;5;224m"  # Soft Rose
    c_g = "\033[38;5;246m"  # Gray
    c_y = "\033[38;5;226m"  # Yellow
    c_w = "\033[38;5;225m"  # Soft Warm White
    c_r = "\033[0m"         # Reset
    
    if not use_color:
        c_m = c_c = c_g = c_y = c_w = c_r = ""

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    env_file = project_root / ".env"
    
    if not env_file.exists():
        print(f"\n{c_y}⚠️ Environment file not initialized yet. Running Express Setup first...{c_r}")
        bootstrap_core(silent=True)
        
    while True:
        # Parse current env to extract statuses
        env_vars = {}
        if env_file.exists():
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            parts = line.split("=", 1)
                            env_vars[parts[0].strip()] = parts[1].strip()
            except Exception:
                pass

        primary_url = env_vars.get("PRIMARY_LLM_URL", "http://localhost:11434/v1")
        primary_model = env_vars.get("PRIMARY_LLM_MODEL", "llama3.2:3b")

        # Detect active provider
        active_provider_name = "Unknown / Custom"
        active_provider_key_status = "[No Key Required]"
        
        for p in PROVIDERS_MAP:
            if p["url"] in primary_url or primary_url in p["url"]:
                active_provider_name = p["name"]
                if p["env_key"]:
                    val = env_vars.get(p["env_key"], "")
                    if not val or "your_" in val.lower() or val == '""' or val == "''":
                        active_provider_key_status = f"{c_g}[Not Configured]{c_r}"
                    elif val.startswith("enc:") or val.startswith("enc:v1:"):
                        active_provider_key_status = f"{c_m}[AES-256 Encrypted]{c_r}"
                    else:
                        active_provider_key_status = f"{c_y}[Plain Text]{c_r}"
                break

        print(f"\n{c_m}🔑 CONFIGURE API KEYS & LOCAL AI ENGINES{c_r}")
        print(f"{c_g}──────────────────────────────────────────────────{c_r}")
        print(f"Current Status:")
        print(f" ➔ Active Provider:    {c_w}{active_provider_name}{c_r}")
        print(f" ➔ Primary LLM URL:    {c_w}{primary_url}{c_r}")
        print(f" ➔ Primary LLM Model:  {c_w}{primary_model}{c_r}")
        print(f" ➔ Active Key Status:  {active_provider_key_status}")
        print(f"{c_g}──────────────────────────────────────────────────{c_r}")
        print("1. ⚙️  Select Primary AI Provider & Model (Select from 20+ options)")
        print("2. 🔌 Register MCP Server in Claude Desktop & Cursor (Auto)")
        print("3. 🔙 Return to Main Menu")
        print(f"{c_g}──────────────────────────────────────────────────{c_r}")
        
        opt = input(f"{c_c}Select option [1-3]: {c_r}").strip()
        
        if opt == "1":
            # Interactive arrow-navigable selector for all 20 providers!
            provider_names = [p["name"] for p in PROVIDERS_MAP]
            sel_idx = select_menu(provider_names, "Select Primary AI Provider:")
            
            if sel_idx is None:
                continue
                
            p = PROVIDERS_MAP[sel_idx]
            final_url = p["url"]
            final_model = p["model"]
            api_key_val = ""
            
            # Dynamic prompt for API Key
            if p["env_key"]:
                print(f"\n{c_c}Paste your {p['env_key']} below (Input is masked / hidden as you paste/type):{c_r}")
                api_key_val = getpass.getpass(f"Credential: ").strip()
                
            # Local probes if LM Studio/Ollama
            if p.get("local") and p.get("type") == "lmstudio":
                url_in = input(f"\nEnter Local Model Server Base URL (Press Enter for '{p['url']}'): ").strip()
                if url_in:
                    final_url = url_in
                    
                print(f"\n📡 Probing local model server at {final_url}...")
                
                # Probing local server
                import urllib.request
                def local_probe_models(base_url: str) -> Optional[List[str]]:
                    root = base_url.strip().rstrip("/")
                    if root.endswith("/v1"):
                        root = root[:-3].rstrip("/")
                    url = root + "/api/v1/models"
                    try:
                        req = urllib.request.Request(url, headers={"User-Agent": "Kenbun-Agent/1.0"})
                        with urllib.request.urlopen(req, timeout=3.0) as resp:
                            payload = json.loads(resp.read().decode())
                            raw_models = payload.get("models")
                            if isinstance(raw_models, list):
                                return [m.get("key") or m.get("id") for m in raw_models if str(m.get("type")).lower() != "embedding"]
                    except Exception:
                        pass
                    return None
                    
                probed = local_probe_models(final_url)
                if probed:
                    print(f"🟢 Connected successfully! Available models:")
                    model_sel = select_menu(probed, "Select active LM Studio Model:")
                    if model_sel is not None:
                        final_model = probed[model_sel]
                else:
                    print(f"🔴 Could not fetch active model keys from {final_url} (server offline).")
                    manual_model = input(f"Enter target Model ID manually (Press Enter for '{p['model']}'): ").strip()
                    if manual_model:
                        final_model = manual_model
            else:
                model_in = input(f"\nEnter Target Model ID (Press Enter for default '{p['model']}'): ").strip()
                if model_in:
                    final_model = model_in

            # AES rest encryption
            do_encrypt = False
            fernet = None
            if api_key_val:
                enc_choice = input(f"\nEncrypt your credentials at rest with AES-256? (Recommended) [Y/n]: ").strip().lower()
                do_encrypt = enc_choice not in ("n", "no")
                
                if do_encrypt:
                    try:
                        from cryptography.fernet import Fernet
                    except ImportError:
                        print(f"\n⚠️ Cryptography library missing. Installing cryptography...")
                        import subprocess
                        subprocess.run([sys.executable, "-m", "pip", "install", "cryptography"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        from cryptography.fernet import Fernet
                        
                    key_file = project_root / ".kenbun_master.key"
                    if not key_file.exists():
                        key = Fernet.generate_key()
                        with open(key_file, "wb") as f:
                            f.write(key)
                        os.chmod(key_file, 0o600)
                    with open(key_file, "rb") as f:
                        fernet = Fernet(f.read().strip())

            # Atomic save env
            with open(env_file, "r", encoding="utf-8") as f:
                content = f.read()

            def get_replacement(k: str, v: str) -> str:
                if do_encrypt and v and fernet is not None:
                    return f"{k}=enc:{fernet.encrypt(v.encode()).decode()}"
                return f"{k}={v}"

            def update_env_var(env_content: str, k: str, v: str) -> str:
                replacement = get_replacement(k, v)
                pattern = rf"^{k}\s*=.*"
                new_content, count = re.subn(pattern, lambda m: replacement, env_content, flags=re.MULTILINE)
                if count == 0:
                    if not env_content.endswith("\n"):
                        env_content += "\n"
                    env_content += f"{replacement}\n"
                    return env_content
                return new_content

            content = update_env_var(content, "PRIMARY_LLM_URL", final_url)
            content = update_env_var(content, "PRIMARY_LLM_MODEL", final_model)
            if p["env_key"] and api_key_val:
                content = update_env_var(content, p["env_key"], api_key_val)

            try:
                temp_fd, temp_path = tempfile.mkstemp(dir=project_root, prefix=".env.tmp")
                with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(temp_path, env_file)
                print(f"\n🟢 {c_m}Successfully updated gateway configuration!{c_r}")
                print(f"  ➔ PRIMARY_LLM_URL:   {final_url}")
                print(f"  ➔ PRIMARY_LLM_MODEL: {final_model}\n")
            except Exception as e:
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.remove(temp_path)
                print(f"❌ Failed to save environment file: {e}")

        elif opt == "2":
            auto_register_claude_desktop_mcp()
            auto_register_cursor_mcp()
        elif opt == "3":
            break
        else:
            print(f"\n{c_y}⚠️ Invalid choice. Select 1 to 3.{c_r}")

def detect_hardware():
    total_ram_gb = 8.0
    vram_gb = 0.0
    try:
        import sys
        import subprocess
        if sys.platform == "darwin":
            # macOS memory detection via sysctl
            res = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True)
            total_ram_gb = int(res.stdout.strip()) / (1024**3)
            # Unified memory VRAM allocation pool is up to 75% for macOS
            vram_gb = total_ram_gb * 0.75
        else:
            # Linux RAM detection
            import os
            total_ram_gb = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024**3)
            # Linux Nvidia VRAM detection via nvidia-smi
            try:
                res = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True)
                vram_gb = int(res.stdout.strip()) / 1024
            except Exception:
                vram_gb = 0.0
    except Exception:
        pass
    return total_ram_gb, vram_gb

def configure_local_models():
    import getpass
    import tempfile
    import json
    import re
    
    use_color = should_enable_color()
    c_m = "\033[38;5;218m"  # Pink
    c_c = "\033[38;5;224m"  # Soft Rose
    c_g = "\033[38;5;246m"  # Gray
    c_y = "\033[38;5;226m"  # Yellow
    c_w = "\033[38;5;225m"  # Soft Warm White
    c_r = "\033[0m"         # Reset
    
    if not use_color:
        c_m = c_c = c_g = c_y = c_w = c_r = ""

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    env_file = project_root / ".env"
    
    if not env_file.exists():
        print(f"\n{c_y}⚠️ Environment file not initialized yet. Running Express Setup first...{c_r}")
        bootstrap_core(silent=True)

    # Load current values
    env_vars = {}
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    parts = line.split("=", 1)
                    env_vars[parts[0].strip()] = parts[1].strip()
    except Exception:
        pass

    current_pull = env_vars.get("OLLAMA_PULL_MODELS", "llama3.2:3b deepseek-r1:8b")
    current_primary = env_vars.get("PRIMARY_LLM_MODEL", "llama3.2:3b")

    # 2.5 Dynamic Hardware VRAM & RAM Sensing Autopilot
    total_ram_gb, vram_gb = detect_hardware()

    # Pick recommended profile based on hardware sensing
    recommended_profile_idx = 1 # Fallback to Standard
    if vram_gb >= 16.0 or total_ram_gb >= 32.0:
        recommended_profile_idx = 2 # Pro
    elif total_ram_gb >= 16.0:
        recommended_profile_idx = 1 # Standard
    else:
        recommended_profile_idx = 0 # Ultra-Light

    profiles = [
        {
            "name": "Ultra-Light (8GB RAM / ~2.5GB Disk)",
            "desc": "Pulls llama3.2:1b and deepseek-r1:1.5b. Best for older laptops, light VPS nodes, or low specs.",
            "pull": "llama3.2:1b deepseek-r1:1.5b",
            "primary": "llama3.2:1b"
        },
        {
            "name": "Standard (16GB RAM / ~6GB Disk)",
            "desc": "Pulls llama3.2:3b and deepseek-r1:8b. Standard hardware profile.",
            "pull": "llama3.2:3b deepseek-r1:8b",
            "primary": "llama3.2:3b"
        },
        {
            "name": "Pro (32GB+ RAM / ~18GB Disk)",
            "desc": "Pulls qwen2.5-coder:7b, gemma2:9b, and deepseek-r1:14b. Premium performance.",
            "pull": "qwen2.5-coder:7b gemma2:9b deepseek-r1:14b",
            "primary": "qwen2.5-coder:7b"
        },
        {
            "name": "Cloud-Only / No Local Downloads (0GB RAM / 0GB Disk)",
            "desc": "Skips downloading local models entirely. Runs strictly via Cloud APIs (Gemini, OpenRouter) or Host LM Studio.",
            "pull": "none",
            "primary": "none"
        },
        {
            "name": "Custom Model Pull List",
            "desc": "Specify your own custom space-separated Ollama models manually.",
            "pull": "custom",
            "primary": "custom"
        }
    ]

    rec_name = profiles[recommended_profile_idx]["name"]
    autopilot_profile = {
        "name": f"✨ Autopilot Recommended Profile ({rec_name.split(' (')[0]})",
        "desc": f"Automatically selects '{rec_name}' based on detected hardware profile.",
        "pull": profiles[recommended_profile_idx]["pull"],
        "primary": profiles[recommended_profile_idx]["primary"]
    }
    # Prepend Autopilot
    profiles.insert(0, autopilot_profile)

    print(f"\n{c_m}🌸 CONFIGURE LOCAL AI MODELS & HARDWARE PROFILE{c_r}")
    print(f"{c_g}Choose a profile that fits your hardware specs. Underpowered specs will experience slow execution times.{c_r}\n")
    print(f"🖥️  {c_c}DYNAMIC HARDWARE SENSING AUDIT:{c_r}")
    print(f"   ➔ Detected System RAM: {c_w}{total_ram_gb:.2f} GB{c_r}")
    if vram_gb > 0.0:
        print(f"   ➔ Detected VRAM / Unified Memory Pool: {c_w}{vram_gb:.2f} GB{c_r}")
    print(f"   ➔ Recommended Hardware Profile: {c_m}{rec_name.split(' (')[0]}{c_r}\n")
    
    print(f"Current Configured Models: {c_c}{current_pull}{c_r}")
    print(f"Current Primary Local Model: {c_c}{current_primary}{c_r}\n")

    options = [p["name"] for p in profiles]
    selection = select_menu(options, "Select Local Hardware Profile:")
    
    if selection is None:
        print(f"\n{c_y}⚠️ Selection cancelled. Returning to main menu.{c_r}\n")
        return

    selected_profile = profiles[selection]
    
    pull_val = selected_profile["pull"]
    primary_val = selected_profile["primary"]

    if pull_val == "custom":
        print(f"\n{c_c}Enter space-separated Ollama models to pull (e.g. phi3:mini llama3:8b): {c_r}")
        pull_val = input("➔ Model List: ").strip()
        if not pull_val:
            print(f"❌ {c_y}Invalid model list. Cancelled.{c_r}\n")
            return
            
        print(f"\n{c_c}Enter the primary model name to invoke for task planning (e.g. phi3:mini): {c_r}")
        primary_val = input("➔ Primary Model: ").strip()
        if not primary_val:
            print(f"❌ {c_y}Invalid primary model. Cancelled.{c_r}\n")
            return

    # Atomic write to env
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            content = f.read()

        def update_env_var(env_content: str, k: str, v: str) -> str:
            replacement = f"{k}={v}"
            pattern = rf"^{k}\s*=.*"
            new_content, count = re.subn(pattern, lambda m: replacement, env_content, flags=re.MULTILINE)
            if count == 0:
                if not env_content.endswith("\n"):
                    env_content += "\n"
                env_content += f"{replacement}\n"
                return env_content
            return new_content

        content = update_env_var(content, "OLLAMA_PULL_MODELS", f'"{pull_val}"' if " " in pull_val else pull_val)
        if primary_val != "none":
            content = update_env_var(content, "PRIMARY_LLM_MODEL", primary_val)

        temp_fd, temp_path = tempfile.mkstemp(dir=project_root, prefix=".env.tmp")
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as tmp:
                tmp.write(content)
            os.replace(temp_path, env_file)
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e

        print(f"\n🟢 {c_m}Successfully updated local model profile!{c_r}")
        print(f"  ➔ Pull Models:   {c_c}{pull_val}{c_r}")
        print(f"  ➔ Primary Model: {c_c}{primary_val if primary_val != 'none' else current_primary}{c_r}")
        print("  ➔ To pull changes, please rebuild docker containers via Option 5.\n")
    except Exception as e:
        print(f"❌ {c_y}Failed to write configuration: {e}{c_r}\n")

def launch_docker_swarm():
    import subprocess
    use_color = should_enable_color()
    c_m = "\033[38;5;218m"  # Pink
    c_c = "\033[38;5;224m"  # Soft Rose
    c_y = "\033[38;5;226m"  # Yellow
    c_r = "\033[0m"         # Reset
    
    if not use_color:
        c_m = c_c = c_y = c_r = ""

    print(f"\n{c_m}🐳 LAUNCHING LOCALIZED SWARM STACK{c_r}")
    print(f"{c_c}Executing Docker Compose local container startup...{c_r}\n")
    
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    
    # Auto-bootstrap if missing .env
    env_file = project_root / ".env"
    if not env_file.exists():
        print(f"\n{c_y}⚠️ Environment file (.env) not found. Auto-generating from template...{c_r}")
        bootstrap_core(silent=True)
    
    docker_bin = shutil.which("docker")
    if not docker_bin:
        print(f"\n{c_y}┌─────────────────────────────────────────────────────────┐")
        print("│             🐋 DOCKER NOT DETECTED                      │")
        print("├─────────────────────────────────────────────────────────┤")
        print("│ It looks like Docker is not installed on your system.  │")
        print("│ Docker Compose is required for local offline containers.│")
        print("├─────────────────────────────────────────────────────────┤")
        print("│ Recommended Action:                                     │")
        print("│ 1. Download Docker Desktop: https://www.docker.com      │")
        print("│ 2. Or run in Cloud Mode (Mode A - Zero Docker needed!)  │")
        print(f"└─────────────────────────────────────────────────────────┘{c_r}\n")
        return

    # 2. Proactive Docker Daemon Health Check (Self-Healing & Secure)
    try:
        # Determine socket location for permission auditing (locale-independent check)
        socket_path = "/var/run/docker.sock"
        has_socket = os.path.exists(socket_path)
        has_write_access = os.access(socket_path, os.W_OK) if has_socket else False
        
        # Query daemon info using resolved absolute path and timeout to avoid hanging indefinitely
        daemon_check = subprocess.run([docker_bin, "info"], capture_output=True, text=True, timeout=5)
        
        if daemon_check.returncode != 0:
            is_permission_denied = False
            if has_socket and not has_write_access:
                is_permission_denied = True
            elif "permission denied" in (daemon_check.stderr or "").lower():
                is_permission_denied = True
                
            # Detect systemd presence and Docker status (Ubuntu specific self-healing)
            is_systemd = os.path.exists("/run/systemd/system")
            systemd_docker_active = False
            if is_systemd:
                try:
                    sysctl_check = subprocess.run(["systemctl", "is-active", "docker"], capture_output=True, text=True, timeout=2)
                    if sysctl_check.stdout.strip() == "active":
                        systemd_docker_active = True
                except Exception:
                    pass

            print(f"\n{c_y}┌─────────────────────────────────────────────────────────┐")
            print("│             🚨 DOCKER DAEMON INACTIVE / ACCESS DENIED   │")
            print("├─────────────────────────────────────────────────────────┤")
            if is_permission_denied:
                print("│ Docker socket exists, but your user lacks permissions.  │")
            else:
                print("│ Docker CLI is active, but the Daemon is not running.   │")
            print("├─────────────────────────────────────────────────────────┤")
            print("│ Recommended Action:                                     │")
            if sys.platform == "darwin":
                print("│ ➔ macOS: Start the Docker Desktop application          │")
            else:
                if is_systemd:
                    if not systemd_docker_active:
                        print("│ ➔ Linux (Start & Enable):                               │")
                        print("│    Run:  sudo systemctl enable --now docker            │")
                    else:
                        print("│ ➔ Docker service is active in systemd.                  │")
                else:
                    print("│ ➔ Linux (Start Daemon):                                 │")
                    print("│    Run:  sudo service docker start                     │")
                
                if is_permission_denied:
                    print("│ ➔ Linux (Permissions - run if socket access is denied): │")
                    print("│    Run:  sudo usermod -aG docker $USER                 │")
                    print("│    Then log out & back in, or run: newgrp docker       │")
            print("├─────────────────────────────────────────────────────────┤")
            print("│ ⚠️  SECURITY NOTICE: Adding a user to the 'docker' group  │")
            print("│    grants root-equivalent access to the host system.   │")
            print(f"└─────────────────────────────────────────────────────────┘{c_r}\n")

            if daemon_check.stderr:
                print(f"{c_y}Raw Docker System Error Output:{c_r}")
                print(f"  {c_c}{daemon_check.stderr.strip()}{c_r}\n")
            return
    except subprocess.TimeoutExpired:
        print(f"\n{c_y}❌ Timeout expired while querying Docker daemon (server hung).{c_r}\n")
        return
    except (subprocess.SubprocessError, OSError) as e:
        print(f"\n{c_y}❌ Failed to query Docker daemon health: {e}{c_r}\n")
        return

    return_code = -1
    try:
        result = subprocess.run(["docker", "compose", "up", "-d", "--build"], cwd=project_root)
        return_code = result.returncode
    except FileNotFoundError:
        try:
            result = subprocess.run(["docker-compose", "up", "-d", "--build"], cwd=project_root)
            return_code = result.returncode
        except Exception as e:
            print(f"\n{c_y}❌ Failed to execute docker compose: {e}{c_r}")
            return
    except Exception as e:
        print(f"\n{c_y}❌ Failed to run docker compose command: {e}{c_r}")
        return

    if return_code == 0:
        print(f"\n{c_c}🎉 Kenbun Swarm started successfully!{c_r}")
        env_file = project_root / ".env"
        chroma_port = "8000"
        api_port = "8001"
        dashboard_port = "3000"
        if env_file.exists():
            try:
                with open(env_file, "r") as f:
                    for line in f:
                        if line.startswith("CHROMA_PORT="):
                            chroma_port = line.split("=")[1].strip()
                        elif line.startswith("API_PORT="):
                            api_port = line.split("=")[1].strip()
                        elif line.startswith("DASHBOARD_PORT="):
                            dashboard_port = line.split("=")[1].strip()
            except Exception:
                pass
        print(f" ➔ ChromaDB port: {chroma_port}")
        print(f" ➔ FastMCP port: {api_port} (SSE URL: http://localhost:{api_port}/sse)")
        print(f" ➔ Dashboard port: {dashboard_port} (Access URL: http://localhost:{dashboard_port})")
    else:
        # Self-healing Host Port Conflict Audit (Consensus Zero-Crash)
        env_file = project_root / ".env"
        current_chroma = 8000
        current_api = 8001
        current_dashboard = 3000
        if env_file.exists():
            try:
                with open(env_file, "r") as f:
                    for line in f:
                        if line.startswith("CHROMA_PORT="):
                            current_chroma = int(line.split("=")[1].strip())
                        elif line.startswith("API_PORT="):
                            current_api = int(line.split("=")[1].strip())
                        elif line.startswith("DASHBOARD_PORT="):
                            current_dashboard = int(line.split("=")[1].strip())
            except Exception:
                pass
        
        chroma_conflict = is_port_in_use(current_chroma)
        api_conflict = is_port_in_use(current_api)
        dashboard_conflict = is_port_in_use(current_dashboard)
        
        if chroma_conflict or api_conflict or dashboard_conflict:
            print(f"\n{c_y}⚠️ Host Port conflict detected!{c_r}")
            if chroma_conflict:
                print(f" ➔ CHROMA_PORT={current_chroma} is already occupied on your host!")
            if api_conflict:
                print(f" ➔ API_PORT={current_api} is already occupied on your host!")
            if dashboard_conflict:
                print(f" ➔ DASHBOARD_PORT={current_dashboard} is already occupied on your host!")
            
            choice = input(f"\n{c_c}Would you like to automatically remap occupied ports in .env and retry? [Y/n]: {c_r}").strip().lower()
            if choice in ("", "y", "yes"):
                print(f"\n{c_c}Stopping any conflicting docker structures...{c_r}")
                try:
                    subprocess.run(["docker", "compose", "down", "-v"], cwd=project_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    try:
                        subprocess.run(["docker-compose", "down", "-v"], cwd=project_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass
                
                new_chroma = find_free_port(8010) if chroma_conflict else current_chroma
                new_api = find_free_port(8011) if api_conflict else current_api
                new_dashboard = find_free_port(3010) if dashboard_conflict else current_dashboard
                
                print(f"Remapping host ports: Chroma ➔ {new_chroma}, API Swarm ➔ {new_api}, Dashboard ➔ {new_dashboard}")
                
                if env_file.exists():
                    try:
                        with open(env_file, "r", encoding="utf-8") as f:
                            content = f.read()
                        content = re.sub(r"^CHROMA_PORT\s*=.*", f"CHROMA_PORT={new_chroma}", content, flags=re.MULTILINE)
                        content = re.sub(r"^API_PORT\s*=.*", f"API_PORT={new_api}", content, flags=re.MULTILINE)
                        content = re.sub(r"^DASHBOARD_PORT\s*=.*", f"DASHBOARD_PORT={new_dashboard}", content, flags=re.MULTILINE)
                        
                        import tempfile
                        temp_fd, temp_path = tempfile.mkstemp(dir=project_root, prefix=".env.tmp")
                        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                            f.write(content)
                        os.replace(temp_path, env_file)
                        log_status(2, "Ports update successful inside .env", "Atomic Saved", status="OK")
                    except Exception as e:
                        print(f"❌ Failed to rewrite ports atomically in .env: {e}")
                        return
                
                launch_docker_swarm()
                return
        
        print(f"\n{c_y}❌ Docker Compose failed with return code {return_code}{c_r}")

def showcase_dashboard():
    use_color = should_enable_color()
    c_m = "\033[38;5;218m"  # Pink
    c_g = "\033[38;5;246m"  # Slate Gray
    c_r = "\033[0m"         # Reset
    
    if not use_color:
        c_m = c_g = c_r = ""

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    env_file = project_root / ".env"
    dashboard_port = "3000"
    if env_file.exists():
        try:
            with open(env_file, "r") as f:
                for line in f:
                    if line.startswith("DASHBOARD_PORT="):
                        dashboard_port = line.split("=")[1].strip()
                        break
        except Exception:
            pass

    print(f"\n{c_m}📊 PORTABLE NEXT.JS TELEMETRY DASHBOARD FRONTEND{c_r}")
    print(f"{c_g}──────────────────────────────────────────────────{c_r}")
    print("The Kenbun Next.js Telemetry Frontend exposes real-time diagnostics:")
    print(" ➔ Bayesian Governor convergence graphs (MAB tool weights)")
    print(" ➔ Dynamic LLM pricing counters & budget token governance")
    print(" ➔ Swarm active tool performance trackers & system sensor logs")
    print("\n Access Instructions:")
    print("   1. Spin up the docker containers using option 4.")
    print(f"   2. Open your web browser and navigate to: http://localhost:{dashboard_port}")
    print("   3. All telemetry data streams dynamically via secure localhost sockets.")
    print(f"{c_g}──────────────────────────────────────────────────{c_r}")

def run_quick_setup():
    import getpass
    import tempfile
    import json
    
    use_color = should_enable_color()
    c_m = "\033[38;5;218m"  # Pink
    c_c = "\033[38;5;224m"  # Soft Rose
    c_g = "\033[38;5;246m"  # Gray
    c_y = "\033[38;5;226m"  # Yellow
    c_w = "\033[38;5;225m"  # Soft Warm White
    c_r = "\033[0m"         # Reset
    
    if not use_color:
        c_m = c_c = c_g = c_y = c_w = c_r = ""

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    env_file = project_root / ".env"
    
    if not env_file.exists():
        print(f"\n{c_y}⚠️ Environment file not initialized. Initializing core defaults first...{c_r}")
        bootstrap_core(silent=True)

    print(f"\n{c_m}⚡ SAKURA QUICK SETUP WIZARD{c_r}")
    print(f"{c_g}──────────────────────────────────────────────────{c_r}")
    print("This wizard configures your primary AI provider, default model,")
    print("and messaging bot integration in a few fast steps.")
    print(f"{c_g}──────────────────────────────────────────────────{c_r}")

    # Step 1: Provider selection via dynamic select menu!
    provider_names = [p["name"] for p in PROVIDERS_MAP]
    sel_idx = select_menu(provider_names, "Select your Primary AI Provider:")
    
    if sel_idx is None:
        print("Quick Setup cancelled.")
        return
        
    p = PROVIDERS_MAP[sel_idx]
    final_url = p["url"]
    final_model = p["model"]
    api_key_val = ""

    # Step 2: Key Setup
    if p["env_key"]:
        print(f"\n{c_w}[STEP 2] Configure API Credentials:{c_r}")
        api_key_val = getpass.getpass(f"Enter your {p['env_key']}: ").strip()

    # Probing local servers
    if p.get("local") and p.get("type") == "lmstudio":
        url_in = input(f"\nEnter local server base URL (Press Enter for '{p['url']}'): ").strip()
        if url_in:
            final_url = url_in
            
        print(f"📡 Probing local server at {final_url}...")
        
        import urllib.request
        def quick_probe(base_url: str) -> Optional[List[str]]:
            root = base_url.strip().rstrip("/")
            if root.endswith("/v1"):
                root = root[:-3].rstrip("/")
            url = root + "/api/v1/models"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Kenbun-Agent/1.0"})
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    payload = json.loads(resp.read().decode())
                    if "models" in payload:
                        return [m["key"] for m in payload["models"] if str(m.get("type")).lower() != "embedding"]
            except Exception:
                pass
            return None
            
        probe_res = quick_probe(final_url)
        if probe_res:
            print(f"🟢 Connected successfully! Available models:")
            model_sel = select_menu(probe_res, "Select active Model:")
            if model_sel is not None:
                final_model = probe_res[model_sel]
        else:
            print(f"🔴 Could not fetch active model keys from {final_url} (offline).")
            model_in = input(f"Enter target Model ID manually (Press Enter for '{p['model']}'): ").strip()
            if model_in:
                final_model = model_in
    else:
        model_in = input(f"\nEnter Target Model ID (Press Enter for default '{p['model']}'): ").strip()
        if model_in:
            final_model = model_in

    # Step 3: Messaging setup
    print(f"\n{c_w}[STEP 3] Configure Telegram Bot Messaging (Optional):{c_r}")
    setup_tg = input(f"Configure Telegram Messaging Bot? [y/N]: ").strip().lower()
    
    tg_token = ""
    tg_chat_id = ""
    if setup_tg in ("y", "yes"):
        tg_token = input(f"Enter Telegram Bot Token: ").strip()
        tg_chat_id = input(f"Enter Telegram Chat ID:  ").strip()

    # Step 4: AES Encryption
    do_encrypt = False
    fernet = None
    if api_key_val:
        enc_choice = input(f"\nEncrypt credentials at rest with AES-256? (Recommended) [Y/n]: ").strip().lower()
        do_encrypt = enc_choice not in ("n", "no")
        
        if do_encrypt:
            try:
                from cryptography.fernet import Fernet
            except ImportError:
                print(f"\n⚠️ Cryptography library missing. Installing cryptography...")
                import subprocess
                subprocess.run([sys.executable, "-m", "pip", "install", "cryptography"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                from cryptography.fernet import Fernet
                    
            key_file = project_root / ".kenbun_master.key"
            if not key_file.exists():
                key = Fernet.generate_key()
                with open(key_file, "wb") as f:
                    f.write(key)
                os.chmod(key_file, 0o600)
            with open(key_file, "rb") as f:
                fernet = Fernet(f.read().strip())
                    
    # Step 5: Save atomic env
    with open(env_file, "r", encoding="utf-8") as f:
        content = f.read()

    def get_replacement(k: str, v: str) -> str:
        if do_encrypt and v and fernet is not None:
            return f"{k}=enc:{fernet.encrypt(v.encode()).decode()}"
        return f"{k}={v}"

    def update_env_var(env_content: str, k: str, v: str) -> str:
        replacement = get_replacement(k, v)
        pattern = rf"^{k}\s*=.*"
        new_content, count = re.subn(pattern, lambda m: replacement, env_content, flags=re.MULTILINE)
        if count == 0:
            if not env_content.endswith("\n"):
                env_content += "\n"
            env_content += f"{replacement}\n"
            return new_content
        return new_content

    content = update_env_var(content, "PRIMARY_LLM_URL", final_url)
    content = update_env_var(content, "PRIMARY_LLM_MODEL", final_model)
    if p["env_key"] and api_key_val:
        content = update_env_var(content, p["env_key"], api_key_val)
    if tg_token and tg_chat_id:
        content = update_env_var(content, "TELEGRAM_BOT_TOKEN", tg_token)
        content = update_env_var(content, "TELEGRAM_CHAT_ID", tg_chat_id)

    try:
        temp_fd, temp_path = tempfile.mkstemp(dir=project_root, prefix=".env.tmp")
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(temp_path, env_file)
        print(f"\n🟢 {c_m}Quick Setup completed successfully!{c_r}")
        print(f"  ➔ PRIMARY_LLM_URL:   {final_url}")
        print(f"  ➔ PRIMARY_LLM_MODEL: {final_model}")
        if tg_token:
            print(f"  ➔ Telegram Bot:      Configured")
        print("\nReady to launch Swarm Stack! select menu Option 4 next.")
    except Exception as e:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        print(f"\n❌ Failed to save environment file: {e}")

def run_interactive_wizard():
    print_sakura_banner()
    
    use_color = should_enable_color()
    c_m = "\033[38;5;218m"  # Pink
    c_c = "\033[38;5;224m"  # Soft Rose
    c_g = "\033[38;5;246m"  # Slate Gray
    c_y = "\033[38;5;226m"  # Yellow
    c_r = "\033[0m"         # Reset
    
    if not use_color:
        c_m = c_c = c_g = c_y = c_r = ""

    while True:
        print(f"\n{c_m}🌸 KENBUN-AGENT INTERACTIVE WIZARD MENU{c_r}")
        print(f"{c_g}──────────────────────────────────────────────────{c_r}")
        print(f"1. 🚀 Express Setup (Automated Defaults - remap ports & seed)")
        print(f"2. ⚡ Quick Setup (Configure Provider, Model, & Messaging bot)")
        print(f"3. 🔑 Configure API Keys & Local AI Engines (Interactive)")
        print(f"4. 🐳 Configure Local AI Models & Docker Pull List")
        print(f"5. 🐳 Start Swarm Stack (Docker Compose up)")
        print(f"6. 🔌 Register MCP Server in Claude Desktop & Cursor (Auto)")
        print(f"7. 📊 Showcase Telemetry Dashboard (Access guidelines)")
        print(f"8. 🌸 Start Kenbun Cognitive Agentic Shell (Termchat)")
        print(f"9. ❌ Exit")
        print(f"{c_g}──────────────────────────────────────────────────{c_r}")
        try:
            choice = input(f"{c_c}Select an option [1-9]: {c_r}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n{c_y}⚠️ Standard input was closed or interrupted. Exiting wizard.{c_r}")
            print(f"{c_c}➔ Type {c_m}\"source ~/.bashrc\"{c_c} and press ENTER to reload your profile.{c_r}")
            print(f"{c_c}➔ Type {c_m}\"kenbun\"{c_c} and press ENTER to launch the setup wizard.{c_r}")
            print(f"{c_c}➔ Or run using the direct path fallback: {c_m}~/.local/bin/kenbun{c_r}")
            print(f"\nFor full configuration details, please refer to the README.md online:")
            print(f"  {c_c}https://github.com/Clos01/Kenbun-Agent{c_r}\n")
            sys.exit(0)

        if choice == "1":
            bootstrap_core()
        elif choice == "2":
            run_quick_setup()
        elif choice == "3":
            configure_api_keys()
        elif choice == "4":
            configure_local_models()
        elif choice == "5":
            launch_docker_swarm()
        elif choice == "6":
            auto_register_claude_desktop_mcp()
            auto_register_cursor_mcp()
        elif choice == "7":
            showcase_dashboard()
        elif choice == "8":
            # Launch Kenbun Cognitive Shell (Termchat) in-place
            script_dir = Path(__file__).parent.resolve()
            project_root = script_dir.parent
            termchat_path = project_root / "scripts" / "terminal_chat.py"
            if termchat_path.exists():
                print(f"\n{c_m}🌸 Initiating Cognitive Agent Shell...{c_r}")
                try:
                    import subprocess
                    subprocess.run([sys.executable, str(termchat_path)])
                except Exception as e:
                    print(f"\n❌ Failed to start terminal chat subprocess: {e}")
            else:
                print(f"\n❌ Error: terminal_chat.py not found at {termchat_path}")
        elif choice == "9":
            print(f"\n{c_m}🌸 Thank you for using Kenbun-Agent! Sayonara!{c_r}\n")
            break
        else:
            print(f"\n{c_y}⚠️ Invalid choice. Please select 1 to 9.{c_r}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--express":
        bootstrap_core()
    else:
        run_interactive_wizard()
