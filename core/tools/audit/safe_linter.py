import asyncio
import os
import threading
import concurrent.futures

MAX_CODE_SIZE = 1024 * 1024  # 1 MB
MAX_OUTPUT_SIZE = 1024 * 1024 # 1 MB
PROCESS_TIMEOUT = 5.0

# Global thread-safe semaphore to prevent CPU exhaustion (limit concurrent linting to CPU cores)
_SEMAPHORE = None
_SEMAPHORE_LOCK = threading.Lock()

def _get_semaphore():
    global _SEMAPHORE
    with _SEMAPHORE_LOCK:
        if _SEMAPHORE is None:
            try:
                cores = os.cpu_count() or 4
            except Exception:
                cores = 4
            _SEMAPHORE = threading.Semaphore(cores)
        return _SEMAPHORE

async def _async_safe_pre_flight_linter(code_snippet: str) -> dict:
    if not code_snippet:
        return {"status": "ERROR", "messages": ["No input provided"], "fixed_code": None}

    payload = code_snippet.encode('utf-8')
    if len(payload) > MAX_CODE_SIZE:
        return {"status": "ERROR", "messages": [f"Snippet exceeds maximum size limit of {MAX_CODE_SIZE} bytes."], "fixed_code": None}

    cmd = ["ruff", "check", "--isolated", "--select", "E,F", "-"]
    
    clean_env = {"PATH": os.environ.get("PATH", "")}
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=clean_env
        )
        
        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                process.communicate(input=payload),
                timeout=PROCESS_TIMEOUT
            )
            
            if len(stdout_data) > MAX_OUTPUT_SIZE or len(stderr_data) > MAX_OUTPUT_SIZE:
                try: process.kill()
                except Exception: pass
                return {"status": "ERROR", "messages": ["Linter output exceeded maximum size limit."], "fixed_code": None}
                
        except asyncio.TimeoutError:
            try: process.kill()
            except Exception: pass
            await process.wait()
            return {"status": "ERROR", "messages": ["Linter execution timed out (possible DoS attempt)."], "fixed_code": None}
            
        await process.wait()

        try:
            # Just decode to check for UnicodeDecodeError
            stdout_data.decode('utf-8', errors='strict')
            stderr_data.decode('utf-8', errors='strict')
        except UnicodeDecodeError:
            return {"status": "ERROR", "messages": ["Unicode Decoding Error: Possible Log Injection payload."], "fixed_code": None}
        
        if process.returncode == 0:
            return {"status": "CLEAN", "messages": [], "fixed_code": code_snippet}
        else:
            error_text = stdout_data.decode('utf-8', errors='ignore') + "\n" + stderr_data.decode('utf-8', errors='ignore')
            return {"status": "ISSUES_REMAIN", "messages": error_text.splitlines()[:50], "fixed_code": code_snippet}
            
    except Exception as e:
        return {"status": "ERROR", "messages": [f"Internal Linter Error: {str(e)}"], "fixed_code": None}

def _run_in_new_loop(code_snippet: str) -> dict:
    return asyncio.run(_async_safe_pre_flight_linter(code_snippet))

def safe_pre_flight_linter(code_snippet: str) -> dict:
    """
    Executes a secure, isolated static analysis pass on a code snippet.
    Returns a dict with 'status', 'fixed_code', and 'messages'.
    """
    semaphore = _get_semaphore()
    # Wait to acquire a concurrency slot before spawning the thread/loop
    semaphore.acquire()
    try:
        # Run in a separate thread to guarantee we don't clash with an existing asyncio event loop
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_in_new_loop, code_snippet)
            return future.result()
    except Exception as e:
        return {"status": "ERROR", "messages": [f"Execution Error: {str(e)}"], "fixed_code": None}
    finally:
        semaphore.release()
