"""Configuration management middleware.

Settings are loaded from layered YAML config first, then overridden by
environment variables. Nested domain models are constructed from flat fields
by a ``model_validator``.

    from src.core.config import get_config

    cfg = get_config()              # singleton
    cfg.llm.api_key                 # nested access (preferred)
    cfg.llm.model                   # "mimo-v2.5"
    cfg.reasoning.model             # "mimo-v2.5-pro"
    cfg.mineru.api_token            # MinerU API token
    cfg.postgresql.host             # PostgreSQL host

All configuration uses nested domain models. Flat fields are internal
implementation details populated by Pydantic Settings from YAML/env vars.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlparse

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from src.core.config_loader import load_backend_config_into_env


# ── Constants ───────────────────────────────────────────────────────────

PGVECTOR_DIMENSION: int = 1024
BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


# Load YAML config on module import (before Settings instantiation)
load_backend_config_into_env(BACKEND_ROOT)


# ── Nested domain models ────────────────────────────────────────────────


class LLMConfig(BaseModel):
    """Generic LLM (OpenAI-compatible)."""

    api_key: str = ""
    api_keys: list[str] = Field(default_factory=list)
    base_url: str = ""
    model: str = ""
    max_tokens: int = 8192
    timeout: int = 60
    temperature: float | None = None
    max_retries: int = 0

    @property
    def all_api_keys(self) -> list[str]:
        """Return all available API keys (deduplicated, preserving order)."""
        seen: set[str] = set()
        keys: list[str] = []
        for k in [*self.api_keys, self.api_key]:
            k = k.strip()
            if k and k not in seen:
                seen.add(k)
                keys.append(k)
        return keys


class ReasoningConfig(BaseModel):
    """Expert reasoning agent (stronger reasoning model)."""

    api_key: str = ""
    api_keys: list[str] = Field(default_factory=list)
    model: str = ""
    reasoning_effort: str = "high"
    base_url: str = ""
    max_tokens: int = 8192
    timeout: int = 60
    temperature: float | None = None
    max_retries: int = 0

    @property
    def all_api_keys(self) -> list[str]:
        """Return all available API keys (deduplicated, preserving order)."""
        seen: set[str] = set()
        keys: list[str] = []
        for k in [*self.api_keys, self.api_key]:
            k = k.strip()
            if k and k not in seen:
                seen.add(k)
                keys.append(k)
        return keys


class ChatLLMConfig(BaseModel):
    """Dedicated chat interaction LLM (lightweight, conversational)."""

    api_key: str = ""
    api_keys: list[str] = Field(default_factory=list)
    base_url: str = ""
    model: str = ""
    max_tokens: int = 4096
    timeout: int = 30
    temperature: float | None = 0.7
    max_retries: int = 0

    @property
    def all_api_keys(self) -> list[str]:
        """Return all available API keys (deduplicated, preserving order)."""
        seen: set[str] = set()
        keys: list[str] = []
        for k in [*self.api_keys, self.api_key]:
            k = k.strip()
            if k and k not in seen:
                seen.add(k)
                keys.append(k)
        return keys


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

    max_file_size_mb: int = 100


class ParseDocumentConfig(BaseModel):
    """Parse document module configuration."""

    mineru_remote_poll_interval: float = 2.0
    mineru_remote_max_poll_attempts: int = 150
    mineru_local_model_server_url: str = "http://localhost:8001"
    mineru_local_model_id: str = "opendatalab/MinerU2.5-Pro-2604-1.2B"
    mineru_local_timeout: float = 120.0
    mineru_local_dpi: int = 200


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
    db: str = "cross_evidence"
    schema_: str = "acmg_app"
    user: str = ""
    password: str = ""
    pool_size: int = 20
    max_overflow: int = 30


class WebSearchConfig(BaseModel):
    """Web search provider configuration (adapter-based, currently Firecrawl)."""

    api_key: str = ""
    base_url: str = "https://api.firecrawl.dev"
    timeout: int = 30
    max_results: int = 10


# Domains that bypass the proxy and connect directly.
# "cn" matches all *.cn and *.com.cn / *.ac.cn / *.edu.cn / etc.
_DEFAULT_NO_PROXY = (
    "cn,"
    "ncbi.nlm.nih.gov,"
    "nlm.nih.gov,"
    "unpaywall.org,"
    "localhost,"
    "127.0.0.1"
)


class NetworkConfig(BaseModel):
    """Outbound HTTP proxy with per-domain bypass.

    ``proxy`` is the proxy URL for international sites (e.g.
    ``http://127.0.0.1:7890`` or ``socks5://127.0.0.1:7891``).

    ``no_proxy`` is a comma-separated list of domain suffixes that should
    bypass the proxy and connect directly (mainland China sites).
    """

    proxy: str = ""
    no_proxy: str = _DEFAULT_NO_PROXY

    def resolve_proxy_for_url(self, url: str) -> str | None:
        """Return the proxy URL to use for *url*, or ``None`` for direct."""
        if not self.proxy:
            return None
        hostname = urlparse(url).hostname or ""
        if not hostname:
            return None
        for domain in self.no_proxy.split(","):
            domain = domain.strip().lower()
            if not domain:
                continue
            if hostname == domain or hostname.endswith("." + domain):
                return None
        return self.proxy


# ── Root settings ────────────────────────────────────────────────────────


class Settings(BaseSettings):
    """Root configuration.  Loaded once from layered YAML config and env vars.

    Flat ``llm_*`` / ``mt_*`` / … fields are populated automatically by
    pydantic-settings.  The nested domain models (``self.llm``, ``self.mt``, …)
    are constructed from those flat fields by ``_build_nested``.
    """

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    # ── Top-level app config ─────────────────────────────────────────────

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    environment: str = "development"
    debug: bool = False
    api_key: str = ""  # X-API-Key for route auth; empty = disabled (insecure)

    # ── Preferred fast LLM flat fields (FAST_LLM_*) ────────────────────

    fast_llm_api_key: str = ""
    fast_llm_api_keys: list[str] = Field(default_factory=list)
    fast_llm_base_url: str = ""
    fast_llm_model: str = ""
    fast_llm_temperature: float | None = None
    fast_llm_max_tokens: int = 8192
    fast_llm_timeout: int = 0
    fast_llm_max_retries: int = 0


    # ── Preferred reasoning LLM flat fields (REASONING_LLM_*) ──────────

    reasoning_llm_api_key: str = ""
    reasoning_llm_api_keys: list[str] = Field(default_factory=list)
    reasoning_llm_model: str = ""
    reasoning_llm_reasoning_effort: str = ""
    reasoning_llm_base_url: str = ""
    reasoning_llm_temperature: float | None = None
    reasoning_llm_max_tokens: int = 8192
    reasoning_llm_timeout: int = 0
    reasoning_llm_max_retries: int = 0

    # ── Chat interaction LLM flat fields (CHAT_LLM_*) ──────────────────

    chat_llm_api_key: str = ""
    chat_llm_api_keys: list[str] = Field(default_factory=list)
    chat_llm_model: str = ""
    chat_llm_base_url: str = ""
    chat_llm_temperature: float | None = None
    chat_llm_max_tokens: int = 4096
    chat_llm_timeout: int = 0
    chat_llm_max_retries: int = 0


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

    mineru_api_token: str = ""
    mineru_max_file_size_mb: int = 100

    # ── Parse Document flat fields (MINERU_REMOTE_* / MINERU_LOCAL_*) ───

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
    postgres_db: str = "cross_evidence"
    postgres_schema: str = "acmg_app"
    postgres_user: str = ""
    postgres_password: str = ""
    postgres_pool_size: int = 20
    postgres_max_overflow: int = 30
    pgvector_enabled: bool = True


    # ── Web Search flat fields (WEB_SEARCH_*) ───────────────────────────

    WEB_SEARCH_API_KEY: str = ""
    WEB_SEARCH_BASE_URL: str = "https://api.firecrawl.dev"
    WEB_SEARCH_TIMEOUT: int = 30
    WEB_SEARCH_MAX_RESULTS: int = 10


    # ── Network / proxy flat fields (NETWORK_*) ─────────────────────────

    network_proxy: str = ""
    network_no_proxy: str = _DEFAULT_NO_PROXY


    # ── Nested domain models (populated by validator) ────────────────────

    llm: LLMConfig = Field(default_factory=LLMConfig, exclude=True)
    reasoning: ReasoningConfig = Field(default_factory=ReasoningConfig, exclude=True)
    chat: ChatLLMConfig = Field(default_factory=ChatLLMConfig, exclude=True)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig, exclude=True)
    rerank: RerankConfig = Field(default_factory=RerankConfig, exclude=True)
    mineru: MinerUConfig = Field(default_factory=MinerUConfig, exclude=True)
    parse_document: ParseDocumentConfig = Field(default_factory=ParseDocumentConfig, exclude=True)
    redis: RedisConfig = Field(default_factory=RedisConfig, exclude=True)
    postgresql: PostgreSQLConfig = Field(default_factory=PostgreSQLConfig, exclude=True)
    web_search: WebSearchConfig = Field(default_factory=WebSearchConfig, exclude=True)
    network: NetworkConfig = Field(default_factory=NetworkConfig, exclude=True)

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
        
        self.llm = LLMConfig(
            api_key=self.fast_llm_api_key,
            api_keys=self.fast_llm_api_keys,
            base_url=self.fast_llm_base_url,
            model=self.fast_llm_model,
            max_tokens=self.fast_llm_max_tokens,
            timeout=self.fast_llm_timeout,
            temperature=self.fast_llm_temperature,
            max_retries=self.fast_llm_max_retries,
        )
        self.reasoning = ReasoningConfig(
            api_key=self.reasoning_llm_api_key,
            api_keys=self.reasoning_llm_api_keys,
            model=self.reasoning_llm_model,
            reasoning_effort=self.reasoning_llm_reasoning_effort,
            base_url=self.reasoning_llm_base_url,
            max_tokens=self.reasoning_llm_max_tokens,
            timeout=self.reasoning_llm_timeout,
            temperature=self.reasoning_llm_temperature,
            max_retries=self.reasoning_llm_max_retries,
        )
        self.chat = ChatLLMConfig(
            api_key=self.chat_llm_api_key,
            api_keys=self.chat_llm_api_keys,
            base_url=self.chat_llm_base_url,
            model=self.chat_llm_model,
            max_tokens=self.chat_llm_max_tokens,
            timeout=self.chat_llm_timeout,
            temperature=self.chat_llm_temperature,
            max_retries=self.chat_llm_max_retries,
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
            max_file_size_mb=self.mineru_max_file_size_mb,
        )
        self.parse_document = ParseDocumentConfig(
            mineru_remote_poll_interval=self.mineru_remote_poll_interval,
            mineru_remote_max_poll_attempts=self.mineru_remote_max_poll_attempts,
            mineru_local_model_server_url=self.mineru_local_model_server_url,
            mineru_local_model_id=self.mineru_local_model_id,
            mineru_local_timeout=self.mineru_local_timeout,
            mineru_local_dpi=self.mineru_local_dpi,
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
        )
        self.web_search = WebSearchConfig(
            api_key=self.WEB_SEARCH_API_KEY,
            base_url=self.WEB_SEARCH_BASE_URL,
            timeout=self.WEB_SEARCH_TIMEOUT,
            max_results=self.WEB_SEARCH_MAX_RESULTS,
        )
        self.network = NetworkConfig(
            proxy=self.network_proxy,
            no_proxy=self.network_no_proxy,
        )

        if self.is_production and not self.api_key.strip():
            raise ValueError("API_KEY must be set when ENVIRONMENT=production")

        if self.is_production and not self.redis.password.strip():
            raise ValueError("REDIS_PASSWORD must be set when ENVIRONMENT=production")

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
