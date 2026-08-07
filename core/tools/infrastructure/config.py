from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic import Field, SecretStr, field_validator, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from tools.utils.path_utils import get_project_root

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
    default_local_model: str = "google/gemma-4-26b-a4b"
    lm_studio_port: int = 2065
    lm_studio_model: str = "google/gemma-4-26b-a4b"
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
    ollama_pull_models: str = "qwen2.5:1.5b"
    primary_llm_model: str = "qwen2.5:1.5b"  # Set by bootstrap.py wizard
    openai_runtime: str = "auto"


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
    sandbox_mode: str = "docker"

class BitwardenSettings(BaseModel):
    enabled: bool = False
    access_token_env: str = "BWS_ACCESS_TOKEN"
    project_id: str = ""
    server_url: str = ""
    cache_ttl_seconds: int = 300
    override_existing: bool = True
    auto_install: bool = True

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
    BRAIN_HEALTH_DIR: Path = Field(default_factory=lambda: get_project_root() / "brain_health")
    FRONTEND_URL: str = Field(default="http://localhost:3000")
    MASTER_KEY_PATH: Path = Field(default_factory=lambda: Path.home() / ".gemini" / "antigravity" / "keys" / ".kenbun_master.key")
    OLD_MASTER_KEY_PATH: Path = Field(default_factory=lambda: Path.home() / ".gemini" / "antigravity" / "keys" / ".antigravity_master.key")
    OBSIDIAN_VAULT_PATH: Optional[Path] = None
    CODEX_HOME: Path = Field(default_factory=lambda: Path.home() / ".codex")
    OPENAI_API_KEY: Optional[SecretStr] = None

    @field_validator("PROJECT_ROOT", mode="after")
    @classmethod
    def resolve_project_root(cls, v: Path) -> Path:
        if not v.is_absolute():
            return (get_project_root() / v).resolve()
        return v.resolve()

    @field_validator("BRAIN_HEALTH_DIR", mode="before")
    @classmethod
    def assemble_brain_health_dir(cls, v, info):
        if v is None:
            return get_project_root() / "brain_health"
        return Path(v)

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

    # --- ORCHESTRATION ---
    MAX_CONCURRENT_ORCHESTRATE_JOBS: int = Field(default=10)
    ORCHESTRATE_JOB_TIMEOUT_SEC: int = Field(default=600)
    CONFIG_TOKEN: Optional[str] = Field(default=None)

    # --- SECRETS & BITWARDEN ---
    secrets_bitwarden_enabled: bool = Field(default=False, validation_alias="SECRETS_BITWARDEN_ENABLED")
    secrets_bitwarden_access_token_env: str = Field(default="BWS_ACCESS_TOKEN")
    secrets_bitwarden_project_id: str = Field(default="")
    secrets_bitwarden_server_url: str = Field(default="")
    secrets_bitwarden_cache_ttl_seconds: int = Field(default=300)
    secrets_bitwarden_override_existing: bool = Field(default=True)
    secrets_bitwarden_auto_install: bool = Field(default=True)

    @property
    def secrets_bitwarden(self) -> BitwardenSettings:
        return BitwardenSettings(
            enabled=self.secrets_bitwarden_enabled,
            access_token_env=self.secrets_bitwarden_access_token_env,
            project_id=self.secrets_bitwarden_project_id,
            server_url=self.secrets_bitwarden_server_url,
            cache_ttl_seconds=self.secrets_bitwarden_cache_ttl_seconds,
            override_existing=self.secrets_bitwarden_override_existing,
            auto_install=self.secrets_bitwarden_auto_install
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

    # --- POSTGRES DB ---
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_USER: str = Field(default="appuser")
    POSTGRES_PASSWORD: str = Field(default="kenbun")
    POSTGRES_DB: str = Field(default="kenbun_intelligence")

    # --- MODELS & AI ---
    SWARM_MODEL: str = "qwen2.5-coder-14b-instruct"
    LM_STUDIO_PORT: int = 2065
    LM_STUDIO_MODEL: str = "local-model"
    LM_STUDIO_DRAFT_MODEL: str = "qwen2.5-coder-1.5b-instruct"
    USE_SPECULATIVE_DECODING: bool = True
    SPECULATIVE_LOOKAHEAD: int = Field(default=5, ge=1, le=20)
    GEMINI_MODEL: str = "gemini-3-flash-preview"
    GEMINI_PRO_MODEL: str = "gemini-3.1-pro-preview"
    GEMINI_API_KEY: Optional[SecretStr] = None
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
    OLLAMA_PULL_MODELS: str = "qwen2.5:1.5b"
    PRIMARY_LLM_URL: Optional[str] = None
    PRIMARY_LLM_MODEL: str = "qwen2.5:1.5b"
    # Adversarial Court judgment model. The court's verdict short-circuits the
    # whole supervisor, so it needs a model strong enough not to hallucinate
    # vulnerabilities; small primaries (1.5b-3b) reject safe code with invented
    # RCE claims. Falls back to PRIMARY_LLM_MODEL when unset.
    COURT_LLM_MODEL: Optional[str] = None
    # Tier 2 "Supreme Evaluator" audit model. This is the strong rung of the
    # oversight ladder — it must never be pinned behind the models it audits, or
    # the supervisor/executor capability gap silently inverts. Was hardcoded to
    # claude-3-5-sonnet-20241022 in supervisor_agent.py.
    AUDIT_LLM_MODEL: str = "claude-sonnet-5"
    AUDIT_LLM_URL: str = "https://api.anthropic.com/v1"
    OLLAMA_PORT: int = 11434
    FALLBACK_LLM_URL: Optional[str] = None
    OPENAI_RUNTIME: str = Field(default="auto")
    FALLBACK_LLM_MODEL: Optional[str] = None
    SPECULATIVE_SERVER_IP: Optional[str] = None
    SPECULATIVE_SERVER_PORT: Optional[int] = None
    SPECULATIVE_SERVER_MODEL: Optional[str] = None
    SPECULATIVE_LATENCY_THRESHOLD_SEC: Optional[float] = None
    CODE_EXECUTION_MODE: str = Field(default="project")
    CODE_EXECUTION_TIMEOUT: int = Field(default=300)
    CODE_EXECUTION_MAX_TOOL_CALLS: int = Field(default=50)

    # --- WEB SEARCH & EXTRACT ---
    FIRECRAWL_API_KEY: Optional[SecretStr] = None
    FIRECRAWL_API_URL: Optional[str] = None
    SEARXNG_URL: Optional[str] = None
    BRAVE_SEARCH_API_KEY: Optional[SecretStr] = None
    TAVILY_API_KEY: Optional[SecretStr] = None
    EXA_API_KEY: Optional[SecretStr] = None
    PARALLEL_API_KEY: Optional[SecretStr] = None
    WEB_BACKEND: str = Field(default="ddgs")
    WEB_SEARCH_BACKEND: Optional[str] = None
    WEB_EXTRACT_BACKEND: Optional[str] = None
    AUXILIARY_WEB_EXTRACT_PROVIDER: str = Field(default="auto")
    AUXILIARY_WEB_EXTRACT_MODEL: Optional[str] = None
    AUXILIARY_WEB_EXTRACT_TIMEOUT: int = Field(default=360)

    # --- BROWSER AUTOMATION ---
    BROWSERBASE_API_KEY: Optional[SecretStr] = None
    BROWSERBASE_PROJECT_ID: Optional[str] = None
    BROWSER_USE_API_KEY: Optional[SecretStr] = None
    CAMOFOX_URL: Optional[str] = None
    CAMOFOX_USER_ID: Optional[str] = None
    CAMOFOX_SESSION_KEY: Optional[str] = None
    CAMOFOX_ADOPT_EXISTING_TAB: bool = Field(default=False)
    CAMOFOX_REWRITE_LOOPBACK_URLS: bool = Field(default=False)
    CAMOFOX_LOOPBACK_HOST_ALIAS: str = Field(default="host.docker.internal")
    CAMOFOX_MANAGED_PERSISTENCE: bool = Field(default=False)
    BROWSER_CLOUD_PROVIDER: Optional[str] = None
    BROWSER_AUTO_LOCAL_FOR_PRIVATE_URLS: bool = Field(default=True)
    BROWSER_ALLOW_PRIVATE_URLS: bool = Field(default=False)
    BROWSER_RECORD_SESSIONS: bool = Field(default=False)
    BROWSER_INACTIVITY_TIMEOUT: int = Field(default=120)
    BROWSER_DIALOG_POLICY: str = Field(default="must_respond")
    BROWSER_DIALOG_TIMEOUT_S: int = Field(default=300)
    AGENT_BROWSER_ARGS: Optional[str] = None

    # --- COMPUTER USE ---
    CUA_DRIVER_CMD: str = Field(default="cua-driver")
    CUA_TELEMETRY: bool = Field(default=False)
    COMPUTER_USE_BACKEND: str = Field(default="mcp")
    COMPUTER_USE_APPROVAL_REQUIRED: bool = Field(default=True)

    # --- VISION & IMAGE PASTE ---
    AUXILIARY_VISION_PROVIDER: str = Field(default="auto")
    AUXILIARY_VISION_MODEL: Optional[str] = None
    AUXILIARY_VISION_TIMEOUT: int = Field(default=360)

    # --- VOICE & TTS ---
    TTS_PROVIDER: str = Field(default="edge")
    TTS_SPEED: float = Field(default=1.0)
    STT_PROVIDER: str = Field(default="local")
    STT_MODEL: str = Field(default="base")
    KENBUN_CONFIG_PATH: str = Field(default="~/.kenbun/config.yaml")




    @property
    def models(self) -> ModelSettings:
        return ModelSettings(
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
            lm_studio_read_timeout=self.LM_STUDIO_READ_TIMEOUT,
            ollama_pull_models=self.OLLAMA_PULL_MODELS,
            openai_runtime=self.OPENAI_RUNTIME
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
    SECURITY_SANDBOX_MODE: str = Field(default="docker")

    @property
    def security(self) -> SecuritySettings:
        security_settings_instance = SecuritySettings(
            cron_mode=self.SECURITY_CRON_MODE,
            approval_mode=self.SECURITY_APPROVAL_MODE,
            approval_timeout=self.SECURITY_APPROVAL_TIMEOUT,
            custom_hook_path=self.SECURITY_CUSTOM_HOOK_PATH,
            sandbox_mode=self.SECURITY_SANDBOX_MODE
        )
        return security_settings_instance

    # --- WATCHDOG & TELEMETRY ---
    BASE_TIMEOUT: int = 120              # Per-step timeout budget (seconds)
    GEMINI_STEP_TIMEOUT: int = 90        # Dedicated timeout for Gemini steps (seconds)
    SWARM_TIMEOUT_MULTIPLIER: float = 1.0

    # --- SUPERVISOR (System 2) TIER BUDGETS ---
    # These are the authoritative per-tier budgets that supervisor_agent enforces
    # internally. They live here so the orchestrator's watchdog can be derived
    # from them instead of guessing: the supervisor step used to inherit
    # BASE_TIMEOUT (120s) while its own tiers were allowed to spend up to 405s,
    # so `supervisor_review` was killed mid-deliberation on every pipeline that
    # had the adversarial court enabled. A watchdog must never be tighter than
    # the budget of the thing it is watching.
    SUPERVISOR_COURT_TIMEOUT: int = 300     # Tier 1a: adversarial court (3 serialized LLM calls)
    SUPERVISOR_ENSEMBLE_TIMEOUT: int = 60   # Tier 1: local ensemble (runs parallel to the court)
    SUPERVISOR_CLOUD_TIMEOUT: int = 45      # Tier 2: cloud escalation
    SUPERVISOR_FALLBACK_TIMEOUT: int = 60   # Tier 3: local senior fallback
    SUPERVISOR_WATCHDOG_MARGIN: int = 15    # Headroom for tier hand-off overhead

    # --- TIER CALIBRATION (weak-to-strong bootstrapping) ---
    # A cheap rung may only auto-APPROVE in a category where it has been shown to
    # agree with the rung above it. Until then its approvals escalate instead of
    # short-circuiting. Rejections always short-circuit (fail-closed is free).
    AUDIT_CALIBRATION_ENABLED: bool = True
    # These two are tuned to bind together. The Wilson bound on a perfect record
    # reaches 0.85 at ~25 samples, so a category graduates at exactly the minimum
    # sample count if it never falsely approves — and a single unsafe approval in
    # those 25 drops the bound to ~0.80 and keeps it locked. Raising MIN_SAMPLES
    # without lowering MIN_AGREEMENT (or vice versa) makes one knob dead weight.
    AUDIT_CALIBRATION_MIN_SAMPLES: int = 25    # Paired approvals before a category can be trusted
    AUDIT_CALIBRATION_MIN_AGREEMENT: float = 0.85  # Wilson lower bound required on safe-approval rate
    # Fraction of short-circuited cheap approvals that still run the strong tier in
    # the background purely to collect paired observations. 0.0 disables live
    # sampling (offline golden-set runs still populate the store).
    AUDIT_CALIBRATION_SAMPLE_RATE: float = 0.15

    # --- APPEALS (letting the student discount the supervisor) ---
    # An executor whose code is rejected may contest once with evidence instead of
    # blindly re-healing. The appeal is adjudicated by the court under a reversed
    # burden of proof (the appellant must prove the critique wrong).
    AUDIT_APPEALS_ENABLED: bool = True
    AUDIT_APPEAL_MIN_CONFIDENCE: float = 0.75  # Judge confidence required to overturn

    # --- GENERATIVE SUPERVISION ---
    # Feed the court unrated repo context before it judges, so a weak judge can
    # tell "this helper already validates the path" from "nothing validates it".
    # Per-role budgets for the adversarial court. These were hardcoded at 90s /
    # 240s. A thinking judge on an 8B local model routinely exceeds 240s, and the
    # failure is silent: the aiohttp call raises, the code falls through to the
    # OpenAI-compatible gateway, and the gateway quietly serves the verdict from
    # a cloud model. The verdict still says "court_2a".
    COURT_BRIEF_TIMEOUT: int = 90
    COURT_JUDGE_TIMEOUT: int = 240
    COURT_REPO_CONTEXT_ENABLED: bool = True
    COURT_REPO_CONTEXT_CHUNKS: int = 4
    COURT_REPO_CONTEXT_TIMEOUT: float = 8.0
    COURT_REPO_CONTEXT_MAX_CHARS: int = 3000

    @property
    def SUPERVISOR_STEP_TIMEOUT(self) -> int:
        """Worst-case wall time a full supervisor consultation can legitimately take.

        Tier 1a (court) and Tier 1 (ensemble) race in parallel, so they cost
        max(), not sum(). If neither returns a verdict the agent falls through
        to Tier 2 and then Tier 3 sequentially.
        """
        return (
            max(self.SUPERVISOR_COURT_TIMEOUT, self.SUPERVISOR_ENSEMBLE_TIMEOUT)
            + self.SUPERVISOR_CLOUD_TIMEOUT
            + self.SUPERVISOR_FALLBACK_TIMEOUT
            + self.SUPERVISOR_WATCHDOG_MARGIN
        )
    SWARM_CLOUD_FAILOVER: bool = True
    TELEMETRY_ENABLED: bool = True
    NOTIFICATIONS_ENABLED: bool = True
    # AI IDE context — set to "claude", "cursor", "vscode", "windsurf", or "local"
    # Leave blank for auto-detection. Affects which pipeline steps run.
    KENBUN_CALLER_IDE: str = ""
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8001)
    MONITOR_PORT: int = Field(default=8002)
    # Internal URL the MCP / dashboard use to reach the FastAPI server. Set by
    # docker-compose to http://localhost:8001 inside the dashboard container and
    # http://fastmcp_server:8001 inside other compose services. Defaults to
    # 127.0.0.1 for host-side dev. Several call sites (server.py:601, :726)
    # read this directly via settings.INTERNAL_API_URL.
    INTERNAL_API_URL: str = Field(default="http://127.0.0.1:8001")
    DASHBOARD_PORT: int = Field(default=3000)
    DOZZLE_PORT: int = Field(default=8888)

    # --- GIT PUSH WATCHER ---
    GIT_WATCH_REPOS: str = Field(default="Clos01/Kenbun-Agent")
    GIT_WATCH_INTERVAL: int = Field(default=600)
    GITHUB_TOKEN: Optional[str] = Field(default=None)

    @property
    def GIT_WATCH_STATE_FILE(self) -> Path:
        return self.BRAIN_HEALTH_DIR / "git_watcher_state.json"

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
    try:
        from tools.utils.secrets_bitwarden import apply_secrets_to_env
        apply_secrets_to_env()
    except Exception as e:
        import sys
        sys.stderr.write(f"Warning: Failed to bootstrap Bitwarden secrets: {e}\n")
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
SWARM_PC_IP = settings.SWARM_PC_IP
LM_STUDIO_PORT = settings.LM_STUDIO_PORT
CHROMA_PORT = settings.CHROMA_PORT
DEFAULT_LOCAL_MODEL = settings.models.default_local_model
BASE_TIMEOUT = settings.BASE_TIMEOUT
TIMEOUT_MULTIPLIER = settings.SWARM_TIMEOUT_MULTIPLIER
ENABLE_CLOUD_FAILOVER = settings.SWARM_CLOUD_FAILOVER
LOCAL_IP = settings.LOCAL_IP

# Backward compatibility alias
AntigravitySettings = KenbunSettings
