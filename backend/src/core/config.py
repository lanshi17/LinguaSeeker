"""Configuration management middleware.

All settings are loaded from ``.env.local`` / ``.env`` / environment variables
via pydantic-settings.  Flat fields match env var names (case-insensitive);
nested domain models are constructed from those fields by a ``model_validator``.

Usage::

    from src.core.config import get_config

    cfg = get_config()              # singleton
    cfg.llm.api_key                 # preferred: nested access
    cfg.postgresql.host             # nested domain
    cfg.llm_api_key                 # also available as flat field
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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


class TranslationConfig(BaseModel):
    """Multi-language translation LLM."""

    api_key: str = ""
    base_url: str = ""
    model: str = ""


class VisionConfig(BaseModel):
    """Vision / image extraction LLM."""

    api_key: str = ""
    base_url: str = ""
    model: str = ""
    enable: bool = False


class ArbitrationConfig(BaseModel):
    """Expert arbitration agent (stronger reasoning model)."""

    api_key: str = ""
    model: str = ""
    reasoning_effort: str = "high"
    base_url: str = ""


class EmbeddingConfig(BaseModel):
    """Embedding model."""

    base_url: str = ""
    model: str = ""
    dimension: int = 1536
    batch_size: int = 10


class RerankConfig(BaseModel):
    """Rerank model."""

    base_url: str = ""
    model: str = ""
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
        env_file=(".env.local", ".env"),
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
    api_host: str = "localhost"
    api_port: int = 8000

    # ── LLM flat fields (LLM_*) ─────────────────────────────────────────

    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_temperature: float = 0.0
    llm_max_tokens: int = 2000
    llm_timeout: int = 60
    llm_max_retries: int = 3

    # ── Translation flat fields (MT_*) ───────────────────────────────────

    mt_api_key: str = ""
    mt_base_url: str = ""
    mt_model: str = ""

    # ── Vision flat fields (VLM_*) ───────────────────────────────────────

    vlm_api_key: str = ""
    vlm_base_url: str = ""
    vlm_model: str = ""
    vlm_enable: bool = False

    # ── Arbitration flat fields (ARBITRATION_*) ──────────────────────────

    arbitration_api_key: str = ""
    arbitration_model: str = ""
    arbitration_reasoning_effort: str = "high"
    arbitration_base_url: str = ""

    # ── Embedding flat fields (EMBEDDING_*) ──────────────────────────────

    embedding_base_url: str = ""
    embedding_model: str = ""
    embedding_dimension: int = 1536
    embedding_batch_size: int = 10

    # ── Rerank flat fields (RERANK_*) ────────────────────────────────────

    rerank_base_url: str = ""
    rerank_model: str = ""
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

    # ── Nested domain models (populated by validator) ────────────────────

    llm: LLMConfig = Field(default_factory=LLMConfig, exclude=True)
    translation: TranslationConfig = Field(default_factory=TranslationConfig, exclude=True)
    vision: VisionConfig = Field(default_factory=VisionConfig, exclude=True)
    arbitration: ArbitrationConfig = Field(default_factory=ArbitrationConfig, exclude=True)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig, exclude=True)
    rerank: RerankConfig = Field(default_factory=RerankConfig, exclude=True)
    mineru: MinerUConfig = Field(default_factory=MinerUConfig, exclude=True)
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
        self.llm = LLMConfig(
            api_key=self.llm_api_key,
            base_url=self.llm_base_url,
            model=self.llm_model,
            temperature=self.llm_temperature,
            max_tokens=self.llm_max_tokens,
            timeout=self.llm_timeout,
            max_retries=self.llm_max_retries,
        )
        self.translation = TranslationConfig(
            api_key=self.mt_api_key,
            base_url=self.mt_base_url,
            model=self.mt_model,
        )
        self.vision = VisionConfig(
            api_key=self.vlm_api_key,
            base_url=self.vlm_base_url,
            model=self.vlm_model,
            enable=self.vlm_enable,
        )
        self.arbitration = ArbitrationConfig(
            api_key=self.arbitration_api_key,
            model=self.arbitration_model,
            reasoning_effort=self.arbitration_reasoning_effort,
            base_url=self.arbitration_base_url,
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


# ── Singleton & FastAPI dependency ───────────────────────────────────────


@lru_cache(maxsize=1)
def get_config() -> Settings:
    """Return the global Settings singleton (created once, cached forever)."""
    return Settings()


def get_settings() -> Settings:
    """FastAPI dependency — inject via ``cfg: Settings = Depends(get_settings)``."""
    return get_config()
