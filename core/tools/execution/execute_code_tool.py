import os
import sys
import json
import socket
import tempfile
import threading
import subprocess
import time
import shutil
import inspect
import signal
from pathlib import Path
from typing import Dict, Any, List, Optional
from tools.registry import sovereign_tool, registry
from tools.infrastructure.config import settings

def run_handler_sync(handler, *args, **kwargs):
    """Safely executes sync or async tool handlers in a blocking fashion."""
    if inspect.iscoroutinefunction(handler):
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(handler(*args, **kwargs), loop)
                return future.result()
            else:
                return loop.run_until_complete(handler(*args, **kwargs))
        except RuntimeError:
            # Fallback when loop is closed or missing
            return asyncio.run(handler(*args, **kwargs))
    else:
        return handler(*args, **kwargs)

def handle_web_search(query: str, limit: int = 5) -> dict:
    """Wrapper to forward web_search to WebSearchEngine."""
    try:
        from tools.utils.web_engine import WebSearchEngine
        engine = WebSearchEngine()
        return engine.search(query, limit)
    except Exception as e:
        return {"error": f"Failed to run web_search: {e}"}

def handle_web_extract(urls: List[str]) -> dict:
    """Wrapper to download web page contents using WebExtractEngine."""
    try:
        from tools.utils.web_engine import WebExtractEngine
        engine = WebExtractEngine()
        return engine.extract(urls)
    except Exception as e:
        return {"error": f"Failed to run web_extract: {e}"}

