import os
import sys
import platform
import urllib.request
import zipfile
import hashlib
import shutil
import subprocess
import json
import time
import yaml

BWS_VERSION = "2.0.0"
BWS_HASHES = {
    "aarch64-apple-darwin": "5bbb43fcec75528c5d78e4dfdb22b6b368ecdff7020bcd853911564587f61f8a",
    "aarch64-unknown-linux-gnu": "49a250d4f3121c67155c195afbad4ced90a92a878c3256ca091276b82e7ad131",
    "x86_64-apple-darwin": "2f33fa7da3d7c3ee1838f3c5f3e8a47051e3fdb01c45701f6844fa0b344e92d1",
    "x86_64-pc-windows-msvc": "4284944f3b0c7b97a4d4105c715cd814c744ceff0405481a213937955e31d866",
    "x86_64-unknown-linux-gnu": "a8340ce01da609200441f2eca0e591173e124f012c88a16afda574279c052013"
}

_CACHE = {
    "timestamp": 0,
    "secrets": {}
}

_APPLIED_NOTICE = False

def get_target_triple():
    os_name = sys.platform
    arch = platform.machine().lower()
    if os_name == "darwin":
        if arch in ("arm64", "aarch64"):
            return "aarch64-apple-darwin"
        return "x86_64-apple-darwin"
    elif os_name == "win32":
        return "x86_64-pc-windows-msvc"
    elif os_name.startswith("linux"):
        if arch in ("arm64", "aarch64"):
            return "aarch64-unknown-linux-gnu"
        return "x86_64-unknown-linux-gnu"
    return None

def get_bws_bin_name():
    return "bws.exe" if sys.platform == "win32" else "bws"

def get_kenbun_dir():
    return os.path.expanduser("~/.kenbun")

def get_bws_local_path():
    return os.path.join(get_kenbun_dir(), "bin", get_bws_bin_name())

def get_bws_path():
    # 1. Check PATH
    bin_name = get_bws_bin_name()
    path_bin = shutil.which(bin_name)
    if path_bin:
        return path_bin
    
    # 2. Check ~/.kenbun/bin/
    local_bin = get_bws_local_path()
    if os.path.exists(local_bin) and os.access(local_bin, os.X_OK):
        return local_bin
    
    return None

def download_bws():
    triple = get_target_triple()
    if not triple:
        raise ValueError(f"Unsupported platform: {sys.platform} ({platform.machine()})")
    
    expected_hash = BWS_HASHES.get(triple)
    if not expected_hash:
        raise ValueError(f"No SHA-256 hash defined for platform triple: {triple}")
    
    url = f"https://github.com/bitwarden/sdk-sm/releases/download/bws-v{BWS_VERSION}/bws-{triple}-{BWS_VERSION}.zip"
    
    kenbun_dir = get_kenbun_dir()
    bin_dir = os.path.join(kenbun_dir, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    
    zip_path = os.path.join(bin_dir, f"bws-{BWS_VERSION}.zip")
    
    sys.stderr.write(f"Downloading bws v{BWS_VERSION} for {triple}...\n")
    
    # Download zip file
    req = urllib.request.Request(url, headers={"User-Agent": "KenbunSecretsDownloader"})
    with urllib.request.urlopen(req) as response:
        content = response.read()
    
    # Verify SHA-256 hash
    actual_hash = hashlib.sha256(content).hexdigest()
    if actual_hash != expected_hash:
        raise ValueError(f"Checksum verification failed for bws zip!\nExpected: {expected_hash}\nActual:   {actual_hash}")
    
    # Save zip to disk
    with open(zip_path, "wb") as f:
        f.write(content)
    
    # Extract zip file
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(bin_dir)
    
    # Clean up zip
    try:
        os.remove(zip_path)
    except Exception:
        pass
    
    # Binary name checking (could be bws or bws.exe)
    extracted_bin = os.path.join(bin_dir, get_bws_bin_name())
    if not os.path.exists(extracted_bin):
        # In some cases the zip might contain just 'bws' but we are on Windows, etc.
        # Check if an extensionless 'bws' exists and rename
        alternative = os.path.join(bin_dir, "bws")
        if os.path.exists(alternative) and sys.platform == "win32":
            shutil.move(alternative, extracted_bin)
    
    # Set executable permissions
    if sys.platform != "win32" and os.path.exists(extracted_bin):
        os.chmod(extracted_bin, 0o755)
        
    sys.stderr.write(f"Successfully installed and verified bws binary at {extracted_bin}\n")
    return extracted_bin

def load_kenbun_config_raw() -> dict:
    config_path = os.path.join(get_kenbun_dir(), "config.yaml")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            sys.stderr.write(f"Warning: Failed to load config.yaml at {config_path}: {e}\n")
    return {}

def save_kenbun_config_raw(config: dict):
    os.makedirs(get_kenbun_dir(), exist_ok=True)
    config_path = os.path.join(get_kenbun_dir(), "config.yaml")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, default_flow_style=False)
    except Exception as e:
        sys.stderr.write(f"Error: Failed to save config.yaml at {config_path}: {e}\n")

