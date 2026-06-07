"""
🌸 Kenbun Banner
Rich-powered welcome banner with gradient ASCII logo and side-by-side panel layout.
Modeled after Hermes Agent's banner.py — uses rich.Panel + rich.Table.grid().
"""

import shutil
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.tools.cli.ui.skin_engine import SkinConfig, get_active_skin

# =============================================================================
# Kenbun ASCII Logo — Rich gradient markup (cherry blossom theme)
# =============================================================================

KENBUN_LOGO = """\
[bold #FF69B4]██╗  ██╗███████╗███╗   ██╗██████╗ ██╗   ██╗███╗   ██╗[/]
[bold #DA70D6]██║ ██╔╝██╔════╝████╗  ██║██╔══██╗██║   ██║████╗  ██║[/]
[#C25BCD]█████╔╝ █████╗  ██╔██╗ ██║██████╔╝██║   ██║██╔██╗ ██║[/]
[#A347B0]██╔═██╗ ██╔══╝  ██║╚██╗██║██╔══██╗██║   ██║██║╚██╗██║[/]
[#7B2D8B]██║  ██╗███████╗██║ ╚████║██████╔╝╚██████╔╝██║ ╚████║[/]
[#5C1A6E]╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═════╝  ╚═════╝ ╚═╝  ╚═══╝[/]"""

KENBUN_HERO = """\
[#FF69B4]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⡀⠀⣀⣀⠀⢀⣀⡀⠀⠀⠀⠀⠀⠀⠀[/]
[#DA70D6]⠀⠀⠀⠀⢀⣠⣴⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣦⣄⡀⠀⠀[/]
[#C25BCD]⠀⠀⢀⣾⡿⠋⣩⡿⣿⡿⠻⣿⡇⢠⡄⢸⣿⠟⢿⣿⢿⣍⠙⢿⣷⡀⠀[/]
[#A347B0]⠀⠀⠀⠉⠶⠟⠋⠀⠉⠀⢀⣈⣁⡈⢁⣈⣁⡀⠀⠉⠀⠙⠻⠶⠉⠀⠀[/]
[#8B35A0]⠀⠀⠀⠀⠀⠀⠀⠀⠀⣴⣿⡿⠛⢁⡈⠛⢿⣿⣦⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#7B2D8B]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠿⣿⣦⣤⣈⠁⢠⣴⣿⠿⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#5C1A6E]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠉⠻⣿⣿⣦⡉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#4B0082]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⢷⣦⣈⠛⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#DA70D6]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣴⠦⠈⠙⠿⣦⡄⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#FF69B4]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠸⣿⣤⡈⠁⢤⣿⠇⠀⠀⠀⠀⠀⠀⠀⠀[/]
[dim #7B2D8B]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀cognitive sovereignty⠀⠀⠀⠀⠀⠀[/]"""


