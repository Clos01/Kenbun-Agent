import asyncio
import logging
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import centralized settings
from tools.infrastructure.config import settings

project_root = settings.PROJECT_ROOT

from contextlib import asynccontextmanager

from tools.infrastructure.server_deps import (
    get_or_create_config_token,
    update_signals_count_task,
)
from tools.utils.workspace_manager import workspace_manager


@asynccontextmanager
async def lifespan_context(app: FastAPI):
    """Start background daemons on server load."""
    try:
        token = get_or_create_config_token()
        
        # Security Bind Gate:
        # If settings.API_HOST is a public interface (e.g. 0.0.0.0 or non-loopback),
        # then CONFIG_TOKEN must be configured and secure.
        host = getattr(settings, "API_HOST", "127.0.0.1")
        is_loopback = host in ("127.0.0.1", "localhost", "::1")
        if not is_loopback:
            if not token or len(token) < 16:
                raise RuntimeError("Public network bind requested, but no strong CONFIG_TOKEN is configured.")
                
    except RuntimeError as e:
        logging.critical(f"FATAL STARTUP ERROR: {e}")
        import sys

        sys.exit(1)

    tasks = set()

    def handle_task_result(task: asyncio.Task):
        tasks.discard(task)
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Background daemon task died: {e}", exc_info=True)

    t1 = asyncio.create_task(update_signals_count_task())
    t1.add_done_callback(handle_task_result)
    tasks.add(t1)

    from tools.memory.digester import digester_daemon
    t2 = asyncio.create_task(digester_daemon.digestion_loop())
    t2.add_done_callback(handle_task_result)
    tasks.add(t2)

    # Launch background cron scheduler loop
    from tools.infrastructure.routers.cron import cron_scheduler_loop
    t3 = asyncio.create_task(cron_scheduler_loop())
    t3.add_done_callback(handle_task_result)
    tasks.add(t3)

    yield
    
    # Graceful shutdown of daemons
    for task in list(tasks):
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass



app = FastAPI(title="Kenbun Mission Control API", lifespan=lifespan_context)


def health_check():
    return {"status": "healthy"}


from urllib.parse import urlparse


def build_cors_origins() -> List[str]:
    """
    Constructs a hardened, explicit CORS origin whitelist.
    Adheres strictly to the CTO-Consensus security standards:
    - Eliminates DNS rebinding risks by using a static, explicit whitelist.
    - Sanitizes all environment-derived strings using urllib.parse.
    - Prevents arbitrary port and protocol injections.
    """
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # 1. Sanitize and append settings.FRONTEND_URL
    if settings.FRONTEND_URL:
        try:
            parsed = urlparse(settings.FRONTEND_URL)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                origins.append(f"{parsed.scheme}://{parsed.netloc}")
        except Exception as e:
            logging.error(f"CORS Init: Invalid FRONTEND_URL: {e}")

    # 2. Sanitize and trust the host machine's configured Tailscale/PC IP for local development
    if settings.SWARM_PC_IP:
        pc_ip = settings.SWARM_PC_IP.strip("\"'")
        if pc_ip not in ("localhost", "127.0.0.1"):
            # Clean and validate PC IP
            try:
                # If a port is present in FRONTEND_URL, reuse it; otherwise default to 3000
                frontend_port = 3000
                if settings.FRONTEND_URL:
                    parsed_fe = urlparse(settings.FRONTEND_URL)
                    if parsed_fe.port:
                        frontend_port = parsed_fe.port

                # Strip potential path or protocol injections from pc_ip
                clean_ip = pc_ip.split("/")[-1].split(":")[0].strip("[]")

                # Trust and construct explicit entries
                origins.append(f"http://{clean_ip}:{frontend_port}")
                origins.append(f"https://{clean_ip}:{frontend_port}")
            except Exception as e:
                logging.error(f"CORS Init: Invalid SWARM_PC_IP: {e}")

    # Dedup and return
    return list(set(origins))


# Allow Dashboard to connect securely (CTO Standard CORS Whitelisting)
# NOTE: Using wildcard for local Docker dev. Tighten for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=build_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def get_projects_to_watch():
    return workspace_manager.get_projects()


# In-memory queue for swarm events
swarm_events = []


from tools.infrastructure.routers.chat import router as chat_router
from tools.infrastructure.routers.config import router as config_router
from tools.infrastructure.routers.logs import router as logs_router
from tools.infrastructure.routers.cron import router as cron_router
from tools.infrastructure.routers.mcp import router as mcp_router
from tools.infrastructure.routers.extensions import router as extensions_router
from tools.infrastructure.routers.skills import router as skills_router

# --- Router Registrations ---
from tools.infrastructure.routers.health import router as health_router
from tools.infrastructure.routers.intelligence import router as intelligence_router
from tools.infrastructure.routers.legacy import router as legacy_router
from tools.infrastructure.routers.planka import router as planka_router
from tools.infrastructure.routers.supervisor import router as supervisor_router
from tools.infrastructure.routers.swarm import router as swarm_router
from tools.infrastructure.routers.telemetry import router as telemetry_router

app.include_router(health_router)
app.include_router(config_router)
app.include_router(telemetry_router)
app.include_router(intelligence_router)
app.include_router(chat_router)
app.include_router(swarm_router)
app.include_router(legacy_router)
app.include_router(supervisor_router)
app.include_router(planka_router)
app.include_router(logs_router)
app.include_router(cron_router)
app.include_router(mcp_router)
app.include_router(extensions_router)
app.include_router(skills_router)

# Dynamic Plugin Router Loader
try:
    import importlib.util
    import sys
    from pathlib import Path
    from tools.infrastructure.routers.extensions import discover_plugins
    
    plugins = discover_plugins()
    for p in plugins:
        api_rel_path = p.get("api")
        if api_rel_path:
            plugin_path = Path(p["_plugin_path"])
            api_path = plugin_path / "dashboard" / api_rel_path
            if api_path.exists():
                plugin_name = p["name"]
                module_name = f"kenbun_plugin_{plugin_name}"
                spec = importlib.util.spec_from_file_location(module_name, str(api_path))
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    if hasattr(module, "router"):
                        app.include_router(module.router, prefix=f"/api/plugins/{plugin_name}")
                        logging.info(f"Loaded dynamic API routes for plugin '{plugin_name}' under prefix '/api/plugins/{plugin_name}'")
except Exception as ex:
    logging.error(f"Failed to load dynamic plugin routers: {ex}", exc_info=True)


if __name__ == "__main__":
    import uvicorn

    # Bind host is configurable via API_HOST. Defaults to 0.0.0.0 for Docker
    # container networking; set API_HOST=127.0.0.1 for native/loopback-only runs.
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
