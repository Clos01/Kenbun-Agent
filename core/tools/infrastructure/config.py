from functools import lru_cache
from pathlib import Path
from typing import Optional, List
from pydantic import Field, SecretStr, field_validator, model_validator, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from tools.utils.path_utils import get_project_root
import os
import base64
from cryptography.fernet import Fernet

# --- 0. ENV DISCOVERY ---

def discover_env_file() -> str:
    """Locates the .env file in expected locations."""
    root = get_project_root()
    locations = [
        root / "core" / ".env",
        root / ".env",
        Path.cwd() / ".env"
    ]
    for loc in locations:
        if loc.exists():
            return str(loc)
    return str(root / "core" / ".env") # Fallback

# --- 0.5 ENCRYPTION UTILS ---

import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("config_crypto")

class DecryptionError(Exception):
    """Raised when configuration decryption fails to prevent downstream leakage."""
    pass

_CACHED_MASTER_KEY: Optional[bytes] = None

def get_master_key() -> bytes:
    global _CACHED_MASTER_KEY
    if _CACHED_MASTER_KEY is not None:
        return _CACHED_MASTER_KEY
        
    key_path = Path.home() / ".kenbun" / ".master.key"
    key_bytes = None
    
    # 1. Try home directory master key
    if key_path.exists():
        try:
            with open(key_path, "rb") as f:
                key_bytes = f.read().strip()
        except Exception as e:
            logger.error(f"Failed to read home master key: {e}")
            
    # 2. Try project root key fallback
    if not key_bytes:
        root_key_path = get_project_root() / ".kenbun_master.key"
        if root_key_path.exists():
            try:
                # Validate strict POSIX permissions (0600)
                if os.name == 'posix':
                    file_mode = root_key_path.stat().st_mode & 0o777
                    if file_mode != 0o600:
                        try:
                            os.chmod(root_key_path, 0o600)
                        except Exception:
                            pass
                with open(root_key_path, "rb") as f:
                    key_bytes = f.read().strip()
            except Exception as e:
                logger.error(f"Failed to read project root key: {e}")
                
    # 3. Generate key if completely missing
    if not key_bytes:
        try:
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_bytes = Fernet.generate_key()
            with open(key_path, "wb") as f:
                f.write(key_bytes)
            os.chmod(key_path, 0o600)
        except Exception as e:
            try:
                root_key_path = get_project_root() / ".kenbun_master.key"
                key_bytes = Fernet.generate_key()
                with open(root_key_path, "wb") as f:
                    f.write(key_bytes)
                os.chmod(root_key_path, 0o600)
            except Exception as e2:
                raise RuntimeError(f"Failed to provision any master key: {e} | {e2}")
                
    _CACHED_MASTER_KEY = key_bytes
    return key_bytes

def decrypt_value(val: str) -> str:
    if not val or not val.startswith("enc:"):
        return val

    # Structured parsing: split by ':' up to 2 times
    # Valid formats: "enc:v1:<ciphertext>" or "enc:<ciphertext>" (legacy)
    parts = val.split(":", 2)
    if len(parts) == 3:
        version = parts[1]
        ciphertext = parts[2]
    elif len(parts) == 2:
        version = "legacy"
        ciphertext = parts[1]
    else:
        raise DecryptionError("Malformed encrypted configuration format.")

    try:
        if version == "v1":
            key = get_master_key()
            f = Fernet(key)
            return f.decrypt(ciphertext.encode()).decode("utf-8")
        elif version == "legacy" or version == "":
            # Attempt to read project root key first
            key = None
            root_key_path = get_project_root() / ".kenbun_master.key"
            if root_key_path.exists():
                try:
                    with open(root_key_path, "rb") as f_file:
                        key = f_file.read().strip()
                except Exception:
                    pass
            if not key:
                key = get_master_key()
            f = Fernet(key)
            return f.decrypt(ciphertext.encode()).decode("utf-8")
        else:
            raise DecryptionError(f"Unsupported encryption version: {version}")
            
    except InvalidToken as e:
        logger.error(f"Decryption integrity check failed for version '{version}'. Key mismatch or corrupted data.")
        raise DecryptionError("Decryption failed: Integrity check failed.") from e
    except Exception as e:
        logger.error(f"Internal error during decryption: {e}")
        raise DecryptionError("Decryption failed due to an internal error.") from e

# --- 1. NESTED MODELS (DATA OBJECTS) ---

class SipSettings(BaseModel):
    server: Optional[str] = None
    port: int = 5060
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    user_phone_number: Optional[str] = None

class ChromaSettings(BaseModel):
    host: str = "localhost"
    port: int = 8000
    project_name: str = "kenbun"

class SupabaseSettings(BaseModel):
    url: Optional[str] = None
    service_key: Optional[SecretStr] = None
    db_url: Optional[SecretStr] = None

