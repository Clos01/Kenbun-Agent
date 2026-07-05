"""
🌸 Kenbun UI Renderer
Decoupled presentation layer — wraps Rich primitives so engine.py
stays clean of direct Rich API calls. Supervisor-recommended pattern.

Usage:
    renderer = UIRenderer()
    renderer.print_banner(model="gemma4:12b", health={...})
    renderer.print_panel(["line 1", "line 2"], title="INFO")

    with renderer.live_stream() as live:
        live.update(Markdown(chunk))

    with renderer.spinner("Thinking...") as status:
        do_work()
"""

import sys
import shutil
import threading
from contextlib import contextmanager
from typing import Generator, List, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.status import Status
    from rich.text import Text
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from core.tools.cli.ui.skin_engine import SkinConfig, get_active_skin, set_active_skin, list_skins, get_active_skin_name
from core.tools.cli.ui.banner import build_welcome_banner


class NullLive:
    """Null Object pattern for rich.Live when rich is unavailable."""
    def update(self, *args, **kwargs) -> None:
        pass
    def refresh(self, *args, **kwargs) -> None:
        pass


class NullStatus:
    """Null Object pattern for rich.status.Status when rich is unavailable."""
    def update(self, *args, **kwargs) -> None:
        pass
    def start(self) -> None:
        pass
    def stop(self) -> None:
        pass
    def __enter__(self) -> "NullStatus":
        return self
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


class NullLiveContext:
    """Null context manager for rich.Live when rich is unavailable."""
    def __enter__(self) -> NullLive:
        return NullLive()
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


class NullConsole:
    """Null Object pattern for rich.Console when rich is unavailable."""
    def print(self, *args, **kwargs) -> None:
        pass

    @contextmanager
    def status(self, message: str, *args, **kwargs) -> Generator:
        print(f"⏳ {message}")
        yield NullStatus()


