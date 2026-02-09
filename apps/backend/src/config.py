# config.py
from typing import List, Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # ==================== 应用配置 ====================
    app_name: str
    app_version: str
    api_prefix: str
    cors_origins: str
    environment: str
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ==================== LLM配置 ====================
    generic_api_key: str
    generic_base_url: str
    
    evidence_api_key: str
    evidence_base_url: str
    evidence_model: str

    arbitration_api_key: str
    arbitration_model: str
    arbitration_base_url: str

    llm_temperature: float = 0.0
    llm_max_tokens: int = 2000
    llm_timeout: int = 60
    llm_max_retries: int = 3
    llm_mode: str = "api"

    # ==================== Embedding配置 ====================
    embedding_provider: str
    embedding_base_url: str
    embedding_api_key: str
    embedding_model: str
    embedding_dimension: int
    embedding_batch_size: int = 10
    
    # ==================== Rerank 配置 ====================
    rerank_api_key: Optional[str] = None
    rerank_base_url: Optional[str] = None
    rerank_model: Optional[str] = None
    rerank_top_k: int = 10
    rerank_score_threshold: float = 0.7

    # ==================== MinerU 配置 ====================
    mineru_mode: str
    mineru_api_url: str
    mineru_api_token: str
    mineru_version: str
    mineru_download_dir: str
    mineru_timeout: int = 300
    mineru_max_file_size_mb: int = 100

    # ==================== Redis配置 ====================
    redis_host: str
    redis_port: int = 6379
    redis_password: Optional[str] = None
    redis_db: int = 0
    redis_max_connections: int = 20

    # ==================== PostgreSQL配置 ====================
    postgres_host: str = Field(validation_alias=AliasChoices("POSTGRES_HOST", "PGHOST"))
    postgres_port: int = Field(5432, validation_alias=AliasChoices("POSTGRES_PORT", "PGPORT"))
    postgres_db: str = Field(validation_alias=AliasChoices("POSTGRES_DB", "PGDATABASE"))
    postgres_user: str = Field(validation_alias=AliasChoices("POSTGRES_USER", "PGUSER"))
    postgres_password: str = Field(validation_alias=AliasChoices("POSTGRES_PASSWORD", "PGPASSWORD"))
    postgres_pool_size: int = 20
    postgres_max_overflow: int = 30

    # ==================== Neo4j配置 ====================
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str
    neo4j_max_connection_lifetime: int = 3600
    neo4j_max_connection_pool_size: int = 50

    # ==================== 向量数据库选择 ====================
    vector_db: str
    knowledge_docs_dir: str

    # ==================== Qdrant配置 ====================
    qdrant_host: str
    qdrant_port: int = 6333
    qdrant_https: bool = False
    qdrant_verify_ssl: bool = True
    qdrant_collection_name: str
    qdrant_api_key: Optional[str] = None
    qdrant_dimension: int
    qdrant_prefer_grpc: bool = True
    qdrant_top_k: int = 5
    qdrant_score_threshold: float = 0.7
    qdrant_max_retries: int = 3
    qdrant_retry_delay: float = 1.0

    # ==================== Milvus配置 ====================
    milvus_host: str
    milvus_port: int
    milvus_collection_name: str
    milvus_dimension: int
    milvus_index_type: str
    milvus_metric_type: str

    # ==================== MinIO配置 ====================
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_api: str
    minio_path: str
    minio_bucket_name: str = "processed-results"
    minio_uploads_bucket: str = "literature-uploads"
    minio_results_bucket: str = "processed-results"
    minio_secure: bool = True
    minio_root_user: str
    minio_root_password: str

    # ==================== 任务配置 ====================
    max_reasoning_iterations: int = 3
    task_timeout_seconds: int = 3600

    # ==================== 爬取配置 ====================
    pubmed_api_key: Optional[str] = None
    pubmed_base_url: str
    firecrawl_base_url: str
    firecrawl_api_key: Optional[str] = None

    # 额外示例：列表类型
    allowed_hosts: List[str] = ["localhost"]

    # 使用 SettingsConfigDict (Pydantic V2)
    model_config = SettingsConfigDict(
        env_file=[".env.local"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        # 严格模式，要求所有字段都有值或默认值
        # extra='forbid'
    )

# Ensure all required environment variables are set in .env.local before instantiating Settings
settings = Settings()  # type: ignore[call-arg]
