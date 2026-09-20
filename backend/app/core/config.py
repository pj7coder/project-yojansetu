from functools import lru_cache
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application Metadata
    app_name: str = Field(default="YojanSetu", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")

    # Server Network Configuration
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")

    # CORS & Client Origins
    frontend_url: str = Field(default="http://localhost:3000", alias="FRONTEND_URL")

    # Logging Configuration
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Database Configuration (PostgreSQL)
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="yojansetu", alias="POSTGRES_DB")
    postgres_user: str = Field(default="postgres", alias="POSTGRES_USER")
    postgres_password: str = Field(default="", alias="POSTGRES_PASSWORD")
    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")

    # Document Storage Configuration
    storage_root: str = Field(default="./storage", alias="STORAGE_ROOT")
    max_document_size_mb: int = Field(default=100, alias="MAX_DOCUMENT_SIZE_MB")
    watch_folder_enabled: bool = Field(default=True, alias="WATCH_FOLDER_ENABLED")

    # Duplicate & Version Detection Configuration
    duplicate_high_similarity_threshold: float = Field(default=0.98, alias="DUPLICATE_HIGH_SIMILARITY_THRESHOLD")
    version_candidate_threshold: float = Field(default=0.70, alias="VERSION_CANDIDATE_THRESHOLD")
    text_similarity_enabled: bool = Field(default=True, alias="TEXT_SIMILARITY_ENABLED")

    # Document Parser Configuration (Day 6)
    parser_type: str = Field(default="mineru", alias="PARSER_TYPE")
    mineru_cmd: str = Field(default="magic-pdf", alias="MINERU_CMD")
    parser_device: str = Field(default="auto", alias="PARSER_DEVICE")
    parser_timeout_seconds: int = Field(default=180, alias="PARSER_TIMEOUT_SECONDS")
    max_parse_pages: int = Field(default=200, alias="MAX_PARSE_PAGES")
    parser_fallback_enabled: bool = Field(default=True, alias="PARSER_FALLBACK_ENABLED")

    # OCR Configuration (Day 7)
    ocr_enabled: bool = Field(default=True, alias="OCR_ENABLED")
    ocr_provider: str = Field(default="paddleocr", alias="OCR_PROVIDER")
    ocr_device: str = Field(default="auto", alias="OCR_DEVICE")
    ocr_render_dpi: int = Field(default=250, alias="OCR_RENDER_DPI")
    ocr_min_text_chars: int = Field(default=50, alias="OCR_MIN_TEXT_CHARS")
    ocr_garbled_ratio_threshold: float = Field(default=0.15, alias="OCR_GARBLED_RATIO_THRESHOLD")
    ocr_max_pages_per_document: int = Field(default=100, alias="OCR_MAX_PAGES_PER_DOCUMENT")
    ocr_page_max_retries: int = Field(default=2, alias="OCR_PAGE_MAX_RETRIES")
    ocr_worker_concurrency: int = Field(default=1, alias="OCR_WORKER_CONCURRENCY")
    ocr_fallback_enabled: bool = Field(default=True, alias="OCR_FALLBACK_ENABLED")
    ocr_numeric_confidence_threshold: float = Field(default=0.80, alias="OCR_NUMERIC_CONFIDENCE_THRESHOLD")

    # Document Chunking Configuration (Day 8)
    chunk_target_tokens: int = Field(default=1200, alias="CHUNK_TARGET_TOKENS")
    chunk_max_tokens: int = Field(default=1800, alias="CHUNK_MAX_TOKENS")
    chunk_min_tokens: int = Field(default=150, alias="CHUNK_MIN_TOKENS")
    chunk_overlap_tokens: int = Field(default=200, alias="CHUNK_OVERLAP_TOKENS")
    chunk_strategy_version: str = Field(default="1.0", alias="CHUNK_STRATEGY_VERSION")
    chunk_schema_version: str = Field(default="1.0", alias="CHUNK_SCHEMA_VERSION")

    # LLM & Extraction Configuration (Day 9)
    ollama_base_url: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.2:3b", alias="OLLAMA_MODEL")
    llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE")
    llm_num_ctx: int = Field(default=2048, alias="LLM_NUM_CTX")
    llm_extraction_max_retries: int = Field(default=1, alias="LLM_EXTRACTION_MAX_RETRIES")
    llm_request_timeout_seconds: int = Field(default=45, alias="LLM_REQUEST_TIMEOUT_SECONDS")
    llm_worker_concurrency: int = Field(default=1, alias="LLM_WORKER_CONCURRENCY")
    extraction_prompt_version: str = Field(default="1.0", alias="EXTRACTION_PROMPT_VERSION")
    extraction_schema_version: str = Field(default="1.0", alias="EXTRACTION_SCHEMA_VERSION")

    # Canonical Normalization Configuration (Day 10)
    canonical_schema_version: str = Field(default="1.0", alias="CANONICAL_SCHEMA_VERSION")
    normalizer_version: str = Field(default="1.0", alias="NORMALIZER_VERSION")

    # Deterministic Validation Configuration (Day 11)
    validator_version: str = Field(default="1.0", alias="VALIDATOR_VERSION")
    validation_schema_version: str = Field(default="1.0", alias="VALIDATION_SCHEMA_VERSION")
    max_reasonable_age: int = Field(default=125, alias="MAX_REASONABLE_AGE")
    max_rule_depth: int = Field(default=20, alias="MAX_RULE_DEPTH")

    # Second-Pass Evidence Verification Configuration (Day 12)
    evidence_verifier_version: str = Field(default="1.0", alias="EVIDENCE_VERIFIER_VERSION")
    evidence_verification_prompt_version: str = Field(default="1.0", alias="EVIDENCE_VERIFICATION_PROMPT_VERSION")
    evidence_verification_schema_version: str = Field(default="1.0", alias="EVIDENCE_VERIFICATION_SCHEMA_VERSION")
    evidence_verifier_max_retries: int = Field(default=2, alias="EVIDENCE_VERIFIER_MAX_RETRIES")
    evidence_verifier_concurrency: int = Field(default=1, alias="EVIDENCE_VERIFIER_CONCURRENCY")
    evidence_context_blocks: int = Field(default=1, alias="EVIDENCE_CONTEXT_BLOCKS")

    # Day 15: Candidate Filtering & Semantic Ranking Configuration
    include_central_schemes: bool = Field(default=False, alias="INCLUDE_CENTRAL_SCHEMES")
    embedding_model_name: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        alias="EMBEDDING_MODEL_NAME",
    )
    embedding_dimension: int = Field(default=384, alias="EMBEDDING_DIMENSION")
    embedding_batch_size: int = Field(default=32, alias="EMBEDDING_BATCH_SIZE")
    search_index_version: str = Field(default="1.0", alias="SEARCH_INDEX_VERSION")
    discovery_engine_version: str = Field(default="1.0", alias="DISCOVERY_ENGINE_VERSION")
    discovery_default_limit: int = Field(default=5, alias="DISCOVERY_DEFAULT_LIMIT")
    discovery_max_limit: int = Field(default=20, alias="DISCOVERY_MAX_LIMIT")
    max_sql_candidates: int = Field(default=200, alias="MAX_SQL_CANDIDATES")
    semantic_ranking_enabled: bool = Field(default=True, alias="SEMANTIC_RANKING_ENABLED")

    # Rule Cache Configuration (Day 16)
    rule_cache_enabled: bool = Field(default=True, alias="RULE_CACHE_ENABLED")
    rule_cache_warm_on_start: bool = Field(default=False, alias="RULE_CACHE_WARM_ON_START")
    rule_cache_max_entries: int = Field(default=1000, alias="RULE_CACHE_MAX_ENTRIES")
    rule_cache_version: str = Field(default="1.0", alias="RULE_CACHE_VERSION")

    # Citizen Session Configuration (Day 16)
    citizen_session_ttl_minutes: int = Field(default=45, alias="CITIZEN_SESSION_TTL_MINUTES")
    max_active_sessions: int = Field(default=5000, alias="MAX_ACTIVE_SESSIONS")
    citizen_session_schema_version: str = Field(default="1.0", alias="CITIZEN_SESSION_SCHEMA_VERSION")

    # Intelligent Question Selection Configuration (Day 16)
    target_confirmed_schemes: int = Field(default=3, alias="TARGET_CONFIRMED_SCHEMES")
    question_relevance_weight: float = Field(default=1.5, alias="QUESTION_RELEVANCE_WEIGHT")
    question_resolution_bonus: float = Field(default=2.0, alias="QUESTION_RESOLUTION_BONUS")
    question_repeat_penalty: float = Field(default=3.0, alias="QUESTION_REPEAT_PENALTY")
    question_sensitivity_penalty: float = Field(default=0.5, alias="QUESTION_SENSITIVITY_PENALTY")
    question_selector_version: str = Field(default="1.0", alias="QUESTION_SELECTOR_VERSION")

    # Day 25: Deterministic Conversation Manager Configuration
    max_conversation_turns: int = Field(default=25, alias="MAX_CONVERSATION_TURNS")
    max_clarification_attempts: int = Field(default=3, alias="MAX_CLARIFICATION_ATTEMPTS")
    max_repeat_question_count: int = Field(default=3, alias="MAX_REPEAT_QUESTION_COUNT")
    conversation_manager_version: str = Field(default="1.0", alias="CONVERSATION_MANAGER_VERSION")
    conversation_debug_trace: bool = Field(default=False, alias="CONVERSATION_DEBUG_TRACE")


    # Source Monitoring Configuration (Day 17)
    monitoring_enabled: bool = Field(default=False, alias="MONITORING_ENABLED")
    monitor_http_timeout_seconds: int = Field(default=15, alias="MONITOR_HTTP_TIMEOUT_SECONDS")
    monitor_max_retries: int = Field(default=2, alias="MONITOR_MAX_RETRIES")
    monitor_max_html_bytes: int = Field(default=5 * 1024 * 1024, alias="MONITOR_MAX_HTML_BYTES")  # 5 MB
    monitor_max_concurrent_requests: int = Field(default=5, alias="MONITOR_MAX_CONCURRENT_REQUESTS")
    monitor_max_concurrent_per_host: int = Field(default=1, alias="MONITOR_MAX_CONCURRENT_PER_HOST")
    monitor_min_interval_minutes: int = Field(default=15, alias="MONITOR_MIN_INTERVAL_MINUTES")
    monitor_max_interval_minutes: int = Field(default=10080, alias="MONITOR_MAX_INTERVAL_MINUTES")  # 7 days
    monitor_unchanged_backoff_factor: float = Field(default=1.5, alias="MONITOR_UNCHANGED_BACKOFF_FACTOR")
    monitor_failure_backoff_factor: float = Field(default=2.0, alias="MONITOR_FAILURE_BACKOFF_FACTOR")
    monitor_jitter_percent: float = Field(default=0.10, alias="MONITOR_JITTER_PERCENT")
    monitor_user_agent: str = Field(
        default="YojanSetu-Monitor/1.0 (+https://yojansetu.rajasthan.gov.in/bot)",
        alias="MONITOR_USER_AGENT",
    )
    monitor_allow_private_ips_dev: bool = Field(default=False, alias="MONITOR_ALLOW_PRIVATE_IPS_DEV")

    # Day 18: Changed-Page Analysis, Discovery & Playwright Configuration
    change_analysis_enabled: bool = Field(default=False, alias="CHANGE_ANALYSIS_ENABLED")
    max_discovered_resources_per_event: int = Field(default=50, alias="MAX_DISCOVERED_RESOURCES_PER_EVENT")
    max_fetched_resources_per_event: int = Field(default=20, alias="MAX_FETCHED_RESOURCES_PER_EVENT")
    html_min_meaningful_text_chars: int = Field(default=300, alias="HTML_MIN_MEANINGFUL_TEXT_CHARS")
    playwright_enabled: bool = Field(default=True, alias="PLAYWRIGHT_ENABLED")
    playwright_page_timeout_seconds: int = Field(default=20, alias="PLAYWRIGHT_PAGE_TIMEOUT_SECONDS")
    relevance_llm_fallback_enabled: bool = Field(default=False, alias="RELEVANCE_LLM_FALLBACK_ENABLED")
    resource_max_bytes: int = Field(default=50 * 1024 * 1024, alias="RESOURCE_MAX_BYTES")  # 50 MB
    crawl_max_depth: int = Field(default=1, alias="CRAWL_MAX_DEPTH")
    html_diff_numeric_priority_enabled: bool = Field(default=True, alias="HTML_DIFF_NUMERIC_PRIORITY_ENABLED")

    @property
    def MONITORING_ENABLED(self) -> bool:
        return self.monitoring_enabled

    @property
    def MONITOR_HTTP_TIMEOUT_SECONDS(self) -> int:
        return self.monitor_http_timeout_seconds

    @property
    def MONITOR_MAX_RETRIES(self) -> int:
        return self.monitor_max_retries

    @property
    def MONITOR_MAX_HTML_BYTES(self) -> int:
        return self.monitor_max_html_bytes

    @property
    def MONITOR_MAX_CONCURRENT_REQUESTS(self) -> int:
        return self.monitor_max_concurrent_requests

    @property
    def MONITOR_MAX_CONCURRENT_PER_HOST(self) -> int:
        return self.monitor_max_concurrent_per_host

    @property
    def MONITOR_MIN_INTERVAL_MINUTES(self) -> int:
        return self.monitor_min_interval_minutes

    @property
    def MONITOR_MAX_INTERVAL_MINUTES(self) -> int:
        return self.monitor_max_interval_minutes

    @property
    def MONITOR_UNCHANGED_BACKOFF_FACTOR(self) -> float:
        return self.monitor_unchanged_backoff_factor

    @property
    def MONITOR_FAILURE_BACKOFF_FACTOR(self) -> float:
        return self.monitor_failure_backoff_factor

    @property
    def MONITOR_JITTER_SECONDS(self) -> int:
        return int(self.monitor_min_interval_minutes * 60 * self.monitor_jitter_percent)

    @property
    def MONITOR_USER_AGENT(self) -> str:
        return self.monitor_user_agent

    @property
    def MONITOR_ALLOW_PRIVATE_IPS_DEV(self) -> bool:
        return self.monitor_allow_private_ips_dev

    @property
    def CHANGE_ANALYSIS_ENABLED(self) -> bool:
        return self.change_analysis_enabled

    @property
    def MAX_DISCOVERED_RESOURCES_PER_EVENT(self) -> int:
        return self.max_discovered_resources_per_event

    @property
    def MAX_FETCHED_RESOURCES_PER_EVENT(self) -> int:
        return self.max_fetched_resources_per_event

    @property
    def HTML_MIN_MEANINGFUL_TEXT_CHARS(self) -> int:
        return self.html_min_meaningful_text_chars

    @property
    def PLAYWRIGHT_ENABLED(self) -> bool:
        return self.playwright_enabled

    @property
    def PLAYWRIGHT_PAGE_TIMEOUT_SECONDS(self) -> int:
        return self.playwright_page_timeout_seconds

    @property
    def RELEVANCE_LLM_FALLBACK_ENABLED(self) -> bool:
        return self.relevance_llm_fallback_enabled

    @property
    def RESOURCE_MAX_BYTES(self) -> int:
        return self.resource_max_bytes

    @property
    def CRAWL_MAX_DEPTH(self) -> int:
        return self.crawl_max_depth

    @property
    def HTML_DIFF_NUMERIC_PRIORITY_ENABLED(self) -> bool:
        return self.html_diff_numeric_priority_enabled


    @property
    def base_dir(self):
        from pathlib import Path
        return Path(__file__).resolve().parent.parent.parent

    @property
    def storage_path(self):
        from pathlib import Path
        root = Path(self.storage_root)
        if not root.is_absolute():
            return (self.base_dir / root).resolve()
        return root.resolve()

    @property
    def incoming_dir(self):
        return self.storage_path / "incoming"

    @property
    def originals_dir(self):
        return self.storage_path / "originals"

    @property
    def failed_dir(self):
        return self.storage_path / "failed"

    @property
    def fingerprints_dir(self):
        return self.storage_path / "fingerprints"

    @property
    def parsed_dir(self):
        return self.storage_path / "parsed"

    @property
    def parsed_storage_dir(self):
        return self.parsed_dir

    @property
    def ocr_dir(self):
        return self.storage_path / "ocr"

    @property
    def ocr_storage_dir(self):
        return self.ocr_dir

    @property
    def chunks_dir(self):
        return self.storage_path / "chunks"

    @property
    def chunks_storage_dir(self):
        return self.chunks_dir

    @property
    def extracted_dir(self):
        return self.storage_path / "extracted"

    @property
    def extracted_storage_dir(self):
        return self.extracted_dir

    @property
    def normalized_dir(self):
        return self.storage_path / "normalized"

    @property
    def normalized_storage_dir(self):
        return self.normalized_dir

    @property
    def validation_dir(self):
        return self.storage_path / "validation"

    @property
    def validation_storage_dir(self):
        return self.validation_dir

    @property
    def verification_dir(self):
        return self.storage_path / "verification"

    @property
    def verification_storage_dir(self):
        return self.verification_dir

    @property
    def verified_dir(self):
        return self.storage_path / "verified"

    @property
    def verified_storage_dir(self):
        return self.verified_dir

    @property
    def archived_dir(self):
        return self.storage_path / "archived"

    @property
    def monitoring_dir(self):
        return self.storage_path / "monitoring"

    @property
    def monitoring_storage_dir(self):
        return self.monitoring_dir

    @property
    def watch_folder_dir(self):
        return self.storage_path / "watch_folder"

    def ensure_storage_dirs(self) -> None:
        """Ensure all storage directories exist."""
        for d in [
            self.incoming_dir,
            self.originals_dir,
            self.failed_dir,
            self.fingerprints_dir,
            self.parsed_dir,
            self.ocr_dir,
            self.chunks_dir,
            self.extracted_dir,
            self.normalized_dir,
            self.validation_dir,
            self.verification_dir,
            self.verified_dir,
            self.archived_dir,
            self.monitoring_dir,
            self.watch_folder_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    @property
    def sync_database_url(self) -> str:
        """Construct SQLAlchemy synchronous PostgreSQL database connection URL."""
        if self.database_url:
            # Ensure proper psycopg driver prefix if user passed generic postgresql://
            if self.database_url.startswith("postgresql://"):
                return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
            return self.database_url

        user_auth = (
            f"{self.postgres_user}:{self.postgres_password}@"
            if self.postgres_password
            else f"{self.postgres_user}@"
        )
        return f"postgresql+psycopg://{user_auth}{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def cors_origins(self) -> List[str]:
        """Parse allowed origins for CORS middleware."""
        origins = [self.frontend_url.rstrip("/")]
        if self.app_env == "development":
            origins.extend([
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ])
        return list(dict.fromkeys(origins))


@lru_cache()
def get_settings() -> Settings:
    """Retrieve cached application settings instance."""
    return Settings()


settings = get_settings()