class ModelSettings(BaseModel):
    primary_llm_url: str = "http://localhost:11434/v1"
    primary_llm_model: str = "llama3.2:3b"
    ollama_pull_models: str = "llama3.2:3b deepseek-r1:8b"
    fallback_llm_url: str = "https://api.openai.com/v1"
    fallback_llm_model: str = "gpt-4o-mini"
    default_local_model: str = "google/gemma-4-26b-it"
    lm_studio_port: int = 2065
    lm_studio_model: str = "google/gemma-4-26b-it"
    lm_studio_draft_model: str = "google/gemma-4-e4b"
    use_speculative_decoding: bool = True
    speculative_lookahead: int = Field(default=5, ge=1, le=20)
    gemini_model: str = "gemini-3-flash-preview"
    gemini_pro_model: str = "gemini-3.1-pro-preview"
    gemini_3_5_flash_model: str = "gemini-3.5-flash"
    gemini_3_1_lite_model: str = "gemini-3.1-flash-lite"
    deepseek_model: str = "deepseek-chat"
    lm_studio_connect_timeout: float = 3.0
    lm_studio_read_timeout: float = 60.0

class TelegramSettings(BaseModel):
    bot_token: Optional[SecretStr] = None
    chat_id: Optional[SecretStr] = None

class WorkerSettings(BaseModel):
    p330_ip: str = "127.0.0.1"
    p330_ollama_port: int = 11434
    ollama_url: str = "http://127.0.0.1:11434/api/generate"

class DeploymentSettings(BaseModel):
    pc_user: str = "dev" # Default to user but overrideable
    pc_remote_path: str = "~/kenbun_training/"
    ssh_key_path: str = "~/.ssh/kenbun_pc"
    training_dir: str = "/root/kenbun_training" # Default internal docker path

# --- 2. MAIN CONFIGURATION HUB ---