def build_welcome_banner(
    console: Console,
    model: str,
    health: Optional[dict] = None,
    skin: Optional[SkinConfig] = None,
    version: str = "2.9.0",
    yolo_mode: bool = False,
) -> None:
    """
    Build and print the Kenbun welcome banner.
    Left column: hero art + model/status info.
    Right column: system health + quick-start commands.

    Args:
        console: Rich Console instance.
        model: Active model name (e.g. 'gemini-2.5-flash', 'gemma4:12b').
        health: Dict with keys 'ollama', 'chroma', 'docker' and their status strings.
        skin: Active SkinConfig (defaults to get_active_skin()).
        version: Kenbun version string.
        yolo_mode: Whether YOLO mode is active.
    """
    if skin is None:
        skin = get_active_skin()

    health = health or {}
    accent   = skin.get_color("banner_accent",  "#DA70D6")
    dim      = skin.get_color("banner_dim",     "#4B0082")
    text     = skin.get_color("banner_text",    "#FFF0F5")
    title_c  = skin.get_color("banner_title",   "#FF69B4")
    border_c = skin.get_color("banner_border",  "#7B2D8B")
    ok_c     = skin.get_color("ui_ok",          "#90EE90")
    err_c    = skin.get_color("ui_error",       "#FF6B6B")
    warn_c   = skin.get_color("ui_warn",        "#FFD700")

    # ── Left column ──────────────────────────────────────────────────────────
    hero = skin.banner_hero if skin.banner_hero else KENBUN_HERO
    model_short = model.split("/")[-1] if "/" in model else model
    if len(model_short) > 30:
        model_short = model_short[:27] + "..."

    tier_label = _detect_tier_label(model, accent, dim)
    left_lines = ["", hero, ""]
    left_lines.append(f"[{accent}]{model_short}[/] [dim {dim}]·[/] {tier_label}")

    if yolo_mode:
        left_lines.append(f"[bold red]⚡ YOLO MODE[/] [dim {dim}]— auto-execute active[/]")

    left_content = "\n".join(left_lines)

    # ── Right column ─────────────────────────────────────────────────────────
    right_lines = [f"[bold {accent}]System Health[/]"]

    ollama_status = health.get("ollama", "unknown")
    chroma_status = health.get("chroma", "unknown")
    docker_status = health.get("docker", "unknown")

    def _status_icon(s: str) -> str:
        s = s.lower()
        if any(x in s for x in ["online", "active", "running", "ok", "✓"]):
            return f"[{ok_c}]✓[/]"
        elif any(x in s for x in ["offline", "error", "fail", "✗"]):
            return f"[{err_c}]✗[/]"
        else:
            return f"[{warn_c}]?[/]"

    right_lines.append(f"  {_status_icon(ollama_status)} [dim {dim}]Ollama[/]  [{text}]{ollama_status}[/]")
    right_lines.append(f"  {_status_icon(chroma_status)} [dim {dim}]ChromaDB[/] [{text}]{chroma_status}[/]")
    right_lines.append(f"  {_status_icon(docker_status)} [dim {dim}]Docker[/]   [{text}]{docker_status}[/]")

    right_lines.append("")
    right_lines.append(f"[bold {accent}]Quick Commands[/]")
    right_lines.append(f"[dim {dim}]/tools[/]   [{text}]➟ List all harvested tools[/]")
    right_lines.append(f"[dim {dim}]/skills[/]  [{text}]➟ Design blueprints catalog[/]")
    right_lines.append(f"[dim {dim}]/run[/]     [{text}]➟ Execute a tool directly[/]")
    right_lines.append(f"[dim {dim}]/skin[/]    [{text}]➟ Change UI theme[/]")
    right_lines.append(f"[dim {dim}]/help[/]    [{text}]➟ Full command reference[/]")
    right_lines.append("")
    right_lines.append(f"[dim {dim}]Example: /run search_hivemind_concepts query=\"auth\"[/]")

    right_content = "\n".join(right_lines)

    # ── Assemble layout ───────────────────────────────────────────────────────
    layout = Table.grid(padding=(0, 3))
    layout.add_column("left",  justify="center")
    layout.add_column("right", justify="left")
    layout.add_row(left_content, right_content)

    agent_name = skin.get_branding("agent_name", "Kenbun Agent")
    title_markup = f"[bold {title_c}]{agent_name} v{version}[/]"

    panel = Panel(
        layout,
        title=title_markup,
        border_style=border_c,
        padding=(0, 2),
    )

    # Print logo (if terminal is wide enough) then the panel
    console.print()
    term_width = shutil.get_terminal_size().columns
    if term_width >= 90:
        logo = skin.banner_logo if skin.banner_logo else KENBUN_LOGO
        console.print(logo)
        console.print()
    console.print(panel)


def _detect_tier_label(model: str, accent: str, dim: str) -> str:
    """Return a Rich-markup tier label based on model name."""
    m = model.lower()
    if any(x in m for x in ["gemini", "gpt", "claude", "generativelanguage", "openai"]):
        return f"[dim {dim}]Cloud API[/]"
    elif any(x in m for x in ["gemma", "deepseek", "llama", "mistral", "phi", "qwen"]):
        return f"[{accent}]Local Ollama[/]"
    else:
        return f"[dim {dim}]Inference Engine[/]"
