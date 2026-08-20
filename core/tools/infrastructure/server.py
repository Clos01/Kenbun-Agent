import builtins
import io
import json
import logging
import os
import signal
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP
from tools.harvester import harvest_and_register_tools
from tools.infrastructure.config import settings
from tools.registry import registry
from tools.utils.helpers import debug_log
from tools.utils.path_utils import get_project_root

sys.stderr.write("DEBUG: server.py IS BEING LOADED\n")

logger = logging.getLogger("fastmcp_server")

PROJECT_ROOT = get_project_root()
LOG_FILE = PROJECT_ROOT / "mcp_debug.log"

# Backward compatibility re-exports for internal consumers (e.g. routers.supervisor, dev tools, tests)
from tools.audit.supervisor_tools import *
from tools.design.design_tools import *
from tools.execution.checkpoint_tools import *
from tools.infrastructure.workspace_tools import *
from tools.memory.hivemind_tools import *
from tools.strategy.orchestration_tools import *
from tools.utils.helpers import *


class ProtocolShield(io.TextIOBase):
    def write(self, s):
        sys.stderr.write(s)
        return len(s)

    def flush(self):
        sys.stderr.flush()


_original_print = builtins.print


def mcp_safe_print(*args, sep=' ', end='\n', file=None, flush=False):
    if file is None or file is sys.stdout:
        msg = sep.join(str(a) for a in args) + end
        sys.stderr.write(msg)
        if flush:
            sys.stderr.flush()
    else:
        _original_print(*args, sep=sep, end=end, file=file, flush=flush)


def install_mcp_safe_print():
    builtins.print = mcp_safe_print


# Initialize FastMCP Server
mcp = FastMCP("Kenbun-tools")

import re

MAX_TOOLS = 256
IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
CONTROL_CHARS_REGEX = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def _sanitize_string(val: str, max_len: int = 1024) -> str:
    """Strip control characters, ANSI codes, and limit string length."""
    if not val:
        return ""
    cleaned = CONTROL_CHARS_REGEX.sub("", str(val))
    return cleaned.strip()[:max_len]


# System 4 Dynamic Harvester: Discover and register all sovereign tools from domain subpackages
discovered_modules = harvest_and_register_tools()
logger.info(f"🛡️ Dynamic Harvester completed sweep across {len(discovered_modules)} domain module(s).")

registered_names = set()
for name, tool_entry in registry.get_all_tools().items():
    if len(registered_names) >= MAX_TOOLS:
        logger.warning(f"⚠️ Maximum tool registration capacity ({MAX_TOOLS}) reached. Halting registration.")
        break

    try:
        raw_name = getattr(tool_entry, "name", name)
        clean_name = _sanitize_string(str(raw_name), 64)

        if not IDENTIFIER_REGEX.match(clean_name):
            logger.error(f"❌ Invalid tool identifier '{clean_name}' — rejected due to non-conforming characters.")
            continue

        if clean_name in registered_names:
            logger.warning(f"⚠️ Tool name collision detected for '{clean_name}'. Skipping duplicate.")
            continue

        raw_desc = getattr(tool_entry, "description", "") or ""
        sanitized_desc = _sanitize_string(str(raw_desc), 1024)

        handler = getattr(tool_entry, "handler", None)
        if not callable(handler):
            logger.error(f"❌ Invalid handler for tool '{clean_name}' — handler is not callable.")
            continue

        mcp.tool(name=clean_name, description=sanitized_desc)(handler)
        registered_names.add(clean_name)
        logger.debug(f"✅ FastMCP registered tool: {clean_name}")
    except Exception as e:
        safe_err = _sanitize_string(str(e), 256)
        logger.error(f"❌ Error registering tool into FastMCP: {safe_err}")

logger.info(f"🚀 FastMCP Server initialized with {len(registered_names)} active sovereign tools.")

if __name__ == "__main__":
    install_mcp_safe_print()

    def handle_sigterm(*args):
        os._exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)

    try:
        import gc
        gc.collect(2)

        try:
            from core.brain_health.docker_sre import SREAgent

            def _run_sre_agent():
                try:
                    agent = SREAgent(check_interval_sec=60, unhealthy_threshold=3)
                    agent.start_monitoring()
                except Exception as e:
                    debug_log(f"SRE Agent crashed: {e}")

            threading.Thread(target=_run_sre_agent, daemon=True).start()
        except Exception as e:
            debug_log(f"SRE Agent unavailable (skipping): {e}")

        mcp.run()
    except Exception as e:
        import traceback
        debug_log(f"CRITICAL CRASH: {e}")
        debug_log(traceback.format_exc())