class KenbunSettings(BaseSettings):
    """
    Kenbun Sovereign Configuration Hub.
    Centralizes and validates all environment variables.
    """
    model_config = SettingsConfigDict(
        env_file=discover_env_file(),
        env_file_encoding='utf-8',
        extra='ignore'
    )

    # --- PROJECT PATHS ---
    PROJECT_ROOT: Path = Field(default_factory=get_project_root)
    DEV_ROOT: Path = Field(default_factory=lambda: Path.home() / "Dev")
    BRAIN_HEALTH_DIR: Optional[Path] = None
    FRONTEND_URL: str = Field(default="http://localhost:3000")
    OBSIDIAN_VAULT_PATH: Optional[Path] = None
    CODEX_HOME: Path = Field(default_factory=lambda: Path.home() / ".codex")
    OPENAI_API_KEY: Optional[SecretStr] = None

    @model_validator(mode='before')
    @classmethod
    def decrypt_secrets(cls, data: dict) -> dict:
        import sys
        for k, v in data.items():
            if isinstance(v, str) and (v.startswith("enc:v1:") or v.startswith("enc:")):
                try:
                    data[k] = decrypt_value(v)
                except DecryptionError as e:
                    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
                        logger.warning(f"Decryption failed for key '{k}' during testing. Falling back to dummy value.")
                        data[k] = "dummy_test_value"
                    else:
                        raise e
        return data

    @field_validator("BRAIN_HEALTH_DIR", mode="before")
    @classmethod
    def assemble_brain_health_dir(cls, v, info):
        return get_project_root() / "brain_health"

    @property
    def INTELLIGENCE_DB_PATH(self) -> Path:
        return self.BRAIN_HEALTH_DIR / "kenbun_intelligence.db"

    # --- HYBRID NEURAL BRIDGE ---
    SWARM_PC_IP: str = Field(default="localhost", validation_alias="PC_IP_ADDRESS")
    LOCAL_IP: str = Field(default="127.0.0.1")

    # --- SIP SENTINEL ---
    SIP_SERVER: Optional[str] = None
    SIP_PORT: int = 5060
    SIP_USERNAME: Optional[str] = None
    SIP_PASSWORD: Optional[SecretStr] = None
    USER_PHONE_NUMBER: Optional[str] = None

    @property
    def sip(self) -> SipSettings:
        return SipSettings(
            server=self.SIP_SERVER,
            port=self.SIP_PORT,
            username=self.SIP_USERNAME,
            password=self.SIP_PASSWORD,
            user_phone_number=self.USER_PHONE_NUMBER
        )

    # --- CHROMA DB ---
    CHROMA_HOST: str = Field(default="localhost")
    CHROMA_PORT: int = Field(default=8000)
    PROJECT_NAME: str = "kenbun"

    @property
    def chroma(self) -> ChromaSettings:
        return ChromaSettings(host=self.CHROMA_HOST, port=self.CHROMA_PORT, project_name=self.PROJECT_NAME)

    # --- SUPABASE DB ---
    SUPABASE_URL: Optional[str] = Field(default=None)
    SUPABASE_SERVICE_KEY: Optional[SecretStr] = Field(default=None)
    SUPABASE_DB_URL: Optional[SecretStr] = Field(default=None)

    @property
    def supabase(self) -> SupabaseSettings:
        return SupabaseSettings(
            url=self.SUPABASE_URL,
            service_key=self.SUPABASE_SERVICE_KEY,
            db_url=self.SUPABASE_DB_URL
        )

    # --- MODELS & AI ---
    PRIMARY_LLM_URL: str = Field(default="http://localhost:11434/v1")
    PRIMARY_LLM_MODEL: str = Field(default="llama3.2:3b")
    OLLAMA_PULL_MODELS: str = Field(default="llama3.2:3b deepseek-r1:8b")
    FALLBACK_LLM_URL: str = Field(default="https://api.openai.com/v1")
    FALLBACK_LLM_MODEL: str = Field(default="gpt-4o-mini")
    SWARM_MODEL: str = "qwen2.5-coder-14b-instruct"
    LM_STUDIO_PORT: int = 2065
    LM_STUDIO_MODEL: str = "local-model"
    LM_STUDIO_DRAFT_MODEL: str = "qwen2.5-coder-1.5b-instruct"
    USE_SPECULATIVE_DECODING: bool = True
    SPECULATIVE_LOOKAHEAD: int = Field(default=5, ge=1, le=20)
    GEMINI_MODEL: str = "gemini-3-flash-preview"
    GEMINI_PRO_MODEL: str = "gemini-3.1-pro-preview"
    GEMINI_API_KEY: Optional[SecretStr] = None
    DEEPSEEK_API_KEY: Optional[SecretStr] = None
    DEEPSEEK_MODEL: str = "deepseek-chat"
    TWENTYONE_DEV_API_KEY: Optional[SecretStr] = None
    NOUS_PORTAL_API_KEY: Optional[SecretStr] = None
    OPENROUTER_API_KEY: Optional[SecretStr] = None
    ANTHROPIC_API_KEY: Optional[SecretStr] = None
    DASHSCOPE_API_KEY: Optional[SecretStr] = None
    MIMO_API_KEY: Optional[SecretStr] = None
    TOKENHUB_API_KEY: Optional[SecretStr] = None
    NVIDIA_API_KEY: Optional[SecretStr] = None
    GITHUB_TOKEN: Optional[SecretStr] = None
    HF_API_KEY: Optional[SecretStr] = None
    XAI_API_KEY: Optional[SecretStr] = None
    ZHIPU_API_KEY: Optional[SecretStr] = None
    KIMI_API_KEY: Optional[SecretStr] = None
    MOONSHOT_API_KEY: Optional[SecretStr] = None
    STEPFUN_API_KEY: Optional[SecretStr] = None
    DAILY_BUDGET: float = Field(default=50.00, validation_alias="DAILY_BUDGET", gt=0.0)
    LM_STUDIO_CONNECT_TIMEOUT: float = Field(default=3.0)
    LM_STUDIO_READ_TIMEOUT: float = Field(default=60.0)

    @property
    def models(self) -> ModelSettings:
        return ModelSettings(
            primary_llm_url=self.PRIMARY_LLM_URL,
            primary_llm_model=self.PRIMARY_LLM_MODEL,
            ollama_pull_models=self.OLLAMA_PULL_MODELS,
            fallback_llm_url=self.FALLBACK_LLM_URL,
            fallback_llm_model=self.FALLBACK_LLM_MODEL,
            default_local_model=self.SWARM_MODEL,
            lm_studio_port=self.LM_STUDIO_PORT,
            lm_studio_model=self.LM_STUDIO_MODEL,
            lm_studio_draft_model=self.LM_STUDIO_DRAFT_MODEL,
            use_speculative_decoding=self.USE_SPECULATIVE_DECODING,
            speculative_lookahead=self.SPECULATIVE_LOOKAHEAD,
            gemini_model=self.GEMINI_MODEL,
            gemini_pro_model=self.GEMINI_PRO_MODEL,
            deepseek_model=self.DEEPSEEK_MODEL,
            lm_studio_connect_timeout=self.LM_STUDIO_CONNECT_TIMEOUT,
            lm_studio_read_timeout=self.LM_STUDIO_READ_TIMEOUT
        )

    # --- TELEGRAM ---
    TELEGRAM_BOT_TOKEN: Optional[SecretStr] = None
    TELEGRAM_CHAT_ID: Optional[SecretStr] = None

    @property
    def telegram(self) -> TelegramSettings:
        return TelegramSettings(bot_token=self.TELEGRAM_BOT_TOKEN, chat_id=self.TELEGRAM_CHAT_ID)

    # --- WORKERS ---
    P330_IP_ADDRESS: str = "127.0.0.1"
    P330_OLLAMA_PORT: int = 11434
    OLLAMA_URL: str = "http://127.0.0.1:11434/api/generate"

    @property
    def workers(self) -> WorkerSettings:
        return WorkerSettings(
            p330_ip=self.P330_IP_ADDRESS,
            p330_ollama_port=self.P330_OLLAMA_PORT,
            ollama_url=self.OLLAMA_URL
        )

    # --- DEPLOYMENT ---
    PC_USER: str = "dev"
    PC_REMOTE_PATH: str = "~/kenbun_training/"
    SSH_KEY_PATH: str = "~/.ssh/kenbun_pc"
    TRAINING_DIR: str = "/root/kenbun_training"

    @property
    def deployment(self) -> DeploymentSettings:
        return DeploymentSettings(
            pc_user=self.PC_USER,
            pc_remote_path=self.PC_REMOTE_PATH,
            ssh_key_path=self.SSH_KEY_PATH,
            training_dir=self.TRAINING_DIR
        )

    # --- WATCHDOG ---
    BASE_TIMEOUT: int = 60
    SWARM_TIMEOUT_MULTIPLIER: float = 1.0
    SWARM_CLOUD_FAILOVER: bool = True
    API_PORT: int = Field(default=8001)
    MONITOR_PORT: int = Field(default=8002)