class UIRenderer:
    """
    Decoupled UI renderer for Kenbun terminal shell.
    All Rich calls go through this class — engine.py never imports Rich directly.

    Falls back gracefully to ANSI print() if Rich is unavailable.
    """
    _lock = threading.RLock()

    def __init__(self, skin: Optional[SkinConfig] = None):
        self._skin = skin or get_active_skin()
        
        if RICH_AVAILABLE:
            self._console = Console(highlight=False, markup=True)
            self._status_context = self._console.status
            # vertical_overflow="visible" keeps responses taller than the
            # terminal from being cropped mid-stream by Live's viewport.
            self._live_context = lambda: Live(
                console=self._console,
                refresh_per_second=15,
                vertical_overflow="visible",
            )
        else:
            self._console = NullConsole()
            self._status_context = self._console.status
            self._live_context = lambda: NullLiveContext()

    # ── Skin management ──────────────────────────────────────────────────────

    @property
    def skin(self) -> SkinConfig:
        return self._skin

    def switch_skin(self, name: str) -> str:
        """Switch active skin. Returns confirmation message."""
        available = [s["name"] for s in list_skins()]
        if name not in available:
            names = ", ".join(available)
            return f"Unknown skin '{name}'. Available: {names}"
        self._skin = set_active_skin(name)
        return f"🎨 Skin switched to '{name}'"

    def list_skins_table(self) -> str:
        """Return a formatted string listing all available skins."""
        skins = list_skins()
        active = get_active_skin_name()
        lines = ["Available skins:"]
        for s in skins:
            marker = " ← active" if s["name"] == active else ""
            lines.append(f"  • {s['name']:<12} — {s['description']}{marker}")
        return "\n".join(lines)

    # ── Banner ───────────────────────────────────────────────────────────────

    def print_banner(
        self,
        model: str,
        health: Optional[dict] = None,
        version: str = "2.9.0",
        yolo_mode: bool = False,
    ) -> None:
        """Print the full Kenbun welcome banner."""
        with self._lock:
            if isinstance(self._console, NullConsole):
                # Graceful ANSI fallback
                self._fallback_banner(model, health, version, yolo_mode)
            else:
                build_welcome_banner(
                    console=self._console,
                    model=model,
                    health=health,
                    skin=self._skin,
                    version=version,
                    yolo_mode=yolo_mode,
                )

    # ── Panel (replaces draw_box) ────────────────────────────────────────────

    def print_panel(
        self,
        lines: List[str],
        title: str = "",
        style: str = "default",
    ) -> None:
        """
        Print a styled panel. Replaces the old draw_box() function.

        Args:
            lines: List of strings (plain text, or ANSI, or Rich markup).
            title: Panel title text (plain text or ANSI).
            style: One of 'default', 'success', 'warning', 'error', 'info', 'yolo'.
        """
        with self._lock:
            if isinstance(self._console, NullConsole):
                self._fallback_box(lines, title)
                return

            border_color = self._resolve_panel_color(style)
            content = "\n".join(lines)

            if "\033[" in content:
                renderable = Text.from_ansi(content)
            else:
                renderable = content

            title_renderable = None
            if title:
                if "\033[" in title:
                    title_renderable = Text.from_ansi(title)
                else:
                    title_renderable = Text.from_markup(f"[bold]{title}[/]")

            panel = Panel(
                renderable,
                title=title_renderable,
                border_style=border_color,
                padding=(0, 1),
            )
            self._console.print(panel)

    def _resolve_panel_color(self, style: str) -> str:
        s = self._skin
        mapping = {
            "default": s.get_color("banner_border", "#7B2D8B"),
            "success": s.get_color("ui_ok",         "#90EE90"),
            "warning": s.get_color("ui_warn",        "#FFD700"),
            "error":   s.get_color("ui_error",       "#FF6B6B"),
            "info":    s.get_color("banner_accent",  "#DA70D6"),
            "yolo":    "#FF0033",
        }
        return mapping.get(style, mapping["default"])

    # ── Response printing ────────────────────────────────────────────────────

    def print_response_header(self, model_name: str) -> None:
        """Print the response label before an AI reply."""
        with self._lock:
            if isinstance(self._console, NullConsole):
                sys.stdout.write(f"\n🌸 Kenbun ({model_name}) ▸ ")
                sys.stdout.flush()
            else:
                label = self._skin.get_branding("response_label", " 🌸 Kenbun ")
                accent = self._skin.get_color("banner_accent", "#DA70D6")
                border = self._skin.get_color("response_border", "#FF69B4")
                self._console.print(
                    f"[{border}]─[/][bold {accent}]{label} ({model_name})[/][{border}]▸[/]",
                    end=" ",
                )

    def print_markdown(self, text: str) -> None:
        """Render a complete response as Rich Markdown."""
        with self._lock:
            if isinstance(self._console, NullConsole):
                print(text)
            else:
                self._console.print(Markdown(text))

    # ── Live streaming ───────────────────────────────────────────────────────

    @contextmanager
    def live_stream(self) -> Generator:
        """
        Context manager for live-updating streaming output (no flicker).
        Yields a Rich Live or NullLive object.

        Usage:
            with renderer.live_stream() as live:
                live.update(Markdown(chunk))
        """
        with self._live_context() as live:
            yield live

    # ── Spinner ──────────────────────────────────────────────────────────────

    @contextmanager
    def spinner(self, message: str = "Thinking...") -> Generator:
        """
        Context manager for a spinner during async operations.

        Usage:
            with renderer.spinner("Calling Hivemind...") as s:
                result = do_work()
        """
        accent = self._skin.get_color("banner_accent", "#DA70D6")
        status_msg = f"[{accent}]{message}[/]" if RICH_AVAILABLE else message
        with self._status_context(status_msg) as status:
            yield status

    # ── System health ─────────────────────────────────────────────────────────

    def print_health_table(self, health: dict) -> None:
        """Print system health as a Rich table."""
        with self._lock:
            if isinstance(self._console, NullConsole):
                for k, v in health.items():
                    print(f"  {k}: {v}")
                return

            ok_c  = self._skin.get_color("ui_ok",    "#90EE90")
            err_c = self._skin.get_color("ui_error",  "#FF6B6B")
            dim   = self._skin.get_color("banner_dim","#4B0082")

            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column("icon",    style="bold", width=3)
            table.add_column("service", style=f"dim {dim}", width=12)
            table.add_column("status")

            for service, status in health.items():
                s = str(status).lower()
                if any(x in s for x in ["online", "active", "running", "ok"]):
                    icon = f"[{ok_c}]✓[/]"
                else:
                    icon = f"[{err_c}]✗[/]"
                table.add_row(icon, service, str(status))

            self._console.print(table)

    # ── Rule / divider ────────────────────────────────────────────────────────

    def print_rule(self, title: str = "") -> None:
        """Print a horizontal divider rule."""
        with self._lock:
            if isinstance(self._console, NullConsole):
                cols = shutil.get_terminal_size().columns
                print("─" * cols)
            else:
                from rich.rule import Rule
                border = self._skin.get_color("input_rule", "#7B2D8B")
                self._console.print(Rule(title, style=border))

    # ── Graceful ANSI fallbacks ───────────────────────────────────────────────

    def _fallback_banner(self, model, health, version, yolo_mode):
        C_P = "\033[95m"; C_G = "\033[92m"; C_R = "\033[0m"; C_Y = "\033[93m"
        print(f"\n{C_P}🌸 KENBUN COGNITIVE AGENT SHELL v{version}{C_R}")
        print(f"   Model: {C_G}{model}{C_R}")
        if yolo_mode:
            print(f"   {C_Y}⚡ YOLO MODE ACTIVE{C_R}")
        if health:
            for k, v in health.items():
                print(f"   {C_G}✓{C_R} {k}: {v}")
        print()

    def _fallback_box(self, lines, title):
        cols = shutil.get_terminal_size().columns
        width = min(cols, 80)
        print(f"┌{'─' * (width - 2)}┐")
        if title:
            print(f"│ {title}")
            print(f"├{'─' * (width - 2)}┤")
        for line in lines:
            print(f"│ {line}")
        print(f"└{'─' * (width - 2)}┘")