@sovereign_tool(name="execute_code", category="Execution")
def execute_code(code: str, mode: str = "project") -> str:
    """
    Executes a Python script programmatically in a child process.
    The script can import 'kenbun_tools' to invoke other harvested tools.
    
    Args:
        code: The Python source code to execute.
        mode: The execution mode ('project' or 'strict').
        
    Returns:
        A JSON string containing the execution status, stdout, stderr, and metadata.
    """
    # 1. Setup temporary staging directory
    temp_dir = tempfile.mkdtemp(prefix="kenbun_exec_")
    socket_path = os.path.join(temp_dir, "rpc.sock")
    script_path = os.path.join(temp_dir, "script.py")
    
    # 2. Write user code
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(code)
        
    # 3. Generate kenbun_tools.py RPC stub
    stubs = """import os
import sys
import json
import socket
from pathlib import Path
import glob
import subprocess
import re

def read_file(path, encoding="utf-8"):
    try:
        with open(path, "r", encoding=encoding) as f:
            return {"content": f.read()}
    except Exception as e:
        return {"error": str(e)}

def write_file(path, content, encoding="utf-8"):
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding=encoding) as f:
            f.write(content)
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}

def search_files(query, path=".", file_glob="*"):
    matches = []
    try:
        for p in Path(path).rglob(file_glob):
            if p.is_file():
                try:
                    content = p.read_text(errors="ignore")
                    if query in content:
                        matches.append({"path": str(p)})
                except:
                    pass
    except Exception as e:
        return {"error": str(e)}
    return {"matches": matches}

def patch(path, old_string, new_string, replace_all=False):
    try:
        with open(path, "r") as f:
            content = f.read()
        if old_string not in content:
            return {"error": "old_string not found"}
        if replace_all:
            content = content.replace(old_string, new_string)
        else:
            content = content.replace(old_string, new_string, 1)
        with open(path, "w") as f:
            f.write(content)
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}

def terminal(command, timeout=300):
    try:
        res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        return {"output": res.stdout + res.stderr, "exit_code": res.returncode}
    except Exception as e:
        return {"output": "", "exit_code": -1, "error": str(e)}

def _rpc_call(name, *args, **kwargs):
    socket_path = os.environ.get("KENBUN_RPC_SOCKET")
    if not socket_path:
        raise RuntimeError("KENBUN_RPC_SOCKET not configured in environment.")
    
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(socket_path)
        payload = json.dumps({"name": name, "args": args, "kwargs": kwargs}) + "\\n"
        s.sendall(payload.encode())
        
        # Read response
        buffer = bytearray()
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            buffer.extend(chunk)
            if b"\\n" in chunk:
                break
        res = json.loads(buffer.decode())
        if "error" in res:
            raise RuntimeError(res["error"])
        return res.get("result")
"""

    # Add dynamic registry imports
    for tool_name in registry.get_all_tools().keys():
        if tool_name not in ("read_file", "write_file", "search_files", "patch", "terminal", "execute_code"):
            stubs += f"""
def {tool_name}(*args, **kwargs):
    return _rpc_call("{tool_name}", *args, **kwargs)
"""
            
    stubs += """
def web_search(*args, **kwargs):
    return _rpc_call("web_search", *args, **kwargs)

def web_extract(*args, **kwargs):
    return _rpc_call("web_extract", *args, **kwargs)

def browser_navigate(*args, **kwargs):
    return _rpc_call("browser_navigate", *args, **kwargs)

def browser_snapshot(*args, **kwargs):
    return _rpc_call("browser_snapshot", *args, **kwargs)

def browser_click(*args, **kwargs):
    return _rpc_call("browser_click", *args, **kwargs)

def browser_type(*args, **kwargs):
    return _rpc_call("browser_type", *args, **kwargs)

def browser_scroll(*args, **kwargs):
    return _rpc_call("browser_scroll", *args, **kwargs)

def browser_press(*args, **kwargs):
    return _rpc_call("browser_press", *args, **kwargs)

def browser_back(*args, **kwargs):
    return _rpc_call("browser_back", *args, **kwargs)

def browser_get_images(*args, **kwargs):
    return _rpc_call("browser_get_images", *args, **kwargs)

def browser_vision(*args, **kwargs):
    return _rpc_call("browser_vision", *args, **kwargs)

def browser_console(*args, **kwargs):
    return _rpc_call("browser_console", *args, **kwargs)

def browser_cdp(*args, **kwargs):
    return _rpc_call("browser_cdp", *args, **kwargs)

def browser_dialog(*args, **kwargs):
    return _rpc_call("browser_dialog", *args, **kwargs)

def computer_use(*args, **kwargs):
    return _rpc_call("computer_use", *args, **kwargs)

def vision_analyze(*args, **kwargs):
    return _rpc_call("vision_analyze", *args, **kwargs)

def text_to_speech(*args, **kwargs):
    return _rpc_call("text_to_speech", *args, **kwargs)

def transcribe_audio(*args, **kwargs):
    return _rpc_call("transcribe_audio", *args, **kwargs)
"""



    with open(os.path.join(temp_dir, "kenbun_tools.py"), "w", encoding="utf-8") as f:
        f.write(stubs)

    # 4. Start RPC Server Thread
    tool_calls_made = 0
    max_tool_calls = settings.CODE_EXECUTION_MAX_TOOL_CALLS
    stop_event = threading.Event()
    
    def handle_connection(conn):
        nonlocal tool_calls_made
        buffer = bytearray()
        try:
            with conn:
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    buffer.extend(chunk)
                    if b"\n" in chunk:
                        break
                if not buffer:
                    return
                
                req = json.loads(buffer.decode())
                name = req.get("name")
                args = req.get("args", [])
                kwargs = req.get("kwargs", {})
                
                # Enforce limits & whitelists
                if name in ("execute_code", "delegate_task") or name.startswith("mcp_"):
                    res = {"error": f"Tool call to '{name}' is forbidden inside execute_code."}
                elif tool_calls_made >= max_tool_calls:
                    res = {"error": f"Tool call limit exceeded ({max_tool_calls})."}
                else:
                    tool_calls_made += 1
                    
                    if name == "web_search":
                        res = handle_web_search(*args, **kwargs)
                    elif name == "web_extract":
                        res = handle_web_extract(*args, **kwargs)
                    else:
                        tool_entry = registry.get_tool(name)
                        if not tool_entry:
                            res = {"error": f"Tool '{name}' is not registered in Kenbun."}
                        else:
                            try:
                                val = run_handler_sync(tool_entry.handler, *args, **kwargs)
                                res = {"result": val}
                            except Exception as exc:
                                res = {"error": str(exc)}
                                
                conn.sendall((json.dumps(res) + "\n").encode())
        except Exception as e:
            try:
                conn.sendall((json.dumps({"error": str(e)}) + "\n").encode())
            except:
                pass

    def rpc_server_loop():
        server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_socket.bind(socket_path)
        server_socket.listen(5)
        server_socket.settimeout(0.5)
        
        while not stop_event.is_set():
            try:
                conn, _ = server_socket.accept()
            except socket.timeout:
                continue
            except Exception:
                break
            threading.Thread(target=handle_connection, args=(conn,), daemon=True).start()
            
        server_socket.close()

    server_thread = threading.Thread(target=rpc_server_loop, daemon=True)
    server_thread.start()

    # 5. Clean Environment Variables
    child_env = {}
    for k, v in os.environ.items():
        k_upper = k.upper()
        if any(sec in k_upper for sec in ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "PASSWD", "AUTH")):
            continue
        child_env[k] = v
        
    child_env["KENBUN_RPC_SOCKET"] = socket_path
    
    # Deriving PYTHONPATH
    project_root = str(Path(settings.PROJECT_ROOT).resolve())
    child_env["PYTHONPATH"] = os.pathsep.join([temp_dir, project_root, child_env.get("PYTHONPATH", "")])

    # 6. Resolve python interpreter binary
    python_bin = sys.executable
    if mode == "project":
        venv_path = os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX")
        if venv_path:
            possible_bin = os.path.join(venv_path, "bin", "python")
            if os.path.exists(possible_bin):
                python_bin = possible_bin
            else:
                possible_bin3 = os.path.join(venv_path, "bin", "python3")
                if os.path.exists(possible_bin3):
                    python_bin = possible_bin3

    run_cwd = project_root if mode == "project" else temp_dir
    timeout = settings.CODE_EXECUTION_TIMEOUT
    
    # 7. Spawn child process
    t0 = time.time()
    proc = None
    status = "success"
    stdout_data = ""
    stderr_data = ""
    
    try:
        proc = subprocess.Popen(
            [python_bin, script_path],
            cwd=run_cwd,
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid
        )
        stdout_data, stderr_data = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        status = "timeout"
        if proc:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                time.sleep(0.5)
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass
            try:
                stdout_data, stderr_data = proc.communicate()
            except Exception:
                pass
    except Exception as e:
        status = "error"
        stderr_data = str(e)
        
    duration = time.time() - t0
    
    # 8. Clean up RPC server
    stop_event.set()
    server_thread.join(timeout=1.0)
    
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass
        
    # 9. Format response
    exit_code = proc.returncode if proc and status != "timeout" else (-1 if status == "timeout" else -2)
    if exit_code != 0 and status == "success":
        status = "error"
        
    # Cap outputs
    stdout_capped = stdout_data[:51200]
    if len(stdout_data) > 51200:
        stdout_capped += "\n[output truncated at 50KB]"
        
    stderr_capped = stderr_data[:10240]
    if len(stderr_data) > 10240:
        stderr_capped += "\n[output truncated at 10KB]"
        
    response = {
        "status": status,
        "exit_code": exit_code,
        "stdout": stdout_capped,
        "stderr": stderr_capped,
        "tool_calls_made": tool_calls_made,
        "duration_seconds": round(duration, 3)
    }
    
    return json.dumps(response, indent=2)