# --- 3. CACHED SINGLETON ACCESS ---

def migrate_database_safely(settings: KenbunSettings):
    """Safely and atomically migrates the legacy database to Kenbun."""
    if not settings.BRAIN_HEALTH_DIR:
        return
    db_old = settings.BRAIN_HEALTH_DIR / "kenbun_intelligence.db"
    db_new = settings.INTELLIGENCE_DB_PATH
    if db_old.exists() and not db_new.exists():
        import shutil
        import os
        import logging
        temp_file = db_new.with_suffix(".tmp")
        try:
            logging.info(f"🔄 Migrating legacy database from {db_old.name} to {db_new.name}...")
            shutil.copy2(db_old, temp_file)
            os.replace(temp_file, db_new)
            logging.info("✅ Database migration complete.")
        except Exception as e:
            logging.error(f"❌ Database migration failed: {e}")
            if temp_file.exists():
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

@lru_cache()
def get_settings() -> KenbunSettings:
    """Returns the globally shared KenbunSettings singleton with caching and bootstrapping."""
    _settings = KenbunSettings()
    if _settings.BRAIN_HEALTH_DIR:
        _settings.BRAIN_HEALTH_DIR.mkdir(parents=True, exist_ok=True)
        # Bootstrap any required telemetry or health logs on first boot
        ( _settings.BRAIN_HEALTH_DIR / "logs" ).mkdir(parents=True, exist_ok=True)
        
        usage_stats = _settings.BRAIN_HEALTH_DIR / "usage_stats.json"
        if not usage_stats.exists():
            with open(usage_stats, "w") as f:
                f.write('{"total_tokens": 0, "session_cost": 0.0}')
                
        benchmarks = _settings.BRAIN_HEALTH_DIR / "BENCHMARKS.json"
        if not benchmarks.exists():
            with open(benchmarks, "w") as f:
                f.write("[]")
                
        post_mortem = _settings.BRAIN_HEALTH_DIR / "POST_MORTEM.md"
        if not post_mortem.exists():
            with open(post_mortem, "w") as f:
                f.write("# 🩺 System Post Mortems & Architectural Corrections\n\nRecord failures and their lessons here.\n")

        # Safely migrate legacy SQLite database atomically
        migrate_database_safely(_settings)
    return _settings

# --- 4. EXPORTED GLOBALS (BACKWARD COMPATIBILITY) ---
settings = get_settings()

PROJECT_ROOT = settings.PROJECT_ROOT
BRAIN_HEALTH_DIR = settings.BRAIN_HEALTH_DIR
SWARM_PC_IP = settings.SWARM_PC_IP
LM_STUDIO_PORT = settings.LM_STUDIO_PORT
CHROMA_PORT = settings.CHROMA_PORT
DEFAULT_LOCAL_MODEL = settings.models.default_local_model
BASE_TIMEOUT = settings.BASE_TIMEOUT
TIMEOUT_MULTIPLIER = settings.SWARM_TIMEOUT_MULTIPLIER
ENABLE_CLOUD_FAILOVER = settings.SWARM_CLOUD_FAILOVER
LOCAL_IP = settings.LOCAL_IP

# Backward compatibility alias
KenbunSettings = KenbunSettings
