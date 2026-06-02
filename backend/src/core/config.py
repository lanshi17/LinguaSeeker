"""Configuration management middleware.

All settings are loaded from ``.env.local`` / ``.env`` / environment variables
via pydantic-settings. Preferred env prefixes are ``FAST_LLM_*`` and
``REASONING_LLM_*``. Legacy ``LLM_*`` / ``REASONING_LLM_*`` variables remain
supported as fallbacks. Nested domain models are constructed from the resolved
flat fields by a ``model_validator``.

    from src.core.config import get_config

    cfg = get_config()              # singleton
    cfg.llm.api_key                 # preferred: nested access
    cfg.postgresql.host             # nested domain
    cfg.llm_api_key                 # also available as flat field
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ── Constants ───────────────────────────────────────────────────────────

PGVECTOR_DIMENSION: int = 1024
BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
DEFAULT_ENV_FILES = (
    str(REPO_ROOT / ".env"),
    str(REPO_ROOT / ".env.local"),
    str(BACKEND_ROOT / ".env"),
    str(BACKEND_ROOT / ".env.local"),
)


# ── Nested domain models ────────────────────────────────────────────────


class LLMConfig(BaseModel):
    """Generic LLM (OpenAI-compatible)."""

    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.0
    max_tokens: int = 2000
    timeout: int = 60
    max_retries: int = 3


class MultimodalLLMConfig(BaseModel):
    """Multimodal LLM (text + vision)."""

    enabled: bool = False
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class ReasoningConfig(BaseModel):
    """Expert reasoning agent (stronger reasoning model)."""

    api_key: str = ""
    model: str = ""
    reasoning_effort: str = "high"
    base_url: str = ""
    timeout: int = 60


class EmbeddingConfig(BaseModel):
    """Embedding model."""

    base_url: str = ""
    model: str = "Qwen/Qwen3-Embedding-0.6B"
    dimension: int = 1024
    batch_size: int = 10


class RerankConfig(BaseModel):
    """Rerank model."""

    base_url: str = ""
    model: str = "BAAI/bge-reranker-v2-m3"
    top_k: int = 10
    score_threshold: float = 0.7


class MinerUConfig(BaseModel):
    """MinerU document parsing service."""

    api_url: str = ""
    api_token: str = ""
    api_token_backup: str = ""
    version: str = "vlm"
    download_dir: str = "/tmp/mineru_downloads"
    timeout: int = 300
    max_file_size_mb: int = 100


class ParseDocumentConfig(BaseModel):
    """Parse document module configuration."""

    mineru_remote_api_token: str = ""
    mineru_remote_poll_interval: float = 2.0
    mineru_remote_max_poll_attempts: int = 150
    mineru_local_model_server_url: str = "http://localhost:8001"
    mineru_local_model_id: str = "opendatalab/MinerU2.5-Pro-2604-1.2B"
    mineru_local_timeout: float = 120.0
    mineru_local_dpi: int = 200


class EvidenceExtractionConfig(BaseModel):
    """Evidence extraction LLM settings."""

    api_key: str = ""
    base_url: str = ""
    fast_model: str = ""
    standard_model: str = ""
    strong_model: str = ""
    temperature: float = 0.0
    timeout: int = 60
    max_retries: int = 3


class RedisConfig(BaseModel):
    """Redis connection."""

    host: str = "localhost"
    port: int = 6379
    password: str = ""
    db: int = 0
    max_connections: int = 20


class PostgreSQLConfig(BaseModel):
    """PostgreSQL connection."""

    host: str = "127.0.0.1"
    port: int = 5432
    db: str = "acmg_ps3"
    schema_: str = "acmg_app"
    user: str = ""
    password: str = ""
    pool_size: int = 20
    max_overflow: int = 30
    pgvector_enabled: bool = True


class Neo4jConfig(BaseModel):
    """Neo4j graph database."""

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""
    database: str = "neo4j"
    max_connection_lifetime: int = 3600
    max_connection_pool_size: int = 50


class MinIOConfig(BaseModel):
    """MinIO object storage."""

    endpoint: str = "localhost:9000"
    access_key: str = ""
    secret_key: str = ""
    api: str = "s3v4"
    path: str = "auto"
    bucket_name: str = "acmg-bucket"
    secure: bool = False
    root_user: str = ""
    root_password: str = ""


class TaskConfig(BaseModel):
    """Task execution limits."""

    max_reasoning_iterations: int = 3
    task_timeout_seconds: int = 3600


class LiteratureConfig(BaseModel):
    """Literature retrieval."""

    pubmed_api_key: str = ""
    pubmed_base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    unpaywall_email: str = ""
    jstage_proxy: str = ""


class SMTPConfig(BaseModel):
    """SMTP email."""

    host: str = ""
    port: int = 465
    user: str = ""
    password: str = ""
    from_email: str = ""


# ── Root settings ────────────────────────────────────────────────────────


class Settings(BaseSettings):
    """Root configuration.  Loaded once from env / ``.env`` files.

    Flat ``llm_*`` / ``mt_*`` / … fields are populated automatically by
    pydantic-settings.  The nested domain models (``self.llm``, ``self.mt``, …)
    are constructed from those flat fields by ``_build_nested``.
    """

    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Top-level app config ─────────────────────────────────────────────

    app_name: str = "ACMG-Lingua"
    app_version: str = "3.0.0"
    api_prefix: str = "/api/v1"
    cors_origins: str = "*"
    environment: str = "development"
    debug: bool = False
    api_key: str = ""  # X-API-Key for write route auth; empty = disabled
    api_host: str = "localhost"
    api_port: int = 8000

    # ── Legacy LLM flat fields (LLM_*) ──────────────────────────────────

    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_temperature: float = 0.0
    llm_max_tokens: int = 2000
    llm_timeout: int = 60
    llm_max_retries: int = 3

    # ── Preferred fast LLM flat fields (FAST_LLM_*) ────────────────────

    fast_llm_api_key: str = ""
    fast_llm_base_url: str = ""
    fast_llm_model: str = ""
    fast_llm_temperature: float | None = None
    fast_llm_max_tokens: int = 0
    fast_llm_timeout: int = 0
    fast_llm_max_retries: int = 0

    # ── Multimodal LLM flat fields (MULTIMODAL_LLM_*) ────────────────────

    multimodal_llm_enabled: bool = False
    multimodal_llm_api_key: str = ""
    multimodal_llm_base_url: str = ""
    multimodal_llm_model: str = ""

    # ── Legacy reasoning flat fields (previously ARBITRATION_*) ────────

    reasoning_api_key: str = ""
    reasoning_model: str = ""
    reasoning_effort: str = "high"
    reasoning_base_url: str = ""

    # ── Preferred reasoning LLM flat fields (REASONING_LLM_*) ──────────

    reasoning_llm_api_key: str = ""
    reasoning_llm_model: str = ""
    reasoning_llm_reasoning_effort: str = ""
    reasoning_llm_base_url: str = ""
    reasoning_llm_temperature: float | None = None
    reasoning_llm_max_tokens: int = 0
    reasoning_llm_timeout: int = 0
    reasoning_llm_max_retries: int = 0

    # ── Embedding flat fields (EMBEDDING_*) ──────────────────────────────

    embedding_base_url: str = ""
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_dimension: int = 1024
    embedding_batch_size: int = 10

    # ── Rerank flat fields (RERANK_*) ────────────────────────────────────

    rerank_base_url: str = ""
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_top_k: int = 10
    rerank_score_threshold: float = 0.7

    # ── MinerU flat fields (MINERU_*) ────────────────────────────────────

    mineru_api_url: str = ""
    mineru_api_token: str = ""
    mineru_api_token_backup: str = ""
    mineru_version: str = "vlm"
    mineru_download_dir: str = "/tmp/mineru_downloads"
    mineru_timeout: int = 300
    mineru_max_file_size_mb: int = 100

    # ── Parse Document flat fields (MINERU_REMOTE_* / MINERU_LOCAL_*) ───

    mineru_remote_api_token: str = ""
    mineru_remote_poll_interval: float = 2.0
    mineru_remote_max_poll_attempts: int = 150
    mineru_local_model_server_url: str = "http://localhost:8001"
    mineru_local_model_id: str = "opendatalab/MinerU2.5-Pro-2604-1.2B"
    mineru_local_timeout: float = 120.0
    mineru_local_dpi: int = 200

    # ── Model Server flat fields (MODEL_SERVER_*) ─────────────────────

    model_server_url: str = "http://localhost:8001"

    # ── Redis flat fields (REDIS_*) ──────────────────────────────────────

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    redis_max_connections: int = 20

    # ── PostgreSQL flat fields (POSTGRES_*) ──────────────────────────────

    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "acmg_ps3"
    postgres_schema: str = "acmg_app"
    postgres_user: str = ""
    postgres_password: str = ""
    postgres_pool_size: int = 20
    postgres_max_overflow: int = 30
    pgvector_enabled: bool = True

    # ── Neo4j flat fields (NEO4J_*) ──────────────────────────────────────

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"
    neo4j_max_connection_lifetime: int = 3600
    neo4j_max_connection_pool_size: int = 50

    # ── MinIO flat fields (MINIO_*) ──────────────────────────────────────

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_api: str = "s3v4"
    minio_path: str = "auto"
    minio_bucket_name: str = "acmg-bucket"
    minio_secure: bool = False
    minio_root_user: str = ""
    minio_root_password: str = ""

    # ── Task flat fields ─────────────────────────────────────────────────

    max_reasoning_iterations: int = 3
    task_timeout_seconds: int = 3600

    # ── Literature flat fields ───────────────────────────────────────────

    pubmed_api_key: str = ""
    pubmed_base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    unpaywall_email: str = ""
    jstage_proxy: str = ""

    # ── SMTP flat fields (SMTP_*) ────────────────────────────────────────

    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""

    # ── Cross-lingual output ─────────────────────────────────────────────

    cross_lingual_output_dir: str = "data/cross_lingual_output"

    # ── Evidence Extraction flat fields (EVIDENCE_EXTRACTION_*) ──────────

    evidence_extraction_api_key: str = ""
    evidence_extraction_base_url: str = ""
    evidence_extraction_fast_model: str = ""
    evidence_extraction_standard_model: str = ""
    evidence_extraction_strong_model: str = ""
    evidence_extraction_temperature: float = 0.0
    evidence_extraction_timeout: int = 60
    evidence_extraction_max_retries: int = 3

    # ── Nested domain models (populated by validator) ────────────────────

    llm: LLMConfig = Field(default_factory=LLMConfig, exclude=True)
    multimodal_llm: MultimodalLLMConfig = Field(default_factory=MultimodalLLMConfig, exclude=True)
    reasoning: ReasoningConfig = Field(default_factory=ReasoningConfig, exclude=True)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig, exclude=True)
    rerank: RerankConfig = Field(default_factory=RerankConfig, exclude=True)
    mineru: MinerUConfig = Field(default_factory=MinerUConfig, exclude=True)
    parse_document: ParseDocumentConfig = Field(default_factory=ParseDocumentConfig, exclude=True)
    evidence_extraction: EvidenceExtractionConfig = Field(
        default_factory=EvidenceExtractionConfig, exclude=True,
    )
    redis: RedisConfig = Field(default_factory=RedisConfig, exclude=True)
    postgresql: PostgreSQLConfig = Field(default_factory=PostgreSQLConfig, exclude=True)
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig, exclude=True)
    minio: MinIOConfig = Field(default_factory=MinIOConfig, exclude=True)
    task: TaskConfig = Field(default_factory=TaskConfig, exclude=True)
    literature: LiteratureConfig = Field(default_factory=LiteratureConfig, exclude=True)
    smtp: SMTPConfig = Field(default_factory=SMTPConfig, exclude=True)

    # ── Build nested models from flat fields ─────────────────────────────

    @model_validator(mode="after")
    def _build_nested(self) -> Settings:
        """Construct nested domain models from the flat env-var fields."""
        if self.embedding_dimension != PGVECTOR_DIMENSION:
            raise ValueError(
                f"EMBEDDING_DIMENSION={self.embedding_dimension} does not match "
                f"pgvector column dimension {PGVECTOR_DIMENSION}. "
                f"Set EMBEDDING_DIMENSION={PGVECTOR_DIMENSION} or update the migration."
            )
        fast_api_key = self.fast_llm_api_key or self.llm_api_key
        fast_base_url = self.fast_llm_base_url or self.llm_base_url
        fast_model = self.fast_llm_model or self.llm_model
        fast_temperature = self.fast_llm_temperature if self.fast_llm_temperature is not None else self.llm_temperature
        fast_max_tokens = self.fast_llm_max_tokens or self.llm_max_tokens
        fast_timeout = self.fast_llm_timeout or self.llm_timeout
        fast_max_retries = self.fast_llm_max_retries or self.llm_max_retries

        reasoning_api_key = self.reasoning_llm_api_key or self.reasoning_api_key
        reasoning_model = self.reasoning_llm_model or self.reasoning_model
        reasoning_effort = self.reasoning_llm_reasoning_effort or self.reasoning_effort
        reasoning_base_url = self.reasoning_llm_base_url or self.reasoning_base_url

        self.llm = LLMConfig(
            api_key=fast_api_key,
            base_url=fast_base_url,
            model=fast_model,
            temperature=fast_temperature,
            max_tokens=fast_max_tokens,
            timeout=fast_timeout,
            max_retries=fast_max_retries,
        )
        self.multimodal_llm = MultimodalLLMConfig(
            enabled=self.multimodal_llm_enabled,
            api_key=self.multimodal_llm_api_key,
            base_url=self.multimodal_llm_base_url,
            model=self.multimodal_llm_model,
        )
        self.reasoning = ReasoningConfig(
            api_key=reasoning_api_key,
            model=reasoning_model,
            reasoning_effort=reasoning_effort,
            base_url=reasoning_base_url,
            timeout=self.reasoning_llm_timeout or 60,
        )
        self.embedding = EmbeddingConfig(
            base_url=self.embedding_base_url,
            model=self.embedding_model,
            dimension=self.embedding_dimension,
            batch_size=self.embedding_batch_size,
        )
        self.rerank = RerankConfig(
            base_url=self.rerank_base_url,
            model=self.rerank_model,
            top_k=self.rerank_top_k,
            score_threshold=self.rerank_score_threshold,
        )
        self.mineru = MinerUConfig(
            api_url=self.mineru_api_url,
            api_token=self.mineru_api_token,
            api_token_backup=self.mineru_api_token_backup,
            version=self.mineru_version,
            download_dir=self.mineru_download_dir,
            timeout=self.mineru_timeout,
            max_file_size_mb=self.mineru_max_file_size_mb,
        )
        self.parse_document = ParseDocumentConfig(
            mineru_remote_api_token=self.mineru_remote_api_token,
            mineru_remote_poll_interval=self.mineru_remote_poll_interval,
            mineru_remote_max_poll_attempts=self.mineru_remote_max_poll_attempts,
            mineru_local_model_server_url=self.mineru_local_model_server_url,
            mineru_local_model_id=self.mineru_local_model_id,
            mineru_local_timeout=self.mineru_local_timeout,
            mineru_local_dpi=self.mineru_local_dpi,
        )
        self.evidence_extraction = EvidenceExtractionConfig(
            api_key=self.evidence_extraction_api_key,
            base_url=self.evidence_extraction_base_url,
            fast_model=self.evidence_extraction_fast_model,
            standard_model=self.evidence_extraction_standard_model,
            strong_model=self.evidence_extraction_strong_model,
            temperature=self.evidence_extraction_temperature,
            timeout=self.evidence_extraction_timeout,
            max_retries=self.evidence_extraction_max_retries,
        )
        self.redis = RedisConfig(
            host=self.redis_host,
            port=self.redis_port,
            password=self.redis_password,
            db=self.redis_db,
            max_connections=self.redis_max_connections,
        )
        self.postgresql = PostgreSQLConfig(
            host=self.postgres_host,
            port=self.postgres_port,
            db=self.postgres_db,
            schema_=self.postgres_schema,
            user=self.postgres_user,
            password=self.postgres_password,
            pool_size=self.postgres_pool_size,
            max_overflow=self.postgres_max_overflow,
            pgvector_enabled=self.pgvector_enabled,
        )
        self.neo4j = Neo4jConfig(
            uri=self.neo4j_uri,
            user=self.neo4j_user,
            password=self.neo4j_password,
            database=self.neo4j_database,
            max_connection_lifetime=self.neo4j_max_connection_lifetime,
            max_connection_pool_size=self.neo4j_max_connection_pool_size,
        )
        self.minio = MinIOConfig(
            endpoint=self.minio_endpoint,
            access_key=self.minio_access_key,
            secret_key=self.minio_secret_key,
            api=self.minio_api,
            path=self.minio_path,
            bucket_name=self.minio_bucket_name,
            secure=self.minio_secure,
            root_user=self.minio_root_user,
            root_password=self.minio_root_password,
        )
        self.task = TaskConfig(
            max_reasoning_iterations=self.max_reasoning_iterations,
            task_timeout_seconds=self.task_timeout_seconds,
        )
        self.literature = LiteratureConfig(
            pubmed_api_key=self.pubmed_api_key,
            pubmed_base_url=self.pubmed_base_url,
            unpaywall_email=self.unpaywall_email,
            jstage_proxy=self.jstage_proxy,
        )
        self.smtp = SMTPConfig(
            host=self.smtp_host,
            port=self.smtp_port,
            user=self.smtp_user,
            password=self.smtp_password,
            from_email=self.smtp_from_email,
        )
        return self

    # ── Derived helpers ──────────────────────────────────────────────────

    @property
    def cors_origins_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    @property
    def postgresql_dsn(self) -> str:
        """Return the async SQLAlchemy PostgreSQL DSN."""
        userinfo = ""
        if self.postgresql.user:
            userinfo = quote(self.postgresql.user, safe="")
            if self.postgresql.password:
                userinfo = f"{userinfo}:{quote(self.postgresql.password, safe='')}"
            userinfo = f"{userinfo}@"

        database = quote(self.postgresql.db, safe="")
        return f"postgresql+asyncpg://{userinfo}{self.postgresql.host}:{self.postgresql.port}/{database}"


# ── Singleton & FastAPI dependency ───────────────────────────────────────


@lru_cache(maxsize=1)
def get_config() -> Settings:
    """Return the global Settings singleton (created once, cached forever)."""
    return Settings()


def get_settings() -> Settings:
    """FastAPI dependency — inject via ``cfg: Settings = Depends(get_settings)``."""
    return get_config()
