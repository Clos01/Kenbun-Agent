import os
import sys
import shutil
import subprocess
import socket
import re
from pathlib import Path

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def find_free_port(start_port: int) -> int:
    port = start_port
    while is_port_in_use(port):
        port += 1
    return port

def launch_docker_swarm():
    try:
        from scripts.bootstrap import should_enable_color, log_status, bootstrap_core
    except ImportError:
        should_enable_color = lambda: True
        log_status = lambda step, desc, detail, status="OK": print(f"[{status}] {desc} -> {detail}")
        bootstrap_core = lambda silent=False: None

    use_color = should_enable_color()
    c_m = "\033[38;5;218m"  # Pink
    c_c = "\033[38;5;224m"  # Soft Rose
    c_y = "\033[38;5;226m"  # Yellow
    c_r = "\033[0m"         # Reset
    
    if not use_color:
        c_m = c_c = c_y = c_r = ""

    print(f"\n{c_m}🐳 LAUNCHING LOCALIZED SWARM STACK{c_r}")
    print(f"{c_c}Executing Docker Compose local container startup...{c_r}\n")
    
    # Calculate project root from scripts/bootstrap.py relative path, since we know this is called from there typically.
    # We resolve from the current file `core/tools/infrastructure/docker_manager.py`
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent.parent
    
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


def clean_docker_stack():
    try:
        from scripts.bootstrap import should_enable_color
    except ImportError:
        should_enable_color = lambda: True

    use_color = should_enable_color()
    c_m = "\033[38;5;218m"  # Pink
    c_c = "\033[38;5;224m"  # Soft Rose
    c_y = "\033[38;5;226m"  # Yellow
    c_r = "\033[0m"         # Reset
    c_g = "\033[38;5;246m"  # Slate Gray
    
    if not use_color:
        c_m = c_c = c_y = c_r = c_g = ""
        
    print(f"\n{c_m}🧹 CLEAN / RESET SWARM DOCKER STACK{c_r}")
    print(f"{c_g}──────────────────────────────────────────────────{c_r}")
    
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent.parent
    
    docker_bin = shutil.which("docker")
    if not docker_bin:
        print(f"\n{c_y}⚠️ Docker is not installed on this system.{c_r}\n")
        return

    print("Choose cleanup intensity:")
    print(f"  {c_c}[1]{c_r} Light Clean (Removes local build images & deletes volumes/containers - FAST)")
    print(f"  {c_c}[2]{c_r} Deep Purge  (Deletes ALL stack containers, volumes, and large cached images - SLOW)")
    print(f"  {c_c}[3]{c_r} Cancel")
    
    try:
        choice = input(f"\n{c_m}Select Option [1-3]: {c_r}").strip()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{c_g}Cleanup cancelled.{c_r}\n")
        return
        
    if choice == "3" or choice not in ("1", "2"):
        print(f"\n{c_g}Cleanup cancelled.{c_r}\n")
        return
        
    print(f"\n{c_y}🟡 Stopping Docker Swarm Stack containers...{c_r}")
    
    # Run compose down
    down_args = ["docker", "compose", "down", "--volumes", "--remove-orphans"]
    if choice == "1":
        down_args.extend(["--rmi", "local"])
    else:
        down_args.extend(["--rmi", "all"])
        
    try:
        subprocess.run(down_args, cwd=project_root)
        # Explicitly kill containers by name to prevent cross-project conflicts (e.g. if ran from /opt vs ~/)
        containers = ["portable_chroma", "portable_ollama", "portable_ollama_init", "portable_fastmcp", "portable_dashboard", "portable_dozzle"]
        subprocess.run(["docker", "rm", "-f"] + containers, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if choice == "2":
            print(f"\n{c_y}🟡 Pruning build caches and unused network layers...{c_r}")
            subprocess.run(["docker", "builder", "prune", "-f"], cwd=project_root)
            subprocess.run(["docker", "image", "prune", "-f"], cwd=project_root)
            
        print(f"\n{c_c}✓ Docker Swarm Stack cleaned successfully!{c_r}")
        print(f"  You can now start a fresh build using the Swarm Stack option in the menu.")
        
        # Guide on file permissions (highly helpful for fresh reinstalls)
        print(f"\n{c_y}┌───────────────── 🌸 HOST FILE OWNERSHIP WARNING ────────────────┐")
        print(f"│ On Linux systems, Docker mount environments compile pycache/     │")
        print(f"│ assets using 'root' ownership on the host filesystem.           │")
        print(f"│                                                                 │")
        print(f"│ ➔ If you plan to completely remove this directory, standard     │")
        print(f"│   'rm -rf' will fail with Permission Denied.                    │")
        print(f"│                                                                 │")
        print(f"│ ➔ To cleanly delete this entire folder from your server:        │")
        print(f"│   {c_c}sudo rm -rf {project_root}{c_y}                           │")
        print(f"└─────────────────────────────────────────────────────────────────┘{c_r}\n")
    except Exception as e:
        print(f"\n{c_y}❌ Cleanup error: {e}{c_r}\n")
