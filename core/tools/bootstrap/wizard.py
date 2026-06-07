from typing import Optional, List
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

def get_python_executable() -> str:
    # Resolve project root relative to this script safely
    project_root = Path(__file__).resolve().parent.parent
    if not project_root.is_dir():
        return sys.executable
        
    # 0. Allow direct developer override via env vars
    env_override = os.environ.get("KENBUN_PYTHON_EXECUTABLE") or os.environ.get("PROJECT_VENV_DIR")
    if env_override:
        override_path = Path(env_override)
        try:
            if override_path.is_dir():
                bin_dir = "Scripts" if sys.platform == "win32" else "bin"
                names = ("python.exe",) if sys.platform == "win32" else ("python", "python3")
                for name in names:
                    p = override_path / bin_dir / name
                    resolved = p.resolve(strict=True)
                    if resolved.is_file():
                        logger.debug(f"Resolved python override directory to: {resolved}")
                        return str(resolved)
            elif override_path.is_file():
                resolved = override_path.resolve(strict=True)
                logger.debug(f"Resolved python override executable to: {resolved}")
                return str(resolved)
        except Exception as e:
            logger.debug(f"Failed to resolve KENBUN_PYTHON_EXECUTABLE/PROJECT_VENV_DIR override: {e}")

    # 1. If we are already running inside an active virtual environment, return sys.executable
    if sys.prefix != sys.base_prefix:
        logger.debug(f"Running inside active virtual environment. Using sys.executable: {sys.executable}")
        return sys.executable

    # 2. Check environment variables for active virtualenv or conda environment
    env_keys = ("VIRTUAL_ENV", "CONDA_PREFIX")
    bin_dir = "Scripts" if sys.platform == "win32" else "bin"
    names = ("python.exe",) if sys.platform == "win32" else ("python", "python3")
    
    for key in env_keys:
        val = os.environ.get(key)
        if val:
            venv_dir = Path(val)
            for name in names:
                venv_path = venv_dir / bin_dir / name
                try:
                    resolved_venv = venv_path.resolve(strict=True)
                    if resolved_venv.is_file():
                        logger.debug(f"Resolved active environment ({key}) to: {resolved_venv}")
                        return str(resolved_venv)
                except Exception as e:
                    logger.debug(f"Failed to resolve path under environment {key}: {e}")

    # 3. Check for project-local virtual environments (escalated search scope for scalability)
    folders = (".venv", "venv", "env", ".env")
    for folder in folders:
        for name in names:
            venv_path = project_root / folder / bin_dir / name
            try:
                resolved_venv = venv_path.resolve(strict=True)
                # Enforce strict path containment boundary check to defeat path traversal/hijacking for local files
                if resolved_venv.is_file() and project_root.resolve() in resolved_venv.parents:
                    logger.debug(f"Resolved local virtual environment ({folder}) to: {resolved_venv}")
                    return str(resolved_venv)
            except Exception as e:
                logger.debug(f"Skipping path {venv_path} during local search: {e}")

    logger.debug(f"No virtual environment detected. Falling back to sys.executable: {sys.executable}")
    return sys.executable



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
    
    # 1. Resolve workspace paths dynamically
    cwd = Path.cwd()
    if (cwd / "docker-compose.yml").exists() or (cwd / ".env.example").exists():
        project_root = cwd
    else:
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
            ''')
            conn.commit()
            log_status(5, "Pre-initializing local SQLite database with WAL Mode", "WAL concurrency active", status="WAL")
    except Exception as e:
        log_status(5, "Failed to initialize SQLite intelligence database", str(e), status="FAIL")

def select_menu(options, title="Select provider:", selected=0):
    # Fallback to standard printed list if tty/termios is not available or not in standard TTY
    if not sys.stdout.isatty():
        print(f"\nSelect options for: {title}")
        for i, opt in enumerate(options):
            print(f" {i+1}. {opt}")
        while True:
            try:
                sel = input(f"Select choice by number (Default {selected+1}): ").strip()
                if not sel:
                    return selected
                sel = int(sel)
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
                sel = input(f"Select choice by number (Default {selected+1}): ").strip()
                if not sel:
                    return selected
                sel = int(sel)
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

    # Ensure initial selected index is within bounds
    if not (0 <= selected < len(options)):
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

MODEL_PRESETS = {
    "Google Gemini via OAuth": [
        "code-assist",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-2.0-pro-exp",
        "gemini-2.0-flash-thinking-exp",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ],
    "Google AI Studio": [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-2.0-pro-exp",
        "gemini-2.0-flash-thinking-exp",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ],
    "Anthropic": [
        "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-latest",
        "claude-3-opus-latest"
    ],
    "OpenAI Codex": [
        "gpt-4o-mini",
        "gpt-4o",
        "o1-mini",
        "o1-preview"
    ],
    "DeepSeek": [
        "deepseek-chat",
        "deepseek-coder",
        "deepseek-reasoner"
    ],
    "OpenRouter": [
        "nousresearch/hermes-3-llama-3.1-405b",
        "meta-llama/llama-3.3-70b-instruct",
        "deepseek/deepseek-chat",
        "google/gemini-flash-1.5"
    ]
}

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
        "url": "https://generativelanguage.googleapis.com/v1beta/openai",
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
    c_y = "\033[38;5;226m"  # Yellow
    c_r = "\033[0m"         # Reset
    
    if not use_color:
        c_m = c_y = c_r = ""

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
    venv_python = Path(get_python_executable())

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
    c_y = "\033[38;5;226m"  # Yellow
    c_r = "\033[0m"         # Reset
    
    if not use_color:
        c_m = c_y = c_r = ""

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
    venv_python = Path(get_python_executable())

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

def decrypt_value_local(val: str, project_root: Path) -> str:
    """Decrypts values that are encrypted with 'enc:' prefix using the repository master key."""
    if not isinstance(val, str) or not val.startswith("enc:"):
        return val
    try:
        from cryptography.fernet import Fernet
        key_file = project_root / ".kenbun_master.key"
        if not key_file.exists():
            key_file = project_root / "core" / ".kenbun_master.key"
        
        if key_file.exists():
            with open(key_file, "rb") as f:
                key = f.read().strip()
                f_obj = Fernet(key)
                return f_obj.decrypt(val[4:].encode()).decode()
    except Exception:
        pass
    return val

def resolve_display_url_and_model(url: str, model: str, project_root: Path) -> tuple[str, str]:
    if "cloudaidoc-pa.googleapis.com" not in url:
        return url, model
        
    project_id = None
    creds_file = project_root / ".google_credentials.json"
    if creds_file.exists():
        try:
            import json
            with open(creds_file, "r") as f:
                creds_data = json.load(f)
                project_id = creds_data.get("project_id") or creds_data.get("quota_project_id")
        except Exception:
            pass
    
    # Also check ADC credentials file for quota_project_id
    if not project_id:
        adc_path = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
        if adc_path.exists():
            try:
                import json
                with open(adc_path, "r") as f:
                    adc_data = json.load(f)
                    project_id = adc_data.get("quota_project_id")
            except Exception:
                pass
            
    if not project_id:
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT") or os.environ.get("PROJECT_ID")
        
    if project_id:
        location = os.environ.get("VERTEX_AI_LOCATION") or os.environ.get("GOOGLE_CLOUD_REGION") or "us-central1"
        res_url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/endpoints/openapi"
        res_model = "google/gemini-1.5-pro-001" if model == "code-assist" else model
        return res_url, res_model
    else:
        # No project ID found — show the actual configured values rather than misleading fallback
        display_model = "gemini-2.5-flash (via OAuth)" if model == "code-assist" else model
        return "generativelanguage.googleapis.com/v1beta (OAuth)", display_model

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
        primary_model = env_vars.get("PRIMARY_LLM_MODEL", "gemma-4-12b")

        # Decrypt for screen display to make it clear for the user
        decrypted_url = decrypt_value_local(primary_url, project_root)
        decrypted_model = decrypt_value_local(primary_model, project_root)
        display_url, display_model = resolve_display_url_and_model(decrypted_url, decrypted_model, project_root)

        # Detect active provider
        active_provider_name = "Unknown / Custom"
        active_provider_key_status = "[No Key Required]"
        
        for p in PROVIDERS_MAP:
            if p["url"] in decrypted_url or decrypted_url in p["url"] or p["url"] in primary_url or primary_url in p["url"]:
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
        
        # Display clean decrypted values with secure visual tag
        if primary_url.startswith("enc:"):
            print(f" ➔ Primary LLM URL:    {c_w}{display_url}{c_r} {c_g}[AES-256 Encrypted]{c_r}")
        else:
            print(f" ➔ Primary LLM URL:    {c_w}{display_url}{c_r}")
            
        if primary_model.startswith("enc:"):
            print(f" ➔ Primary LLM Model:  {c_w}{display_model}{c_r} {c_g}[AES-256 Encrypted]{c_r}")
        else:
            print(f" ➔ Primary LLM Model:  {c_w}{display_model}{c_r}")
            
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
            skip_key_update = False
            g_client_id = ""
            g_client_secret = ""
            do_encrypt = False
            fernet = None

            if p["name"].startswith("Google Gemini via OAuth"):
                print(f"\n{c_m}🌸 GOOGLE OAUTH + VERTEX AI CONFIGURATION{c_r}")
                print(f"{c_g}──────────────────────────────────────────────────{c_r}")
                print("To use Google Gemini via OAuth, you have two authentication options:")
                print("  [1] Google Cloud CLI login (Recommended: easiest setup)")
                print("  [2] Custom Google Cloud Console OAuth Client ID & Secret (Enterprise setup)")
                print(f"{c_g}──────────────────────────────────────────────────{c_r}")
                auth_opt = input(f"{c_c}Select option [1-2, default=1]: {c_r}").strip() or "1"
                
                if auth_opt == "2":
                    print(f"\n{c_m}┌──────────────────────────────────────────────────────────────────┐")
                    print("│             🛠️ GOOGLE DEVELOPER CONSOLE SETUP GUIDE              │")
                    print(f"├──────────────────────────────────────────────────────────────────┤")
                    print("│  1. Open: https://console.cloud.google.com                       │")
                    print("│  2. Create a new project or select an existing one.              │")
                    print("│  3. Navigate to: APIs & Services > OAuth consent screen          │")
                    print("│     - Choose 'External' (or 'Internal' if org).                  │")
                    print("│     - Fill in App Name (e.g. 'Kenbun Client'), User Support      │")
                    print("│       Email, and Developer Contact Email.                        │")
                    print("│     - Save & Continue. Under Scopes, add:                        │")
                    print("│       'https://www.googleapis.com/auth/cloud-platform'           │")
                    print("│     - Add your Gmail/workspace account under 'Test users'.       │")
                    print("│     - Click 'Back to Dashboard' and click 'PUBLISH APP'.         │")
                    print("│  4. Navigate to: APIs & Services > Credentials                   │")
                    print("│     - Click '+ CREATE CREDENTIALS' > 'OAuth client ID'.          │")
                    print("│     - Select Application Type: 'Desktop app'.                    │")
                    print("│     - Name it (e.g. 'Kenbun CLI') & click 'Create'.              │")
                    print("│  5. Click the Download (⬇️) icon next to the client ID to save    │")
                    print("│     the JSON credentials file.                                   │")
                    print(f"└──────────────────────────────────────────────────────────────────┘{c_r}")
                    
                    print(f"\n{c_c}Choose how to input your Custom OAuth Client credentials:{c_r}")
                    print("  [1] Paste absolute path to downloaded JSON file (Automatic & Easiest)")
                    print("  [2] Paste raw JSON content from downloaded file")
                    print("  [3] Enter Client ID and Client Secret manually")
                    
                    input_method = input(f"\nSelect input method [1-3, default=1]: ").strip() or "1"
                    
                    if input_method == "1":
                        json_path_str = input(f"\nEnter absolute path to the downloaded JSON file: ").strip()
                        if json_path_str.startswith("~"):
                            json_path = Path.home() / json_path_str[2:]
                        else:
                            json_path = Path(json_path_str)
                            
                        # Security: canonicalize path and enforce strict file boundaries & size limits
                        try:
                            resolved_path = json_path.resolve()
                            if resolved_path.exists() and resolved_path.is_file():
                                file_size = resolved_path.stat().st_size
                                if file_size > 102400:  # 100 KB limit
                                    print(f"\n❌ Security Error: File is too large ({file_size} bytes). Credentials JSON should be under 100 KB.")
                                    resolved_path = None
                            else:
                                resolved_path = None
                        except Exception:
                            resolved_path = None
                            
                        if resolved_path:
                            try:
                                import json
                                with open(resolved_path, "r", encoding="utf-8") as jf:
                                    data = json.load(jf)
                                for key in ("installed", "web"):
                                    if key in data and isinstance(data[key], dict):
                                        g_client_id = data[key].get("client_id", "")
                                        g_client_secret = data[key].get("client_secret", "")
                                if not g_client_id:
                                    g_client_id = data.get("client_id", "")
                                    g_client_secret = data.get("client_secret", "")
                            except Exception:
                                print(f"\n❌ Error parsing JSON credentials file.")
                        else:
                            print(f"\n❌ Invalid file path or access denied: {json_path_str}")
                            
                    elif input_method == "2":
                        print(f"\n{c_c}Paste raw JSON credentials content below and press Enter twice:{c_r}")
                        lines = []
                        # Security: prevent OOM/DoS by limiting maximum pasted lines
                        while len(lines) < 200:
                            line = sys.stdin.readline().strip()
                            if not line:
                                break
                            lines.append(line)
                        raw_json_str = "".join(lines)
                        if raw_json_str and len(raw_json_str) < 102400: # Max 100 KB payload
                            try:
                                import json
                                data = json.loads(raw_json_str)
                                for key in ("installed", "web"):
                                    if key in data and isinstance(data[key], dict):
                                        g_client_id = data[key].get("client_id", "")
                                        g_client_secret = data[key].get("client_secret", "")
                                if not g_client_id:
                                    g_client_id = data.get("client_id", "")
                                    g_client_secret = data.get("client_secret", "")
                            except Exception:
                                print(f"\n❌ Error parsing raw JSON content.")
                        else:
                            print(f"\n❌ Error: Paste content was empty or exceeded size limitations.")
                    else:
                        g_client_id = input(f"\nEnter Google Client ID: ").strip()
                        g_client_secret = input(f"Enter Google Client Secret: ").strip()
                        
                    if g_client_id and g_client_secret:
                        print(f"\n🟢 Successfully resolved credentials! Client ID starts with: {g_client_id[:15]}...")
                        enc_choice = input(f"\nEncrypt your Google Developer Console credentials at rest with AES-256? (Recommended) [Y/n]: ").strip().lower()
                        do_encrypt = enc_choice not in ("n", "no")
                        
                        if do_encrypt:
                            try:
                                from cryptography.fernet import Fernet
                            except ImportError:
                                print(f"\n⚠️ Cryptography library missing. Installing cryptography...")
                                import subprocess
                                subprocess.run([get_python_executable(), "-m", "pip", "install", "cryptography"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                from cryptography.fernet import Fernet
                                
                            key_file = project_root / ".kenbun_master.key"
                            if not key_file.exists():
                                key = Fernet.generate_key()
                                with open(key_file, "wb") as f:
                                    f.write(key)
                                os.chmod(key_file, 0o600)
                            with open(key_file, "rb") as f:
                                fernet = Fernet(f.read().strip())
                                
                        print(f"\n📡 Starting Google OAuth 2.0 authorization server on your machine...")
                        print(f"  This will open a browser window to authenticate. Please authorize the app.")
                        try:
                            try:
                                from google_auth_oauthlib.flow import InstalledAppFlow
                            except ImportError:
                                print(f"🔧 Installing required oauthlib libraries...")
                                import subprocess
                                subprocess.run([get_python_executable(), "-m", "pip", "install", "google-auth-oauthlib"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                from google_auth_oauthlib.flow import InstalledAppFlow
                                
                            scopes = ["https://www.googleapis.com/auth/cloud-platform"]
                            flow = InstalledAppFlow.from_client_config({
                                "installed": {
                                    "client_id": g_client_id,
                                    "client_secret": g_client_secret,
                                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                                    "token_uri": "https://oauth2.googleapis.com/token"
                                }
                            }, scopes=scopes)
                            
                            credentials = flow.run_local_server(port=0)
                            creds_file = project_root / ".google_credentials.json"
                            with open(creds_file, "w", encoding="utf-8") as f:
                                f.write(credentials.to_json())
                            print(f"\n🟢 {c_m}Successfully authorized custom client and saved credentials to:{c_r}")
                            print(f"  ➔ {creds_file}")
                        except Exception as e:
                            print(f"\n❌ Failed to run Google OAuth flow: {e}")
                            print(f"  Continuing with standard setup...")
                else:
                    print(f"\n{c_y}💡 Google Cloud CLI setup selected.{c_r}")
                    print(f"  This will open a browser window to authenticate with Google.")
                    print(f"  Kenbun will then auto-configure your project and quota settings.\n")
                    
                    run_gcloud = input(f"Ready to begin? [Y/n]: ").strip().lower()
                    if run_gcloud in ("n", "no"):
                        print(f"\n{c_g}Skipped. You can set up gcloud manually:{c_r}")
                        print(f"  1. gcloud auth application-default login")
                        print(f"  2. gcloud auth application-default set-quota-project YOUR_PROJECT_ID")
                    else:
                        import subprocess
                        
                        # ── Phase 1: Login ──
                        print(f"\n{c_m}[Phase 1/3] 🔐 Authenticating with Google Cloud...{c_r}")
                        try:
                            # Use 'login --update-adc' instead of 'application-default login'
                            # This authenticates BOTH the gcloud CLI (allowing project creation/listing)
                            # AND the Application Default Credentials (ADC) needed for the Python SDK.
                            subprocess.run(["gcloud", "auth", "login", "--update-adc"])
                        except FileNotFoundError:
                            print(f"\n❌ gcloud CLI not found. Install it first:")
                            print(f"  sudo snap install google-cloud-cli --classic")
                            print(f"  (or visit: https://cloud.google.com/sdk/docs/install)")
                            # Skip remaining phases
                            run_gcloud = "n"
                        except Exception as ge:
                            print(f"\n❌ Failed to run gcloud: {ge}")
                            run_gcloud = "n"
                        
                        if run_gcloud not in ("n", "no"):
                            # ── Phase 2: Auto-detect & set quota project ──
                            print(f"\n{c_m}[Phase 2/3] 📋 Configuring quota project...{c_r}")
                            
                            adc_path = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
                            has_quota_project = False
                            if adc_path.exists():
                                try:
                                    import json
                                    with open(adc_path, "r") as f:
                                        adc_data = json.load(f)
                                        has_quota_project = bool(adc_data.get("quota_project_id"))
                                        if has_quota_project:
                                            print(f"  ✅ Quota project already set: {c_w}{adc_data['quota_project_id']}{c_r}")
                                except Exception:
                                    pass
                            
                            if not has_quota_project:
                                detected_project = None
                                
                                # Strategy 1: Read active project from gcloud config
                                try:
                                    result = subprocess.run(
                                        ["gcloud", "config", "get-value", "project"],
                                        capture_output=True, text=True, timeout=10
                                    )
                                    candidate = result.stdout.strip()
                                    if candidate and candidate != "(unset)" and result.returncode == 0:
                                        detected_project = candidate
                                except Exception:
                                    pass
                                
                                if detected_project:
                                    print(f"  ✅ Auto-detected active project: {c_w}{detected_project}{c_r}")
                                    use_detected = input(f"  Use this project? [Y/n]: ").strip().lower()
                                    if use_detected in ("n", "no"):
                                        detected_project = None
                                
                                # Strategy 2: List all available projects as a dropdown
                                if not detected_project:
                                    print(f"\n  {c_g}Fetching your Google Cloud projects...{c_r}")
                                    try:
                                        result = subprocess.run(
                                            ["gcloud", "projects", "list", "--format=value(projectId,name)", "--limit=50"],
                                            capture_output=True, text=True, timeout=30
                                        )
                                        if result.returncode == 0 and result.stdout.strip():
                                            lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
                                            if lines:
                                                project_options = []
                                                project_ids = []
                                                for line in lines:
                                                    parts = line.split("\t", 1)
                                                    pid = parts[0].strip()
                                                    if not pid:
                                                        continue
                                                    pname = parts[1].strip() if len(parts) > 1 else ""
                                                    project_ids.append(pid)
                                                    label = f"{pid} ({pname})" if pname and pname != pid else pid
                                                    project_options.append(label)
                                                
                                                if len(project_options) == 1:
                                                    detected_project = project_ids[0]
                                                    print(f"  ✅ Found 1 project: {c_w}{detected_project}{c_r}")
                                                elif len(project_options) > 1:
                                                    sel = select_menu(project_options, "Select the Google Cloud project to use for Kenbun:")
                                                    if sel is not None:
                                                        detected_project = project_ids[sel]
                                    except Exception:
                                        pass
                                
                                # Strategy 3: No projects found — offer to create one or switch to API key
                                if not detected_project:
                                    import random, string
                                    print(f"\n  {c_y}No Google Cloud projects found on this account.{c_r}")
                                    print(f"  You have two options:\n")
                                    print(f"  {c_w}[1] Create a new Google Cloud project automatically (free){c_r}")
                                    print(f"      Kenbun will create a project and enable the Gemini API for you.")
                                    print(f"  {c_w}[2] Use a Google AI Studio API Key instead (simpler, no project needed){c_r}")
                                    print(f"      Get a free key at: {c_m}https://aistudio.google.com/apikey{c_r}\n")
                                    
                                    fallback_choice = input(f"  Select option [1-2, default=1]: ").strip() or "1"
                                    
                                    if fallback_choice == "1":
                                        # Auto-generate a project ID
                                        suffix = ''.join(random.choices(string.digits, k=6))
                                        auto_project_id = f"kenbun-agent-{suffix}"
                                        
                                        print(f"\n  {c_g}Creating project: {c_w}{auto_project_id}{c_r}")
                                        try:
                                            result = subprocess.run(
                                                ["gcloud", "projects", "create", auto_project_id, f"--name=Kenbun Agent"],
                                                capture_output=True, text=True, timeout=60
                                            )
                                            if result.returncode == 0:
                                                print(f"  ✅ Project created: {c_w}{auto_project_id}{c_r}")
                                                detected_project = auto_project_id
                                                
                                                # Set as active project
                                                subprocess.run(
                                                    ["gcloud", "config", "set", "project", auto_project_id],
                                                    capture_output=True, text=True, timeout=10
                                                )
                                                # Enable the Generative Language API
                                                print(f"  {c_g}Enabling Gemini (Generative Language) API...{c_r}")
                                                api_result = subprocess.run(
                                                    ["gcloud", "services", "enable", "generativelanguage.googleapis.com",
                                                     f"--project={auto_project_id}"],
                                                    capture_output=True, text=True, timeout=60
                                                )
                                                if api_result.returncode == 0:
                                                    print(f"  ✅ Generative Language API enabled")
                                                else:
                                                    api_err = api_result.stderr.strip()
                                                    if "billing" in api_err.lower():
                                                        print(f"  {c_y}⚠️ Billing must be enabled on the project to use this API.{c_r}")
                                                        print(f"  Visit: https://console.cloud.google.com/billing/linkedaccount?project={auto_project_id}")
                                                    else:
                                                        print(f"  {c_y}⚠️ Could not enable API: {api_err}{c_r}")
                                            else:
                                                create_err = result.stderr.strip()
                                                print(f"  {c_y}❌ Could not create project: {create_err}{c_r}")
                                                if "billing" in create_err.lower() or "quota" in create_err.lower():
                                                    print(f"  {c_g}Try Option 2 (AI Studio API Key) instead — it's free and simpler.{c_r}")
                                        except Exception as ce:
                                            print(f"  {c_y}❌ Project creation failed: {ce}{c_r}")
                                    
                                    elif fallback_choice == "2":
                                        # Switch to AI Studio API key provider
                                        print(f"\n  {c_m}Switching to Google AI Studio (API Key) provider...{c_r}")
                                        print(f"  Get your free API key at: {c_w}https://aistudio.google.com/apikey{c_r}")
                                        print(f"  Copy the key and paste it below.\n")
                                        
                                        import getpass
                                        api_key_input = getpass.getpass(f"  Paste your Gemini API Key (hidden): ").strip()
                                        
                                        if api_key_input:
                                            # Switch provider to AI Studio
                                            final_url = "https://generativelanguage.googleapis.com/v1beta/openai"
                                            final_model = "gemini-2.5-flash"
                                            
                                            # Write to .env
                                            import tempfile
                                            env_file_path = project_root / ".env"
                                            with open(env_file_path, "r", encoding="utf-8") as f:
                                                env_content = f.read()
                                            
                                            def _update_env(content, k, v):
                                                pattern = rf"^{k}\s*=.*"
                                                new_content, count = re.subn(pattern, f"{k}={v}", content, flags=re.MULTILINE)
                                                if count == 0:
                                                    content = content.rstrip("\n") + f"\n{k}={v}\n"
                                                    return content
                                                return new_content
                                            
                                            env_content = _update_env(env_content, "PRIMARY_LLM_URL", final_url)
                                            env_content = _update_env(env_content, "PRIMARY_LLM_MODEL", final_model)
                                            env_content = _update_env(env_content, "GEMINI_API_KEY", api_key_input)
                                            
                                            temp_fd, temp_path = tempfile.mkstemp(dir=project_root, prefix=".env.tmp")
                                            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                                                f.write(env_content)
                                            os.replace(temp_path, env_file_path)
                                            
                                            print(f"\n  🟢 {c_m}Switched to Google AI Studio!{c_r}")
                                            print(f"  ➔ PRIMARY_LLM_URL:   {final_url}")
                                            print(f"  ➔ PRIMARY_LLM_MODEL: {final_model}")
                                            print(f"  ➔ GEMINI_API_KEY:    [Configured]")
                                            # Skip the rest of OAuth setup since we switched providers
                                            skip_key_update = True
                                        else:
                                            print(f"  {c_y}No key entered. Skipping.{c_r}")
                                
                                # Apply the selected project
                                if detected_project:
                                    try:
                                        result = subprocess.run(
                                            ["gcloud", "auth", "application-default", "set-quota-project", detected_project],
                                            capture_output=True, text=True, timeout=15
                                        )
                                        if result.returncode == 0:
                                            print(f"\n  🟢 Quota project configured: {c_w}{detected_project}{c_r}")
                                        else:
                                            stderr_msg = result.stderr.strip()
                                            if "serviceusage.services.use" in stderr_msg.lower() or "permission" in stderr_msg.lower():
                                                print(f"\n  {c_y}⚠️ Permission note (non-blocking): {stderr_msg[:100]}{c_r}")
                                            else:
                                                print(f"\n  {c_y}⚠️ Note from gcloud: {stderr_msg}{c_r}")
                                    except Exception as qe:
                                        print(f"\n  {c_y}⚠️ Could not auto-set quota project: {qe}{c_r}")
                            
                            # ── Phase 3: Verify credentials are ready ──
                            print(f"\n{c_m}[Phase 3/3] ✅ Verifying credentials...{c_r}")
                            verified = False
                            if adc_path.exists():
                                try:
                                    import json
                                    with open(adc_path, "r") as f:
                                        final_adc = json.load(f)
                                    has_token = bool(final_adc.get("client_id") or final_adc.get("type"))
                                    has_project = bool(final_adc.get("quota_project_id"))
                                    
                                    if has_token and has_project:
                                        print(f"  ✅ OAuth credentials:  {c_w}Ready{c_r}")
                                        print(f"  ✅ Quota project:      {c_w}{final_adc['quota_project_id']}{c_r}")
                                        verified = True
                                    elif has_token:
                                        print(f"  ✅ OAuth credentials:  {c_w}Ready{c_r}")
                                        print(f"  ⚠️  Quota project:      {c_y}Not set (API calls may fail){c_r}")
                                    else:
                                        print(f"  ❌ Credentials file appears incomplete")
                                except Exception:
                                    print(f"  ❌ Could not read credentials file")
                            else:
                                print(f"  ❌ No credentials file found at {adc_path}")
                            
                            if verified:
                                print(f"\n  🟢 {c_m}Google OAuth is fully configured and ready!{c_r}")
            
            # Dynamic prompt for API Key
            if p["env_key"]:
                existing_key = env_vars.get(p["env_key"], "")
                is_existing = False
                if existing_key and "your_" not in existing_key.lower() and existing_key != '""' and existing_key != "''":
                    is_existing = True
                    print(f"\n{c_c}An existing value for {p['env_key']} was detected.{c_r}")
                    print(f"{c_g}Press ENTER to keep the existing key, or paste a new one to replace it.{c_r}")
                    api_key_val = getpass.getpass(f"Credential (Press Enter to keep existing): ").strip()
                else:
                    print(f"\n{c_c}Paste your {p['env_key']} below (Input is masked / hidden as you paste/type):{c_r}")
                    api_key_val = getpass.getpass(f"Credential: ").strip()

                if is_existing and not api_key_val:
                    skip_key_update = True
                
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
                matched_presets = None
                for key, presets in MODEL_PRESETS.items():
                    if key.lower() in p["name"].lower():
                        matched_presets = presets
                        break
                        
                if matched_presets:
                    menu_options = matched_presets + ["Custom model ID (Enter manually)"]
                    model_sel = select_menu(menu_options, f"Select Target Model for {p['name']}:")
                    if model_sel is not None:
                        if model_sel < len(matched_presets):
                            final_model = matched_presets[model_sel]
                        else:
                            manual_in = input(f"\nEnter Target Model ID manually (Press Enter for default '{p['model']}'): ").strip()
                            if manual_in:
                                final_model = manual_in
                else:
                    model_in = input(f"\nEnter Target Model ID (Press Enter for default '{p['model']}'): ").strip()
                    if model_in:
                        final_model = model_in

            # AES rest encryption
            do_encrypt = False
            fernet = None
            if api_key_val and not skip_key_update:
                enc_choice = input(f"\nEncrypt your credentials at rest with AES-256? (Recommended) [Y/n]: ").strip().lower()
                do_encrypt = enc_choice not in ("n", "no")
                
                if do_encrypt:
                    try:
                        from cryptography.fernet import Fernet
                    except ImportError:
                        print(f"\n⚠️ Cryptography library missing. Installing cryptography...")
                        import subprocess
                        subprocess.run([get_python_executable(), "-m", "pip", "install", "cryptography"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
            if p["env_key"] and api_key_val and not skip_key_update:
                content = update_env_var(content, p["env_key"], api_key_val)
            if g_client_id:
                content = update_env_var(content, "GOOGLE_CLIENT_ID", g_client_id)
            if g_client_secret:
                content = update_env_var(content, "GOOGLE_CLIENT_SECRET", g_client_secret)

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
    import tempfile
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

    current_pull = env_vars.get("OLLAMA_PULL_MODELS", "gemma-4-12b deepseek-r1:8b")
    current_primary = env_vars.get("PRIMARY_LLM_MODEL", "gemma-4-12b")

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
            "desc": "Pulls gemma-4:1b and deepseek-r1:1.5b. Best for older laptops, light VPS nodes, or low specs.",
            "pull": "gemma-4:1b deepseek-r1:1.5b",
            "primary": "gemma-4:1b"
        },
        {
            "name": "Standard (16GB RAM / ~6GB Disk)",
            "desc": "Pulls gemma-4-12b and deepseek-r1:8b. Standard hardware profile.",
            "pull": "gemma-4-12b deepseek-r1:8b",
            "primary": "gemma-4-12b"
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
        is_cloud_active = False
        current_url = env_vars.get("PRIMARY_LLM_URL", "http://localhost:11434/v1")
        decrypted_url = decrypt_value_local(current_url, project_root)
        if any(domain in decrypted_url.lower() for domain in ["googleapis.com", "api.openai.com", "api.anthropic.com", "api.deepseek.com"]):
            is_cloud_active = True

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
        
        if is_cloud_active:
            # Active Cloud Provider detected — do not overwrite it with local hardware model
            pass
        else:
            if primary_val != "none":
                # Symmetrically encrypt if they have Fernet active
                if current_primary.startswith("enc:") or env_vars.get("PRIMARY_LLM_MODEL", "").startswith("enc:"):
                    # Check if master key exists to encrypt
                    key_file = project_root / ".kenbun_master.key"
                    if not key_file.exists():
                        key_file = project_root / "core" / ".kenbun_master.key"
                    if key_file.exists():
                        from cryptography.fernet import Fernet
                        with open(key_file, "rb") as fk:
                            f_obj = Fernet(fk.read().strip())
                        encrypted_val = f"enc:{f_obj.encrypt(primary_val.encode()).decode()}"
                        content = update_env_var(content, "PRIMARY_LLM_MODEL", encrypted_val)
                    else:
                        content = update_env_var(content, "PRIMARY_LLM_MODEL", primary_val)
                else:
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
        if is_cloud_active:
            decrypted_model = decrypt_value_local(current_primary, project_root)
            print(f"  ➔ Primary Model: {c_c}{decrypted_model}{c_r} {c_g}[Keeping active Cloud Model]{c_r}")
            print(f"  ℹ️  Local models configured for Docker background stack only.")
        else:
            print(f"  ➔ Primary Model: {c_c}{primary_val if primary_val != 'none' else current_primary}{c_r}")
        print("  ➔ To pull changes, please rebuild docker containers via Option 5.\n")
    except Exception as e:
        print(f"❌ {c_y}Failed to write configuration: {e}{c_r}\n")

def launch_docker_swarm():
    import sys
    from pathlib import Path
    core_path = str(Path(__file__).resolve().parent.parent / "core")
    if core_path not in sys.path: pass
    from core.tools.infrastructure.docker_manager import launch_docker_swarm as _launch
    _launch()

def clean_docker_stack():
    import sys
    from pathlib import Path
    core_path = str(Path(__file__).resolve().parent.parent / "core")
    if core_path not in sys.path: pass
    from core.tools.infrastructure.docker_manager import clean_docker_stack as _clean
    _clean()

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
    skip_key_update = False

    # Step 2: Key Setup
    if p["env_key"]:
        print(f"\n{c_w}[STEP 2] Configure API Credentials:{c_r}")
        existing_key = env_vars.get(p["env_key"], "")
        is_existing = False
        if existing_key and "your_" not in existing_key.lower() and existing_key != '""' and existing_key != "''":
            is_existing = True
            print(f"{c_c}An existing value for {p['env_key']} was detected.{c_r}")
            print(f"{c_g}Press ENTER to keep the existing key, or paste a new one to replace it.{c_r}")
            api_key_val = getpass.getpass(f"Enter your {p['env_key']} (Press Enter to keep existing): ").strip()
        else:
            api_key_val = getpass.getpass(f"Enter your {p['env_key']}: ").strip()

        if is_existing and not api_key_val:
            skip_key_update = True

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
        matched_presets = None
        for key, presets in MODEL_PRESETS.items():
            if key.lower() in p["name"].lower():
                matched_presets = presets
                break
                
        if matched_presets:
            menu_options = matched_presets + ["Custom model ID (Enter manually)"]
            model_sel = select_menu(menu_options, f"Select Target Model for {p['name']}:")
            if model_sel is not None:
                if model_sel < len(matched_presets):
                    final_model = matched_presets[model_sel]
                else:
                    manual_in = input(f"\nEnter Target Model ID manually (Press Enter for default '{p['model']}'): ").strip()
                    if manual_in:
                        final_model = manual_in
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
    if api_key_val and not skip_key_update:
        enc_choice = input(f"\nEncrypt credentials at rest with AES-256? (Recommended) [Y/n]: ").strip().lower()
        do_encrypt = enc_choice not in ("n", "no")
        
        if do_encrypt:
            try:
                from cryptography.fernet import Fernet
            except ImportError:
                print(f"\n⚠️ Cryptography library missing. Installing cryptography...")
                import subprocess
                subprocess.run([get_python_executable(), "-m", "pip", "install", "cryptography"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
            return env_content
        return new_content

    content = update_env_var(content, "PRIMARY_LLM_URL", final_url)
    content = update_env_var(content, "PRIMARY_LLM_MODEL", final_model)
    if p["env_key"] and api_key_val and not skip_key_update:
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


def launch_termchat(project_root):
    termchat_path = project_root / "scripts" / "terminal_chat.py"
    if termchat_path.exists():
        use_color = should_enable_color()
        c_m = "[38;5;218m" if use_color else ""
        c_r = "[0m" if use_color else ""
        
        # Ensure prompt_toolkit is installed before launching terminal chat
        python_exe = get_python_executable()
        try:
            import prompt_toolkit  # noqa: F401
        except ImportError:
            print(f"\n{c_m}⚙️  Installing UI dependencies for Terminal Chat...{c_r}")
            import subprocess
            subprocess.run([python_exe, "-m", "pip", "install", "prompt_toolkit"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
        print(f"\n{c_m}🌸 Initiating Cognitive Agent Shell...{c_r}")
        try:
            import subprocess
            subprocess.run([python_exe, str(termchat_path)])
        except KeyboardInterrupt:
            pass # Graceful exit from Ctrl+C inside the terminal chat
        except Exception as e:
            print(f"\n❌ Failed to start terminal chat subprocess: {e}")
    else:
        print(f"\n❌ Error: terminal_chat.py not found at {termchat_path}")

def run_interactive_wizard():
    use_color = should_enable_color()
    c_m = "\033[38;5;218m"  # Pink
    c_c = "\033[38;5;224m"  # Soft Rose
    c_g = "\033[38;5;246m"  # Slate Gray
    c_r = "\033[0m"         # Reset
    
    if not use_color:
        c_m = c_c = c_g = c_r = ""

    options = [
        "🚀 Express Setup (Automated Defaults - remap ports & seed)",
        "⚡ Quick Setup (Configure Provider, Model, & Messaging bot)",
        "🔑 Configure API Keys & Local AI Engines (Interactive)",
        "🐳 Configure Local AI Models & Docker Pull List",
        "🐳 Start Swarm Stack (Docker Compose up)",
        "🧹 Clean/Reset Swarm Stack (Stop & delete Docker containers/images)",
        "🔌 Register MCP Server in Claude Desktop & Cursor (Auto)",
        "📊 Showcase Telemetry Dashboard (Access guidelines)",
        "🌸 Start Kenbun Cognitive Agentic Shell (Termchat)",
        "❌ Exit"
    ]

    guided_options = [
        "🚀 Express Setup (Automated Defaults - remap ports & seed)",
        "⚡ Quick Setup (Configure Provider, Model, & Messaging bot)",
        "🔑 Configure API Keys & Local AI Engines (Interactive)",
        "🐳 Configure Local AI Models & Docker Pull List",
        "🐳 Start Swarm Stack (Docker Compose up)",
        "🔌 Register MCP Server in Claude Desktop & Cursor (Auto)",
        "📊 Showcase Telemetry Dashboard (Access guidelines)",
        "🌸 Start Kenbun Cognitive Agentic Shell (Termchat)"
    ]

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    env_file = project_root / ".env"

    # Detect first-time setup
    first_time = False
    if not env_file.exists():
        first_time = True
    else:
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                content = f.read()
                has_default_path = "/absolute/path/to/your/cloned/kenbun-agent" in content
                has_default_key = "your_gemini_key_here" in content
                has_oauth = "generativelanguage.googleapis.com" in content or "vertexai" in content
                
                if has_default_path or (has_default_key and not has_oauth):
                    first_time = True
        except Exception:
            pass

    if first_time:
        import time
        # Print guided onboarding sequential sequence without letting them select
        steps_list = [
            ("Express Core Setup", bootstrap_core),
            ("Quick Setup (Provider & Credentials)", run_quick_setup),
            ("Configure API Keys Status", configure_api_keys),
            ("Configure Local Models & Hardware Profile", configure_local_models),
            ("Start Docker Swarm Stack", launch_docker_swarm),
            ("Register MCP in Claude & Cursor", lambda: (auto_register_claude_desktop_mcp(), auto_register_cursor_mcp())),
            ("Showcase Telemetry Dashboard", showcase_dashboard),
            ("Start Cognitive Shell (Termchat)", None)  # special handling for termchat launch
        ]
        
        for step_idx, (step_name, step_func) in enumerate(steps_list):
            # Clear screen
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()
            print_sakura_banner()
            
            print(f"\n{c_m}KENBUN-AGENT INTERACTIVE WIZARD MENU (GUIDED SETUP){c_r}")
            print(f"{c_g}──────────────────────────────────────────────────{c_r}")
            
            for idx, opt in enumerate(guided_options):
                if idx < step_idx:
                    print(f"    {c_g}(○) [Completed] {opt}{c_r}")
                elif idx == step_idx:
                    print(f" ➔ {c_m}(●) {opt}{c_r}")
                else:
                    print(f"    (○) {opt}")
                    
            print(f"{c_g}──────────────────────────────────────────────────{c_r}")
            print(f"{c_c}┌────────────────── 🌸 SAKURA GUIDED SETUP ACTIVE ──────────────────┐{c_r}")
            print(f"{c_c}│ We detected this is your first time setting up Kenbun-Agent.      │{c_r}")
            print(f"{c_c}│ To guarantee infinite scalability and perfect API gateway routing, │{c_r}")
            print(f"{c_c}│ we are walking you through the menu items sequentially.           │{c_r}")
            print(f"{c_c}│ You do not need to choose; we will execute them one-by-one!       │{c_r}")
            print(f"{c_c}└───────────────────────────────────────────────────────────────────┘{c_r}")
            
            print(f"\n{c_m}👉 Automatically executing Step {step_idx+1}/8: {step_name} in 2 seconds...{c_r}")
            time.sleep(2.0)
            
            if step_func is not None:
                step_func()
                # Pause briefly after completion so they can view results
                print(f"\n{c_c}🟢 Step {step_idx+1} completed successfully! Moving to next step...{c_r}")
                time.sleep(2.0)
            else:
                # Last step: Launch termchat in-place!
                launch_termchat(project_root)
                
        print(f"\n{c_m}🎉 Guided setup completed successfully! Welcome to Kenbun Swarm!{c_r}\n")
        # guided setup terminates, continue to standard loop if they don't exit Termchat
        first_time = False

    print_sakura_banner()
    current_selection = 0
    while True:
        selection = select_menu(options, "KENBUN-AGENT INTERACTIVE WIZARD MENU", selected=current_selection)
        
        if selection is None:
            print(f"\n{c_m}🌸 Thank you for using Kenbun-Agent! Sayonara!{c_r}\n")
            break

        if selection == 0:
            bootstrap_core()
            current_selection = 1
        elif selection == 1:
            run_quick_setup()
            current_selection = 2
        elif selection == 2:
            configure_api_keys()
            current_selection = 3
        elif selection == 3:
            configure_local_models()
            current_selection = 4
        elif selection == 4:
            launch_docker_swarm()
            current_selection = 5
        elif selection == 5:
            clean_docker_stack()
            current_selection = 6
        elif selection == 6:
            auto_register_claude_desktop_mcp()
            auto_register_cursor_mcp()
            current_selection = 7
        elif selection == 7:
            showcase_dashboard()
            current_selection = 8
        elif selection == 8:
            # Launch Kenbun Cognitive Shell (Termchat) in-place
            script_dir = Path(__file__).parent.resolve()
            project_root = script_dir.parent
            launch_termchat(project_root)
            current_selection = 8
        elif selection == 9:
            print(f"\n{c_m}🌸 Thank you for using Kenbun-Agent! Sayonara!{c_r}\n")
            break

def main():
        use_color = should_enable_color()
        c_m = "\033[38;5;218m" if use_color else ""
        c_c = "\033[38;5;224m" if use_color else ""
        c_y = "\033[38;5;226m" if use_color else ""
        c_r = "\033[0m" if use_color else ""
        
        if len(sys.argv) > 1:
            cmd = sys.argv[1].lower().strip()
            if cmd in ("--express", "express"):
                bootstrap_core()
            elif cmd in ("chat", "shell", "termchat"):
                # Launch Termchat in-place
                script_dir = Path(__file__).parent.resolve()
                project_root = script_dir.parent
                launch_termchat(project_root)
            elif cmd in ("start", "up"):
                launch_docker_swarm()
            elif cmd in ("stop", "down"):
                # Execute docker compose down
                script_dir = Path(__file__).parent.resolve()
                project_root = script_dir.parent
                print(f"\n{c_m}🐳 Stopping Swarm Stack...{c_r}")
                import subprocess
                try:
                    subprocess.run(["docker", "compose", "down"], cwd=str(project_root))
                except Exception:
                    try:
                        subprocess.run(["docker-compose", "down"], cwd=str(project_root))
                    except Exception as e:
                        print(f"❌ Failed to stop compose stack: {e}")
            elif cmd in ("mcp", "mcp-register"):
                auto_register_claude_desktop_mcp()
                auto_register_cursor_mcp()
            elif cmd in ("setup", "configure"):
                configure_api_keys()
            elif cmd in ("dashboard", "telemetry"):
                showcase_dashboard()
            elif cmd in ("--help", "-h", "help"):
                print(f"\n{c_m}🌸 KENBUN-AGENT CLI TOOL SHORTCUTS{c_r}")
                print(f"──────────────────────────────────────────────────")
                print(f"  {c_c}kenbun chat{c_r}       ➔ Start the Cognitive Agent Shell (Termchat) directly!")
                print(f"  {c_c}kenbun start{c_r}      ➔ Spin up the Docker stack in background!")
                print(f"  {c_c}kenbun stop{c_r}       ➔ Spin down the Docker stack!")
                print(f"  {c_c}kenbun setup{c_r}      ➔ Open the interactive API Key Configuration wizard!")
                print(f"  {c_c}kenbun mcp{c_r}        ➔ Register MCP server in Claude Desktop & Cursor automatically!")
                print(f"  {c_c}kenbun dashboard{c_r}  ➔ Show access guidelines for the Telemetry Dashboard!")
                print(f"  {c_c}kenbun express{c_r}    ➔ Initialize environment configurations with default seed!")
                print(f"  {c_c}kenbun list-tools{c_r} ➔ List all dynamic MCP tools and their signatures!")
                print(f"  {c_c}kenbun <tool>{c_r}     ➔ Execute any MCP tool (e.g., kenbun orchestrate, kenbun recall)")
                print(f"  {c_c}kenbun{c_r}            ➔ Launch full interactive Sakura setup menu (1-9)")
                print(f"──────────────────────────────────────────────────\n")
            elif cmd == "list-tools":
                import inspect
                try:
                    import core.tools.infrastructure.server as server
                    print(f"\n{c_m}🔮 KENBUN SWARM - DYNAMIC MCP TOOLS{c_r}")
                    print("──────────────────────────────────────────────────")
                    for name, obj in inspect.getmembers(server):
                        if inspect.isfunction(obj) and obj.__module__ == server.__name__ and not name.startswith("_"):
                            sig = inspect.signature(obj)
                            doc = inspect.getdoc(obj)
                            doc_summary = doc.split('\n')[0] if doc else "No description available."
                            print(f"🚀 {c_c}{name}{c_r}{sig}")
                            print(f"   {c_y}➔ {doc_summary}{c_r}\n")
                    print("──────────────────────────────────────────────────\n")
                except Exception as e:
                    print(f"❌ Failed to list tools: {e}")
            else:
                # Dynamic MCP tool dispatcher
    
                try:
                    import core.tools.infrastructure.server as server
                    
                    # Support 'search' as an alias for 'search_hivemind_concepts' and 'recall' as an alias for 'recall_fix'
                    actual_cmd = cmd
                    if cmd == "search": actual_cmd = "search_hivemind_concepts"
                    if cmd == "recall": actual_cmd = "search_hivemind_concepts" # Aligning with user expectation for recall
                    if cmd == "remember": actual_cmd = "save_to_hivemind"
                    
                    if hasattr(server, actual_cmd) and callable(getattr(server, actual_cmd)):
                        func = getattr(server, actual_cmd)
                        
                        kwargs = {}
                        args = []
                        
                        # Manual parsing for remember to support "kenbun remember title = content"
                        if cmd == "remember":
                            arg_str = " ".join(sys.argv[2:])
                            if "=" in arg_str:
                                title, content = arg_str.split("=", 1)
                                args.extend([title.strip(), content.strip(), "General"])
                                kwargs["category"] = "concepts"
                            else:
                                print("Usage: kenbun remember <title> = <content>")
                                sys.exit(1)
                        else:
                            if len(sys.argv) > 2:
                                # Reconstruct param string safely to preserve quotes
                                # We'll just use the raw string from sys.argv but properly grouped
                                # Actually, sys.argv already tokenizes. We just parse the tokens.
                                for token in sys.argv[2:]:
                                    if "=" in token:
                                        k, v = token.split("=", 1)
                                        kwargs[k] = v
                                    else:
                                        args.append(token)
                                        
                        print(func(*args, **kwargs))
                    else:
                        print(f"\n❌ Unknown command: {sys.argv[1]}")
                        print(f"Type {c_c}kenbun --help{c_r} to see all available command line shortcuts.\n")
                except Exception as e:
                    print(f"❌ Failed to execute tool '{cmd}': {e}")
        else:
            run_interactive_wizard()