def load_kenbun_env():
    env_path = os.path.join(get_kenbun_dir(), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'").strip('"')
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception as e:
            sys.stderr.write(f"Warning: Failed to parse .env at {env_path}: {e}\n")

def apply_secrets_to_env():
    global _CACHE, _APPLIED_NOTICE
    
    # 1. Load ~/.kenbun/.env first to bootstrap variables
    load_kenbun_env()
    
    # 2. Check config.yaml if secrets.bitwarden is enabled
    config = load_kenbun_config_raw()
    secrets_cfg = config.get("secrets", {})
    bw_cfg = secrets_cfg.get("bitwarden", {})
    
    enabled = bw_cfg.get("enabled", False)
    if not enabled:
        return
        
    access_token_env = bw_cfg.get("access_token_env", "BWS_ACCESS_TOKEN")
    project_id = bw_cfg.get("project_id", "")
    server_url = bw_cfg.get("server_url", "")
    cache_ttl = bw_cfg.get("cache_ttl_seconds", 300)
    override_existing = bw_cfg.get("override_existing", True)
    auto_install = bw_cfg.get("auto_install", True)
    
    token = os.environ.get(access_token_env)
    if not token:
        sys.stderr.write(f"Warning: Bitwarden Secrets Manager is enabled, but {access_token_env} is not set.\n")
        return
        
    if not project_id:
        sys.stderr.write("Warning: Bitwarden Secrets Manager is enabled, but secrets.bitwarden.project_id is empty.\n")
        return
        
    # Check binary presence
    bws_bin = get_bws_path()
    if not bws_bin:
        if auto_install:
            try:
                bws_bin = download_bws()
            except Exception as e:
                sys.stderr.write(f"Warning: Failed to auto-install bws binary: {e}\n")
                return
        else:
            sys.stderr.write("Warning: bws binary not found and secrets.bitwarden.auto_install is false.\n")
            return
            
    # Check cache
    now = time.time()
    if cache_ttl > 0 and _CACHE["timestamp"] > 0 and (now - _CACHE["timestamp"] < cache_ttl):
        secrets_dict = _CACHE["secrets"]
    else:
        # Run bws secret list
        env = os.environ.copy()
        env[access_token_env] = token
        if server_url:
            env["BWS_SERVER_URL"] = server_url
            
        cmd = [bws_bin, "secret", "list", project_id]
        try:
            res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                err_msg = res.stderr.strip() or f"exit code {res.returncode}"
                sys.stderr.write(f"Warning: bws secret list failed: {err_msg}\n")
                return
            
            secrets_list = json.loads(res.stdout)
            secrets_dict = {}
            for s in secrets_list:
                k = s.get("key") or s.get("name")
                v = s.get("value")
                if k and v is not None:
                    secrets_dict[k] = v
            
            # Update cache
            _CACHE["timestamp"] = now
            _CACHE["secrets"] = secrets_dict
            
        except subprocess.TimeoutExpired:
            sys.stderr.write("Warning: bws command timed out connecting to Bitwarden.\n")
            return
        except Exception as e:
            sys.stderr.write(f"Warning: Failed to fetch secrets from Bitwarden: {e}\n")
            return
            
    # Apply to environment
    applied_count = 0
    for k, v in secrets_dict.items():
        # Security Guardrail: Never let Bitwarden overwrite the bootstrap token itself
        if k == access_token_env:
            continue
            
        if override_existing:
            os.environ[k] = v
            applied_count += 1
        else:
            if k not in os.environ:
                os.environ[k] = v
                applied_count += 1
                
    if applied_count > 0 and not _APPLIED_NOTICE:
        sys.stderr.write(f"Kenbun: Applied {applied_count} secrets from Bitwarden Secrets Manager.\n")
        _APPLIED_NOTICE = True
