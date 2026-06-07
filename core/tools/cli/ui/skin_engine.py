"""
🌸 Kenbun Skin Engine
A data-driven theme system inspired by Hermes Agent's skin_engine.py.
Skins are defined as dataclasses (built-in) or YAML files (~/.kenbun/skins/).

Built-in skins:
  - kenbun   : Cherry blossom pink/deep purple (default)
  - cyber    : Neon green on black (hacker aesthetic)
  - slate    : Cool blue developer theme
  - mono     : Clean grayscale

Usage:
    from core.tools.cli.ui.skin_engine import get_active_skin, set_active_skin
    skin = get_active_skin()
    print(skin.get_color("banner_border"))   # "#7B2D8B"
    print(skin.get_branding("agent_name"))   # "Kenbun Agent"
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Skin data structure (mirrors Hermes's SkinConfig)
# =============================================================================

@dataclass
class SkinConfig:
    """Complete skin configuration for Kenbun terminal UI."""
    name: str
    description: str = ""
    colors: Dict[str, str] = field(default_factory=dict)
    spinner: Dict[str, Any] = field(default_factory=dict)
    branding: Dict[str, str] = field(default_factory=dict)
    tool_prefix: str = "┊"
    banner_logo: str = ""    # Rich-markup ASCII art logo
    banner_hero: str = ""    # Rich-markup hero art (left panel)

    def get_color(self, key: str, fallback: str = "") -> str:
        return self.colors.get(key, fallback)

    def get_branding(self, key: str, fallback: str = "") -> str:
        return self.branding.get(key, fallback)

    def get_spinner_faces(self, key: str = "waiting_faces") -> List[str]:
        return self.spinner.get(key, ["(🌸)", "(✿)", "(❀)", "(🌺)"])

    def get_spinner_verbs(self) -> List[str]:
        return self.spinner.get("thinking_verbs", [
            "thinking", "reasoning", "processing", "synthesizing"
        ])


# =============================================================================
# Built-in skin definitions
# =============================================================================

_BUILTIN_SKINS: Dict[str, Dict[str, Any]] = {
    "kenbun": {
        "name": "kenbun",
        "description": "Cherry blossom — deep purple and sakura pink (default)",
        "colors": {
            "banner_border":    "#7B2D8B",   # Deep purple
            "banner_title":     "#FF69B4",   # Hot pink
            "banner_accent":    "#DA70D6",   # Orchid
            "banner_dim":       "#4B0082",   # Indigo
            "banner_text":      "#FFF0F5",   # Lavender blush
            "ui_accent":        "#DA70D6",
            "ui_label":         "#FF69B4",
            "ui_ok":            "#90EE90",   # Light green
            "ui_error":         "#FF6B6B",   # Coral red
            "ui_warn":          "#FFD700",   # Gold
            "prompt":           "#FFF0F5",
            "input_rule":       "#7B2D8B",
            "response_border":  "#FF69B4",
            "status_bar_bg":    "#1A0A2E",   # Very dark purple
            "status_bar_text":  "#FFF0F5",
            "status_bar_strong":"#FF69B4",
            "status_bar_dim":   "#4B0082",
            "status_bar_good":  "#90EE90",
            "status_bar_warn":  "#FFD700",
            "status_bar_bad":   "#FFA07A",
            "status_bar_critical":"#FF6B6B",
            "session_label":    "#DA70D6",
            "session_border":   "#7B2D8B",
        },
        "spinner": {
            "waiting_faces": ["(🌸)", "(✿)", "(❀)", "(🌺)", "(🌷)"],
            "thinking_faces": ["(🌸)", "(🧠)", "(💭)", "(✦)", "(🔮)"],
            "thinking_verbs": [
                "thinking", "reasoning", "synthesizing", "analyzing",
                "reflecting", "computing", "deliberating", "processing",
            ],
        },
        "branding": {
            "agent_name":     "Kenbun Agent",
            "welcome":        "I'm online and ready. What are we working on today?",
            "goodbye":        "Sayonara! 🌸",
            "response_label": " 🌸 Kenbun ",
            "prompt_symbol":  "🌸",
            "help_header":    "🌸 Available Commands",
        },
        "tool_prefix": "┊",
    },

    "cyber": {
        "name": "cyber",
        "description": "Neon cyber — green on black matrix aesthetic",
        "colors": {
            "banner_border":    "#00FF41",   # Matrix green
            "banner_title":     "#00FF41",
            "banner_accent":    "#39FF14",   # Neon green
            "banner_dim":       "#003B00",   # Dark green
            "banner_text":      "#CCFFCC",   # Light green
            "ui_accent":        "#39FF14",
            "ui_label":         "#00FF41",
            "ui_ok":            "#00FF41",
            "ui_error":         "#FF0033",
            "ui_warn":          "#FFFF00",
            "prompt":           "#CCFFCC",
            "input_rule":       "#00FF41",
            "response_border":  "#39FF14",
            "status_bar_bg":    "#000800",   # Near black
            "status_bar_text":  "#CCFFCC",
            "status_bar_strong":"#39FF14",
            "status_bar_dim":   "#005000",
            "status_bar_good":  "#00FF41",
            "status_bar_warn":  "#FFFF00",
            "status_bar_bad":   "#FF8C00",
            "status_bar_critical":"#FF0033",
            "session_label":    "#39FF14",
            "session_border":   "#003B00",
        },
        "spinner": {
            "waiting_faces": ["(▓)", "(▒)", "(░)", "(█)", "(▄)"],
            "thinking_faces": ["(⌁)", "(<>)", "(/)", "(\\)", "(|)"],
            "thinking_verbs": [
                "hacking", "injecting", "compiling", "executing",
                "scanning", "routing", "decrypting", "probing",
            ],
        },
        "branding": {
            "agent_name":     "Kenbun Cyber",
            "welcome":        "SYSTEM ONLINE. AWAITING INPUT...",
            "goodbye":        "DISCONNECTING... ▓▒░",
            "response_label": " ⌁ KENBUN ",
            "prompt_symbol":  ">_",
            "help_header":    "[SYS] Available Commands",
        },
        "tool_prefix": "│",
    },

    "slate": {
        "name": "slate",
        "description": "Cool blue — developer focused",
        "colors": {
            "banner_border":    "#4169E1",
            "banner_title":     "#7EB8F6",
            "banner_accent":    "#8EA8FF",
            "banner_dim":       "#4B5563",
            "banner_text":      "#C9D1D9",
            "ui_accent":        "#7EB8F6",
            "ui_label":         "#8EA8FF",
            "ui_ok":            "#63D0A6",
            "ui_error":         "#F7A072",
            "ui_warn":          "#E6A855",
            "prompt":           "#C9D1D9",
            "input_rule":       "#4169E1",
            "response_border":  "#7EB8F6",
            "status_bar_bg":    "#151C2F",
            "status_bar_text":  "#C9D1D9",
            "status_bar_strong":"#7EB8F6",
            "status_bar_dim":   "#4B5563",
            "status_bar_good":  "#63D0A6",
            "status_bar_warn":  "#E6A855",
            "status_bar_bad":   "#F7A072",
            "status_bar_critical":"#FF7A7A",
            "session_label":    "#7EB8F6",
            "session_border":   "#4B5563",
        },
        "spinner": {
            "waiting_faces": ["(◌)", "(◍)", "(◎)", "(●)", "(◉)"],
            "thinking_faces": ["(⌁)", "(◈)", "(◇)", "(◆)", "(◉)"],
            "thinking_verbs": [
                "computing", "analyzing", "processing", "evaluating",
                "calculating", "reasoning", "planning", "optimizing",
            ],
        },
        "branding": {
            "agent_name":     "Kenbun Agent",
            "welcome":        "Online and ready. What are we building?",
            "goodbye":        "Goodbye! ◉",
            "response_label": " ◉ Kenbun ",
            "prompt_symbol":  "❯",
            "help_header":    "[?] Available Commands",
        },
        "tool_prefix": "┊",
    },

    "mono": {
        "name": "mono",
        "description": "Monochrome — clean grayscale",
        "colors": {
            "banner_border":    "#555555",
            "banner_title":     "#E6EDF3",
            "banner_accent":    "#AAAAAA",
            "banner_dim":       "#444444",
            "banner_text":      "#C9D1D9",
            "ui_accent":        "#AAAAAA",
            "ui_label":         "#888888",
            "ui_ok":            "#888888",
            "ui_error":         "#CCCCCC",
            "ui_warn":          "#999999",
            "prompt":           "#C9D1D9",
            "input_rule":       "#444444",
            "response_border":  "#AAAAAA",
            "status_bar_bg":    "#1F1F1F",
            "status_bar_text":  "#C9D1D9",
            "status_bar_strong":"#E6EDF3",
            "status_bar_dim":   "#777777",
            "status_bar_good":  "#B5B5B5",
            "status_bar_warn":  "#AAAAAA",
            "status_bar_bad":   "#D0D0D0",
            "status_bar_critical":"#F0F0F0",
            "session_label":    "#888888",
            "session_border":   "#555555",
        },
        "spinner": {
            "waiting_faces": ["(◌)", "(◍)", "(◎)", "(●)", "(◉)"],
            "thinking_faces": ["[  ]", "[= ]", "[==]", "[=]", "[  ]"],
            "thinking_verbs": [
                "processing", "working", "computing", "running",
            ],
        },
        "branding": {
            "agent_name":     "Kenbun Agent",
            "welcome":        "Ready. Type your request or /help.",
            "goodbye":        "Goodbye.",
            "response_label": " > Kenbun ",
            "prompt_symbol":  ">",
            "help_header":    "Available Commands",
        },
        "tool_prefix": "│",
    },
}


# =============================================================================
# Skin loading and management
# =============================================================================

_active_skin: Optional[SkinConfig] = None
_active_skin_name: str = "kenbun"


def _skins_dir() -> Path:
    """User skins directory — ~/.kenbun/skins/"""
    return Path.home() / ".kenbun" / "skins"


def _load_skin_from_yaml(path: Path) -> Optional[Dict[str, Any]]:
    """Load a skin definition from a YAML file."""
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict) and "name" in data:
            return data
    except Exception as e:
        logger.debug("Failed to load skin from %s: %s", path, e)
    return None


def _build_skin_config(data: Dict[str, Any]) -> SkinConfig:
    """Build a SkinConfig from a raw dict, inheriting defaults from 'kenbun' skin."""
    default = _BUILTIN_SKINS["kenbun"]
    skin_name = str(data.get("name", "unknown"))

    colors = dict(default.get("colors", {}))
    colors.update(data.get("colors") or {})

    spinner = dict(default.get("spinner", {}))
    spinner.update(data.get("spinner") or {})

    branding = dict(default.get("branding", {}))
    branding.update(data.get("branding") or {})

    return SkinConfig(
        name=skin_name,
        description=data.get("description", ""),
        colors=colors,
        spinner=spinner,
        branding=branding,
        tool_prefix=data.get("tool_prefix", default.get("tool_prefix", "┊")),
        banner_logo=data.get("banner_logo", ""),
        banner_hero=data.get("banner_hero", ""),
    )


def list_skins() -> List[Dict[str, str]]:
    """List all available skins (built-in + user-installed)."""
    result = []
    for name, data in _BUILTIN_SKINS.items():
        result.append({
            "name": name,
            "description": data.get("description", ""),
            "source": "builtin",
            "active": name == _active_skin_name,
        })
    skins_path = _skins_dir()
    if skins_path.is_dir():
        for f in sorted(skins_path.glob("*.yaml")):
            data = _load_skin_from_yaml(f)
            if data:
                s_name = data.get("name", f.stem)
                if any(s["name"] == s_name for s in result):
                    continue
                result.append({
                    "name": s_name,
                    "description": data.get("description", ""),
                    "source": "user",
                    "active": s_name == _active_skin_name,
                })
    return result


def load_skin(name: str) -> SkinConfig:
    """Load a skin by name. Checks user skins first, then built-in."""
    skins_path = _skins_dir()
    user_file = skins_path / f"{name}.yaml"
    if user_file.is_file():
        data = _load_skin_from_yaml(user_file)
        if data:
            return _build_skin_config(data)
    if name in _BUILTIN_SKINS:
        return _build_skin_config(_BUILTIN_SKINS[name])
    logger.warning("Skin '%s' not found, using kenbun default", name)
    return _build_skin_config(_BUILTIN_SKINS["kenbun"])


def get_active_skin() -> SkinConfig:
    """Get the currently active skin (cached)."""
    global _active_skin
    if _active_skin is None:
        _active_skin = load_skin(_active_skin_name)
    return _active_skin


def set_active_skin(name: str) -> SkinConfig:
    """Switch the active skin. Returns the new SkinConfig."""
    global _active_skin, _active_skin_name
    _active_skin_name = name
    _active_skin = load_skin(name)
    return _active_skin


def get_active_skin_name() -> str:
    return _active_skin_name
