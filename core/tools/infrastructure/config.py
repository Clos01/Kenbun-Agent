from functools import lru_cache
from pathlib import Path
from typing import Optional, List
from pydantic import Field, SecretStr, field_validator, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from core.tools.utils.path_utils import get_project_root

# --- 0. ENV DISCOVERY ---

def discover_env_file() -> str:
    """Locates the .env file in expected locations."""
    root = get_project_root()
    locations = [
        root / ".env",
        root / "core" / ".env",
        Path.cwd() / ".env"
    ]
    for loc in locations:
        if loc.exists():
            return str(loc)
    return str(root / ".env") # Fallback

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
    ollama_pull_models: str = "gemma4:12b deepseek-r1:8b"
    primary_llm_model: str = "gemma4:12b"  # Set by bootstrap.py wizard
    primary_llm_url: Optional[str] = None
    fallback_llm_url: Optional[str] = None
    fallback_llm_model: Optional[str] = None

class TelegramSettings(BaseModel):
    bot_token: Optional[SecretStr] = None
    chat_id: Optional[SecretStr] = None

class WorkerSettings(BaseModel):
    p330_ip: str = "127.0.0.1"
    p330_ollama_port: int = 11434
    ollama_url: str = "http://127.0.0.1:11434/api/generate"

class DeploymentSettings(BaseModel):
    pc_user: str = "appuser" # Default to user but overrideable
    pc_remote_path: str = "~/kenbun_training/"
    ssh_key_path: str = "~/.ssh/kenbun_pc"
    training_dir: str = "/app/kenbun_training" # Default internal docker path

