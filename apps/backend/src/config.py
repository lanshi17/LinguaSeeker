# config.py
from dataclasses import dataclass
from typing import List, Literal, Optional

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ==================== LLM Triplet Resolver ====================

LLMRole = Literal[
    "retrieval", "parsing", "mt", "format", "vlm", "evidence", "classification", "arbitration"
]


@dataclass(frozen=True)
class LLMTriplet:
    """Immutable LLM configuration triplet (api_key, base_url, model)."""

    api_key: str
    base_url: str
    model: str


class Settings(BaseSettings):
    # ==================== 应用配置 ====================
    app_name: str = "ACMG-PS3 Intelligence System"
    app_version: str = "2.1.0"
    api_prefix: str = "/api/v1"
    cors_origins: str = '["http://localhost:3000", "http://localhost:8080"]'
    environment: str = "development"  # development | staging | production
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    clear_proxy_env_on_startup: bool = False

    # ==================== LLM配置 ====================

    # 文献获取智能体
    retrieval_api_key: str
    retrieval_base_url: str
    retrieval_model: str

    # 文档解析智能体
    parsing_api_key: str
    parsing_base_url: str
    parsing_model: str

    # 多语种翻译智能体
    mt_api_key: str
    mt_base_url: str
    mt_model: str

    # 多功能排版智能体
    format_api_key: str
    format_base_url: str
    format_model: str

    # 图片提取智能体
    vlm_api_key: str
    vlm_base_url: str
    vlm_model: str
    vlm_enable: bool = False
    vlm_max_batch_images: int = 10

    # 证据提取智能体
    evidence_api_key: str
    evidence_base_url: str
    evidence_model: str

    # ACMG分类智能体
    classification_api_key: str
    classification_base_url: str
    classification_model: str

    # 专家裁决智能体
    arbitration_api_key: str
    arbitration_model: str
    arbitration_base_url: str

    llm_temperature: float = 0.7
    llm_max_tokens: int = 2000
    llm_timeout: int = 60
    llm_max_retries: int = 3
    llm_mode: str = "api"

    # ==================== 证据分类配置 ====================
    evidence_validity_threshold: float = 85.0  # 证据有效性阈值
    evidence_review_floor: float = 60.0  # 低置信度进入人工复核的默认阈值
    evidence_retry_limit: int = 1  # 针对解析失败的自动重试次数
    evidence_retry_delay_seconds: int = 600  # 解析失败重试的延迟
    evidence_failure_alert_threshold: int = 5  # 同一字段失败多少次后告警
    evidence_failure_archive_path: str = "logs/evidence_failure_archive.jsonl"

    # ==================== Rerank 配置 ====================
    rerank_api_key: Optional[str] = None
    rerank_base_url: Optional[str] = None
    rerank_model: Optional[str] = None
    rerank_top_k: int = 10
    rerank_score_threshold: float = 0.7

    # ==================== MinerU 配置 ====================
    mineru_mode: str = "api"  # api | local
    mineru_api_url: str = "http://localhost:8080"
    mineru_api_token: Optional[str] = None
    mineru_version: Optional[str] = None
    mineru_download_dir: Optional[str] = None
    mineru_timeout: int = 300
    mineru_max_file_size_mb: int = 100

    # ==================== Redis配置 ====================
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: Optional[str] = None
    redis_db: int = 0
    redis_max_connections: int = 20
    interaction_session_ttl_seconds: int = 3600

    # ==================== PostgreSQL配置 ====================
    postgres_host: str = Field(
        default="localhost", validation_alias=AliasChoices("POSTGRES_HOST", "PGHOST")
    )
    postgres_port: int = Field(5432, validation_alias=AliasChoices("POSTGRES_PORT", "PGPORT"))
    postgres_db: str = Field(
        default="acmg_ps3", validation_alias=AliasChoices("POSTGRES_DB", "PGDATABASE")
    )
    postgres_user: str = Field(
        default="postgres", validation_alias=AliasChoices("POSTGRES_USER", "PGUSER")
    )
    postgres_password: str = Field(validation_alias=AliasChoices("POSTGRES_PASSWORD", "PGPASSWORD"))
    postgres_pool_size: int = 10
    postgres_max_overflow: int = 20

    # ==================== Neo4j配置 ====================
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str
    neo4j_database: str = "neo4j"
    neo4j_max_connection_lifetime: int = 3600
    neo4j_max_connection_pool_size: int = 50

    # ==================== 向量数据库选择 ====================
    vector_db: str = "qdrant"  # qdrant | milvus
    knowledge_docs_dir: str = "./knowledge_docs"

    # ==================== Embedding配置 ====================
    embedding_provider: str = "nomic"  # nomic | openai
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "nomic-embed-text"
    embedding_dimension: int = 1536
    embedding_batch_size: int = 32

    # ==================== Qdrant配置 ====================
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_https: bool = False
    qdrant_verify_ssl: bool = True
    qdrant_collection_name: str = "paper_chunks"
    qdrant_api_key: Optional[str] = None
    qdrant_dimension: int = 1536
    qdrant_prefer_grpc: bool = True
    qdrant_top_k: int = 5
    qdrant_score_threshold: float = 0.7
    qdrant_max_retries: int = 3
    qdrant_retry_delay: float = 1.0

    # ==================== Milvus配置 ====================
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection_name: str = "paper_chunks"
    milvus_dimension: int = 1536
    milvus_index_type: str = "IVF_FLAT"
    milvus_metric_type: str = "L2"

    # ==================== MinIO配置 ====================
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str
    minio_secret_key: str
    minio_bucket_name: str = "processed-results"
    minio_uploads_bucket: str = "literature-uploads"
    minio_results_bucket: str = "processed-results"
    minio_secure: bool = False  # 根据.env.example，默认为false

    @field_validator("minio_access_key", "minio_secret_key")
    @classmethod
    def validate_minio_credentials(cls, v: str, info) -> str:
        """Reject placeholder MinIO credentials to prevent misconfiguration."""
        if not v:
            raise ValueError(f"{info.field_name} is required for MinIO connection")

        # List of known placeholder values
        placeholders = [
            "your-minio-access-key",
            "your-minio-secret-key",
            "minio-access-key",
            "minio-secret-key",
            "change-me",
            "changeme",
        ]

        if v.lower() in placeholders:
            raise ValueError(
                f"Placeholder value detected for MinIO credential '{info.field_name}'. "
                f"Please set a valid MinIO credential in your environment configuration."
            )

        return v

    # ==================== 任务配置 ====================
    max_reasoning_iterations: int = 3
    task_timeout_seconds: int = 3600
    node_acquisition_max_retries: int = 2
    node_acquisition_delay_seconds: int = 300
    node_acquisition_timeout_seconds: int = 900
    node_parsing_max_retries: int = 1
    node_parsing_delay_seconds: int = 600
    node_parsing_timeout_seconds: int = 1800
    node_translation_max_retries: int = 2
    node_translation_delay_seconds: int = 120
    node_translation_timeout_seconds: int = 1200
    node_extraction_max_retries: int = 2
    node_extraction_delay_seconds: int = 300
    node_extraction_timeout_seconds: int = 1800
    node_acmg_max_retries: int = 1
    node_acmg_delay_seconds: int = 180
    node_acmg_timeout_seconds: int = 900
    use_agent_workflow_pdf: bool = False
    use_agent_workflow_pubmed: bool = False
    use_agent_workflow_web: bool = False
    agent_workflow_interrupt_before_human_review: bool = False

    def use_agent_workflow(self, task_type: str) -> bool:
        return getattr(self, f"use_agent_workflow_{task_type.lower()}", False)

    # ==================== 爬取配置 ====================
    pubmed_api_key: Optional[str] = None
    pubmed_base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    firecrawl_base_url: str = "https://api.firecrawl.dev/v0"
    firecrawl_api_key: Optional[str] = None

    # ==================== 邮箱配置 ====================
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""

    # 额外示例：列表类型
    allowed_hosts: List[str] = ["localhost"]

    # 使用 SettingsConfigDict (Pydantic V2)
    model_config = SettingsConfigDict(
        env_file=[".env.local"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


def resolve_llm_triplet(settings: Settings, role: LLMRole) -> LLMTriplet:
    """Resolve LLM configuration triplet for a given role.

    Args:
        settings: Settings instance containing LLM configurations
        role: LLM role name (retrieval/parsing/mt/format/vlm/evidence/classification/arbitration)

    Returns:
        LLMTriplet containing (api_key, base_url, model) for the role

    Raises:
        ValueError: If role is invalid
    """
    valid_roles: set[str] = {
        "retrieval",
        "parsing",
        "mt",
        "format",
        "vlm",
        "evidence",
        "classification",
        "arbitration",
    }

    if role not in valid_roles:
        raise ValueError(f"Invalid LLM role: {role}. Valid roles: {', '.join(sorted(valid_roles))}")

    return LLMTriplet(
        api_key=getattr(settings, f"{role}_api_key"),
        base_url=getattr(settings, f"{role}_base_url"),
        model=getattr(settings, f"{role}_model"),
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    """
    Get or create the Settings instance.

    Settings are loaded from environment variables (via pydantic-settings).
    This factory pattern allows basedpyright to typecheck cleanly while
    deferring instantiation until first use.
    """
    global _settings
    if _settings is None:
        _settings = Settings()  # pyright: ignore[reportCallIssue]
    return _settings


# For backward compatibility, expose a module-level settings variable
# that is lazily evaluated via __getattr__
def __getattr__(name: str):
    if name == "settings":
        return get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
