import contextlib
import io
import json
import logging
import os
import re
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
try:
    from tools.infrastructure.config import settings
except Exception:
    settings = None
from tools.utils.path_utils import get_project_root

PROJECT_ROOT = get_project_root()
LOG_FILE = PROJECT_ROOT / "mcp_debug.log"
logger = logging.getLogger("tools.helpers")

# --- 0.1 SILENCE HELPER ---
@contextlib.contextmanager
def silence_stdout():
    """Redirects stdout to stderr temporarily to protect the MCP protocol."""
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old_stdout


def debug_log(msg: str) -> None:
    """Writes debug logs to mcp_debug.log and stderr."""
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass
    sys.stderr.write(msg + "\n")


# --- 2. KNOWLEDGE REGISTRY ---
OFFICIAL_DOCS = {
    "react": "react.dev",
    "nextjs": "nextjs.org/docs",
    "vue": "vuejs.org",
    "svelte": "svelte.dev/docs",
    "tailwind": "tailwindcss.com/docs",
    "shadcn": "ui.shadcn.com/docs",
    "zod": "zod.dev",
    "python": "docs.python.org/3",
    "fastapi": "fastapi.tiangolo.com",
    "supabase": "supabase.com/docs",
    "docker": "docs.docker.com",
    "threejs": "threejs.org/docs",
    "r3f": "docs.pmnd.rs/react-three-fiber",
    "gsap": "gsap.com/docs",
}


# --- 3. HELPER: MEMORY ACCESS ---
def query_system_3(query_text: str, n: int = 3) -> List[str]:
    """Internal helper to fetch project concept memories."""
    try:
        from tools.memory.honcho_connect import query_embeddings
        results = query_embeddings(query_text, n_results=n, category="concepts")
        raw_docs = results['documents'][0] if results.get('documents') and results['documents'][0] else []
        return [doc[:4000] for doc in raw_docs]
    except Exception as e:
        debug_log(f"⚠️ System 3 Query Failed: {e}")
        return []


def _run_async_safely(coro):
    """Helper to safely run coroutines from any thread context."""
    import asyncio
    try:
        asyncio.get_running_loop()
        result_box = []
        err_box = []
        def _runner():
            try:
                result_box.append(asyncio.run(coro))
            except Exception as e:
                err_box.append(e)
        t = threading.Thread(target=_runner)
        t.start()
        t.join()
        if err_box:
            raise err_box[0]
        return result_box[0]
    except RuntimeError:
        return asyncio.run(coro)


def _clean_json_response(text: str) -> str:
    """Cleans raw response from models that output <think> blocks or markdown."""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = text.replace("```json", "").replace("```", "").strip()
    return text