class SecuritySettings(BaseModel):
    cron_mode: str = "allow"
    approval_mode: str = "smart"
    approval_timeout: int = 45
    custom_hook_path: Optional[str] = None

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
    MASTER_KEY_PATH: Path = Field(default_factory=lambda: Path.home() / ".gemini" / "antigravity" / "keys" / ".kenbun_master.key")
    OLD_MASTER_KEY_PATH: Path = Field(default_factory=lambda: Path.home() / ".gemini" / "antigravity" / "keys" / ".antigravity_master.key")
    OBSIDIAN_VAULT_PATH: Optional[Path] = None
    CODEX_HOME: Path = Field(default_factory=lambda: Path.home() / ".codex")
    OPENAI_API_KEY: Optional[SecretStr] = None

    @field_validator("BRAIN_HEALTH_DIR", mode="before")
    @classmethod
    def assemble_brain_health_dir(cls, v, info):
        return get_project_root() / "brain_health"

    @field_validator("PRIMARY_LLM_URL", "PRIMARY_LLM_MODEL", "FALLBACK_LLM_URL", "FALLBACK_LLM_MODEL", mode="before")
    @classmethod
    def decrypt_encrypted_fields(cls, v):
        if isinstance(v, str) and v.startswith("enc:"):
            from core.tools.utils.secret_manager import decrypt_value
            try:
                return decrypt_value(v)
            except Exception:
                return v
        return v

    @property
    def INTELLIGENCE_DB_PATH(self) -> Path:
        return self.BRAIN_HEALTH_DIR / "kenbun_intelligence.db"

    # --- HYBRID NEURAL BRIDGE ---
    ASSEMBLY_PC_IP: str = Field(default="localhost", validation_alias="PC_IP_ADDRESS")
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
    ASSEMBLY_MODEL: str = "qwen2.5-coder-14b-instruct"
    LM_STUDIO_PORT: int = 2065
    LM_STUDIO_MODEL: str = "local-model"
    LM_STUDIO_DRAFT_MODEL: str = "qwen2.5-coder-1.5b-instruct"
    USE_SPECULATIVE_DECODING: bool = True
    SPECULATIVE_LOOKAHEAD: int = Field(default=5, ge=1, le=20)
    GEMINI_MODEL: str = "gemini-3-flash-preview"
    GEMINI_PRO_MODEL: str = "gemini-3.1-pro-preview"
    GEMINI_API_KEY: Optional[SecretStr] = None
    GOOGLE_CLIENT_ID: Optional[SecretStr] = None
    GOOGLE_CLIENT_SECRET: Optional[SecretStr] = None
    ANTHROPIC_API_KEY: Optional[SecretStr] = None
    DEEPSEEK_API_KEY: Optional[SecretStr] = None
    OPENROUTER_API_KEY: Optional[SecretStr] = None
    NOUS_PORTAL_API_KEY: Optional[SecretStr] = None
    NVIDIA_API_KEY: Optional[SecretStr] = None
    XAI_API_KEY: Optional[SecretStr] = None
    ZHIPU_API_KEY: Optional[SecretStr] = None
    KIMI_API_KEY: Optional[SecretStr] = None
    MOONSHOT_API_KEY: Optional[SecretStr] = None
    STEPFUN_API_KEY: Optional[SecretStr] = None
    DASHSCOPE_API_KEY: Optional[SecretStr] = None
    MIMO_API_KEY: Optional[SecretStr] = None
    TOKENHUB_API_KEY: Optional[SecretStr] = None
    HF_API_KEY: Optional[SecretStr] = None
    DEEPSEEK_MODEL: str = "deepseek-chat"
    TWENTYONE_DEV_API_KEY: Optional[SecretStr] = None
    DAILY_BUDGET: float = Field(default=50.00, validation_alias="DAILY_BUDGET", gt=0.0)
    LM_STUDIO_CONNECT_TIMEOUT: float = Field(default=3.0)
    LM_STUDIO_READ_TIMEOUT: float = Field(default=60.0)
    OLLAMA_PULL_MODELS: str = "gemma4:12b deepseek-r1:8b"
    PRIMARY_LLM_URL: Optional[str] = None
    PRIMARY_LLM_MODEL: str = "gemma4:12b"
    OLLAMA_PORT: int = 11434
    FALLBACK_LLM_URL: Optional[str] = None
    FALLBACK_LLM_MODEL: Optional[str] = None
    SPECULATIVE_SERVER_IP: Optional[str] = None
    SPECULATIVE_SERVER_PORT: Optional[int] = None
    SPECULATIVE_SERVER_MODEL: Optional[str] = None
    SPECULATIVE_LATENCY_THRESHOLD_SEC: Optional[float] = None

    @property
    def models(self) -> ModelSettings:
        return ModelSettings(
            default_local_model=self.ASSEMBLY_MODEL,
            lm_studio_port=self.LM_STUDIO_PORT,
            lm_studio_model=self.LM_STUDIO_MODEL,
            lm_studio_draft_model=self.LM_STUDIO_DRAFT_MODEL,
            use_speculative_decoding=self.USE_SPECULATIVE_DECODING,
            speculative_lookahead=self.SPECULATIVE_LOOKAHEAD,
            gemini_model=self.GEMINI_MODEL,
            gemini_pro_model=self.GEMINI_PRO_MODEL,
            deepseek_model=self.DEEPSEEK_MODEL,
            lm_studio_connect_timeout=self.LM_STUDIO_CONNECT_TIMEOUT,
            lm_studio_read_timeout=self.LM_STUDIO_READ_TIMEOUT,
            ollama_pull_models=self.OLLAMA_PULL_MODELS,
            primary_llm_model=self.PRIMARY_LLM_MODEL,
            primary_llm_url=self.PRIMARY_LLM_URL,
            fallback_llm_url=self.FALLBACK_LLM_URL,
            fallback_llm_model=self.FALLBACK_LLM_MODEL
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
    PC_USER: str = "appuser"
    PC_REMOTE_PATH: str = "~/kenbun_training/"
    SSH_KEY_PATH: str = "~/.ssh/kenbun_pc"
    TRAINING_DIR: str = "/app/kenbun_training"
    OLLAMA_CONTAINER: str = Field(default="portable_ollama")

    @property
    def deployment(self) -> DeploymentSettings:
        return DeploymentSettings(
            pc_user=self.PC_USER,
            pc_remote_path=self.PC_REMOTE_PATH,
            ssh_key_path=self.SSH_KEY_PATH,
            training_dir=self.TRAINING_DIR
        )

    # --- SECURITY GATEWAY ---
    SECURITY_CRON_MODE: str = Field(default="allow")
    SECURITY_APPROVAL_MODE: str = Field(default="smart")
    SECURITY_APPROVAL_TIMEOUT: int = Field(default=45)
    SECURITY_CUSTOM_HOOK_PATH: Optional[str] = Field(default=None)

    @property
    def security(self) -> SecuritySettings:
        security_settings_instance = SecuritySettings(
            cron_mode=self.SECURITY_CRON_MODE,
            approval_mode=self.SECURITY_APPROVAL_MODE,
            approval_timeout=self.SECURITY_APPROVAL_TIMEOUT,
            custom_hook_path=self.SECURITY_CUSTOM_HOOK_PATH
        )
        return security_settings_instance

    # --- WATCHDOG & TELEMETRY ---
    BASE_TIMEOUT: int = 60
    ASSEMBLY_TIMEOUT_MULTIPLIER: float = 1.0
    ASSEMBLY_CLOUD_FAILOVER: bool = True
    TELEMETRY_ENABLED: bool = True
    NOTIFICATIONS_ENABLED: bool = True
    API_PORT: int = Field(default=8001)
    MONITOR_PORT: int = Field(default=8002)
    DASHBOARD_PORT: int = Field(default=3000)
    DOZZLE_PORT: int = Field(default=8888)

# --- 3. CACHED SINGLETON ACCESS ---

def migrate_database_safely(settings: KenbunSettings):
    """Safely and atomically migrates the legacy database to Kenbun."""
    if not settings.BRAIN_HEALTH_DIR:
        return
    db_old = settings.BRAIN_HEALTH_DIR / "antigravity_intelligence.db"
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
    """Returns the globally shared KenbunSettings singleton with caching."""
    _settings = KenbunSettings()
    if _settings.BRAIN_HEALTH_DIR:
        _settings.BRAIN_HEALTH_DIR.mkdir(parents=True, exist_ok=True)
        # Safely migrate legacy SQLite database atomically
        migrate_database_safely(_settings)
    return _settings

# --- 4. EXPORTED GLOBALS (BACKWARD COMPATIBILITY) ---
settings = get_settings()

PROJECT_ROOT = settings.PROJECT_ROOT
BRAIN_HEALTH_DIR = settings.BRAIN_HEALTH_DIR
ASSEMBLY_PC_IP = settings.ASSEMBLY_PC_IP
LM_STUDIO_PORT = settings.LM_STUDIO_PORT
CHROMA_PORT = settings.CHROMA_PORT
DEFAULT_LOCAL_MODEL = settings.models.default_local_model
BASE_TIMEOUT = settings.BASE_TIMEOUT
TIMEOUT_MULTIPLIER = settings.ASSEMBLY_TIMEOUT_MULTIPLIER
ENABLE_CLOUD_FAILOVER = settings.ASSEMBLY_CLOUD_FAILOVER
LOCAL_IP = settings.LOCAL_IP

# Backward compatibility alias
AntigravitySettings = KenbunSettings
