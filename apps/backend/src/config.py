"""主配置文件 - 整合所有配置项"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class VectorBackend(str, Enum):
    """向量数据库后端选择"""

    QDRANT = "qdrant"
    MILVUS = "milvus"


@dataclass
class LLMConfig:
    """大语言模型配置"""

    # OCR-LLM
    ocr_provider: str = "qwen"
    ocr_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ocr_api_key: Optional[str] = None
    ocr_model: str = "qwen-vl-ocr-latest"
    ocr_batch_size: int = (
        1  # Number of pages to process in one API call (1 = single page for accuracy)
    )

    # MT-LLM
    mt_api_key: Optional[str] = None
    mt_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    mt_model: str = "qwen-mt-plus"

    # 主力LLM - DeepSeek-V3.2
    primary_provider: str = "deepseek"
    deepseek_api_key: Optional[str] = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # 仲裁LLM - Claude
    arbiter_provider: str = "claude"
    claude_api_key: Optional[str] = None
    anthropic_base_url: str = "https://api.anthropic.com"
    claude_model: str = "claude-3-5-sonnet-20241022"  # 或 claude-opus-4.5

    # 通用配置
    temperature: float = 0
    max_tokens: int = 2000
    timeout: int = 60
    max_retries: int = 3

    # MinerU SDK / Service
    mineru_batch_url: Optional[str] = "https://mineru.net/api/v4/file-urls/batch"
    mineru_api_url: Optional[str] = "https://mineru.net/api/v4/extract/task"
    mineru_model_version: str = "vlm"
    mineru_api_token: Optional[str] = ""
    mineru_pipeline_id: Optional[str] = ""
    mineru_timeout: int = 300
    mineru_max_file_size_mb: int = 100


@dataclass
class EmbeddingConfig:
    """向量嵌入模型配置"""

    provider: str = "nomic"  # nomic | openai | qwen
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model_name: str = "nomic-embed-text"
    dimension: int = 1536
    batch_size: int = 32


@dataclass
class RerankConfig:
    """Rerank 重排序模型配置"""

    enabled: bool = True
    model: str = "qwen3-rerank"
    endpoint: str = "https://dashscope.aliyuncs.com/compatible-api/v1/reranks"
    api_key: str = ""
    top_k: int = 5
    instruct: str = (
        "Given a web search query, retrieve relevant passages that answer the query."
    )


@dataclass
class MinerUConfig:
    """MinerU解析服务配置"""

    batch_url: str = "https://mineru.net/api/v4/file-urls/batch"
    api_url: str = "https://mineru.net/api/v4/extract/task"
    task_batch_url: str = "https://mineru.net/api/v4/extract/task/batch"
    status_url: str = "https://mineru.net/api/v4/extract/task/"  # https://mineru.net/api/v4/extract/task/{task_id}
    batch_status_url: str = "https://mineru.net/api/v4/extract-results/batch/"  # https://mineru.net/api/v4/extract-results/batch/{batch_id}
    model_version: str = "vlm"
    extra_formats: list[str] = None
    api_token: str = ""
    pipeline_id: str = ""
    timeout: int = 300
    max_file_size_mb: int = 100

    def __post_init__(self):
        if self.extra_formats is None:
            self.extra_formats = ["html"]


@dataclass
class RedisConfig:
    """Redis配置"""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    max_connections: int = 10


@dataclass
class PostgreSQLConfig:
    """PostgreSQL配置"""

    host: str = "localhost"
    port: int = 5432
    database: str = "acmg_ps3"
    user: str = "postgres"
    password: str = ""
    pool_size: int = 10
    max_overflow: int = 20


@dataclass
class Neo4jConfig:
    """Neo4j图数据库配置"""

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""
    database: str = "neo4j"
    max_connection_lifetime: int = 3600
    max_connection_pool_size: int = 50


@dataclass
class MilvusConfig:
    """Milvus向量数据库配置"""

    host: str = "localhost"
    port: int = 19530
    collection_name: str = "paper_chunks"
    dimension: int = 1536  # nomic-embed-text或openai embedding维度
    index_type: str = "IVF_FLAT"
    metric_type: str = "L2"


@dataclass
class QdrantConfig:
    """Qdrant向量数据库配置"""

    host: str = "localhost"
    port: int = 6333
    https: bool = False
    verify_ssl: bool = True  # TLS验证
    collection_name: str = "paper_chunks"
    api_key: str = ""
    dimension: int = 1536
    prefer_grpc: bool = False
    # 新增TLS相关配置
    grpc_port: int = 6334
    root_certificates: Optional[str] = None  # TLS根证书路径
    certificate_chain: Optional[str] = None  # TLS证书链路径
    private_key: Optional[str] = None  # TLS私钥路径
    # 从旧配置迁移的属性
    top_k: int = 5
    score_threshold: float = 0.7
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class MinIOConfig:
    """MinIO对象存储配置"""

    endpoint: str = "localhost:9000"
    access_key: str = ""  # 根凭证
    secret_key: str = ""  # 根凭证
    bucket_name: str = "acmg-documents"
    uploads_bucket: str = "literature-uploads"
    results_bucket: str = "processed-results"
    api: str = "s3v4"
    path: str = "auto"
    secure: bool = False  # 是否启用SSL/TLS


class AppConfig:
    """应用配置"""

    def __init__(self):
        self.app_name: str = "ACMG-PS3 Intelligence System"
        self.app_version: str = "1.0.0"
        self.environment: Environment = Environment.DEVELOPMENT
        self.debug: bool = True

        # API配置
        self.api_prefix: str = "/api"
        self.api_version: str = "v1"
        self.host: str = "0.0.0.0"
        self.port: int = 8000

        # 服务配置
        self.llm: Optional[LLMConfig] = LLMConfig()
        self.embedding: Optional[EmbeddingConfig] = EmbeddingConfig()
        self.rerank: Optional[RerankConfig] = RerankConfig()
        self.mineru: Optional[MinerUConfig] = MinerUConfig()

        # 数据库配置
        self.redis: RedisConfig = RedisConfig()
        self.postgresql: PostgreSQLConfig = PostgreSQLConfig()
        self.neo4j: Neo4jConfig = Neo4jConfig()
        self.milvus: MilvusConfig = MilvusConfig()
        self.qdrant: QdrantConfig = QdrantConfig()
        self.vector_backend: VectorBackend = VectorBackend.QDRANT
        self.minio: MinIOConfig = MinIOConfig()

        # 任务配置
        self.max_reasoning_iterations: int = 3
        self.max_upload_size: int = 50 * 1024 * 1024  # 50 MB
        self.task_timeout_seconds: int = 3600

        # 节点重试配置
        self.node_acquisition_max_retries: int = 2
        self.node_acquisition_delay_seconds: int = 300
        self.node_acquisition_timeout_seconds: int = 900
        self.node_parsing_max_retries: int = 1
        self.node_parsing_delay_seconds: int = 600
        self.node_parsing_timeout_seconds: int = 1800
        self.node_translation_max_retries: int = 2
        self.node_translation_delay_seconds: int = 120
        self.node_translation_timeout_seconds: int = 1200
        self.node_extraction_max_retries: int = 2
        self.node_extraction_delay_seconds: int = 300
        self.node_extraction_timeout_seconds: int = 1800
        self.node_acmg_max_retries: int = 1
        self.node_acmg_delay_seconds: int = 180
        self.node_acmg_timeout_seconds: int = 900

    @staticmethod
    def _str_to_bool(value: Optional[str], default: bool) -> bool:
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _load_dotenv():
        try:
            from dotenv import load_dotenv
        except ImportError:
            # python-dotenv is optional; skip if unavailable
            pass
        else:
            # 基础.env
            load_dotenv()

            # 环境特定配置（如 .env.development）
            env_name = os.getenv("ENVIRONMENT", "development").lower()
            env_path = os.path.join(os.getcwd(), f".env.{env_name}")
            if os.path.exists(env_path):
                load_dotenv(dotenv_path=env_path, override=True)

            # 显式ENV_FILE优先级最高
            env_file = os.getenv("ENV_FILE")
            if env_file:
                env_file_path = os.path.join(os.getcwd(), env_file)
                if os.path.exists(env_file_path):
                    load_dotenv(dotenv_path=env_file_path, override=True)

    @classmethod
    def from_env(cls):
        """从环境变量加载配置"""
        cls._load_dotenv()
        cfg = cls()

        cfg.app_name = os.getenv("APP_NAME", cfg.app_name)
        cfg.app_version = os.getenv("APP_VERSION", cfg.app_version)

        environment = os.getenv("ENVIRONMENT")
        if environment:
            try:
                cfg.environment = Environment(environment.lower())
            except ValueError:
                cfg.environment = Environment.DEVELOPMENT

        cfg.debug = cls._str_to_bool(os.getenv("DEBUG"), cfg.debug)
        cfg.api_prefix = os.getenv("API_PREFIX", cfg.api_prefix)
        cfg.api_version = os.getenv("API_VERSION", cfg.api_version)
        cfg.host = os.getenv("API_HOST", cfg.host)
        cfg.port = int(os.getenv("API_PORT", cfg.port))

        cfg.max_reasoning_iterations = int(
            os.getenv("MAX_REASONING_ITERATIONS", cfg.max_reasoning_iterations)
        )
        cfg.task_timeout_seconds = int(
            os.getenv("TASK_TIMEOUT_SECONDS", cfg.task_timeout_seconds)
        )

        # LLM配置
        llm = cfg.llm
        # OCR LLM配置
        llm.ocr_provider = os.getenv("OCR_PROVIDER", llm.ocr_provider)
        llm.ocr_base_url = os.getenv("OCR_BASE_URL", llm.ocr_base_url)
        llm.ocr_api_key = os.getenv("OCR_API_KEY", llm.ocr_api_key)
        llm.ocr_model = os.getenv("OCR_MODEL", llm.ocr_model)
        llm.ocr_batch_size = int(os.getenv("OCR_BATCH_SIZE", llm.ocr_batch_size))

        # MT-LLM配置
        llm.mt_api_key = os.getenv("MT_LLM_API_KEY", llm.mt_api_key)
        llm.mt_base_url = os.getenv("MT_LLM_BASE_URL", llm.mt_base_url)
        llm.mt_model = os.getenv("MT_LLM_MODEL", llm.mt_model)

        # 主力LLM配置
        llm.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", llm.deepseek_api_key)
        llm.deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", llm.deepseek_base_url)
        llm.deepseek_model = os.getenv("DEEPSEEK_MODEL", llm.deepseek_model)
        llm.claude_api_key = os.getenv("CLAUDE_API_KEY", llm.claude_api_key)
        llm.anthropic_base_url = os.getenv("ANTHROPIC_BASE_URL", llm.anthropic_base_url)
        llm.claude_model = os.getenv("CLAUDE_MODEL", llm.claude_model)
        llm.temperature = float(os.getenv("LLM_TEMPERATURE", llm.temperature))
        llm.max_tokens = int(os.getenv("LLM_MAX_TOKENS", llm.max_tokens))
        llm.timeout = int(os.getenv("LLM_TIMEOUT", llm.timeout))
        llm.max_retries = int(os.getenv("LLM_MAX_RETRIES", llm.max_retries))

        # Embedding配置
        embedding = cfg.embedding
        embedding.provider = os.getenv("EMBEDDING_PROVIDER", embedding.provider)
        embedding.base_url = os.getenv("EMBEDDING_BASE_URL", embedding.base_url)
        embedding.api_key = os.getenv("EMBEDDING_API_KEY", embedding.api_key)
        embedding.model_name = os.getenv("EMBEDDING_MODEL", embedding.model_name)
        embedding.dimension = int(os.getenv("EMBEDDING_DIMENSION", embedding.dimension))
        embedding.batch_size = int(
            os.getenv("EMBEDDING_BATCH_SIZE", embedding.batch_size)
        )

        # Rerank配置
        rerank = cfg.rerank
        rerank.enabled = cls._str_to_bool(os.getenv("RERANK_ENABLED"), rerank.enabled)
        rerank.model = os.getenv("RERANK_MODEL", rerank.model)
        rerank.endpoint = os.getenv("RERANK_ENDPOINT", rerank.endpoint)
        rerank.api_key = os.getenv("RERANK_API_KEY", rerank.api_key)
        rerank.top_k = int(os.getenv("RERANK_TOP_K", rerank.top_k))
        rerank.instruct = os.getenv("RERANK_INSTRUCT", rerank.instruct)

        # MinerU配置（环境变量）
        mineru = cfg.mineru
        mineru.api_url = os.getenv("MINERU_API_URL", mineru.api_url)
        mineru.batch_url = os.getenv("MINERU_BATCH_URL", mineru.batch_url)
        mineru.task_batch_url = os.getenv(
            "MINERU_TASK_BATCH_URL", mineru.task_batch_url
        )
        mineru.status_url = os.getenv("MINERU_STATUS_URL", mineru.status_url)
        mineru.batch_status_url = os.getenv(
            "MINERU_BATCH_STATUS_URL", mineru.batch_status_url
        )
        mineru.api_token = os.getenv("MINERU_API_TOKEN", mineru.api_token)
        mineru.pipeline_id = os.getenv("MINERU_PIPELINE_ID", mineru.pipeline_id)
        mineru.timeout = int(os.getenv("MINERU_TIMEOUT", mineru.timeout))
        mineru.max_file_size_mb = int(
            os.getenv("MINERU_MAX_FILE_SIZE_MB", mineru.max_file_size_mb)
        )
        mineru.model_version = os.getenv("MINERU_MODEL_VERSION", mineru.model_version)

        # Redis配置
        cfg.redis = RedisConfig(
            host=os.getenv("REDIS_HOST", cfg.redis.host),
            port=int(os.getenv("REDIS_PORT", cfg.redis.port)),
            db=int(os.getenv("REDIS_DB", cfg.redis.db)),
            password=os.getenv("REDIS_PASSWORD", cfg.redis.password),
            max_connections=int(
                os.getenv("REDIS_MAX_CONNECTIONS", cfg.redis.max_connections)
            ),
        )

        # PostgreSQL配置
        cfg.postgresql.host = os.getenv("POSTGRES_HOST", cfg.postgresql.host)
        cfg.postgresql.port = int(os.getenv("POSTGRES_PORT", cfg.postgresql.port))
        cfg.postgresql.database = os.getenv("POSTGRES_DB", cfg.postgresql.database)
        cfg.postgresql.user = os.getenv("POSTGRES_USER", cfg.postgresql.user)
        cfg.postgresql.password = os.getenv(
            "POSTGRES_PASSWORD", cfg.postgresql.password
        )
        cfg.postgresql.pool_size = int(
            os.getenv("POSTGRES_POOL_SIZE", cfg.postgresql.pool_size)
        )
        cfg.postgresql.max_overflow = int(
            os.getenv("POSTGRES_MAX_OVERFLOW", cfg.postgresql.max_overflow)
        )

        # Neo4j配置
        cfg.neo4j.uri = os.getenv("NEO4J_URI", cfg.neo4j.uri)
        cfg.neo4j.user = os.getenv("NEO4J_USER", cfg.neo4j.user)
        cfg.neo4j.password = os.getenv("NEO4J_PASSWORD", cfg.neo4j.password)
        cfg.neo4j.database = os.getenv("NEO4J_DATABASE", cfg.neo4j.database)

        # Vector backend selection
        backend = os.getenv("VECTOR_DB", cfg.vector_backend.value).lower()
        cfg.vector_backend = (
            VectorBackend(backend)
            if backend in (b.value for b in VectorBackend)
            else VectorBackend.QDRANT
        )

        # Milvus配置
        cfg.milvus.host = os.getenv("MILVUS_HOST", cfg.milvus.host)
        cfg.milvus.port = int(os.getenv("MILVUS_PORT", cfg.milvus.port))
        cfg.milvus.collection_name = os.getenv(
            "MILVUS_COLLECTION_NAME", cfg.milvus.collection_name
        )
        cfg.milvus.dimension = int(os.getenv("MILVUS_DIMENSION", cfg.milvus.dimension))
        cfg.milvus.index_type = os.getenv("MILVUS_INDEX_TYPE", cfg.milvus.index_type)
        cfg.milvus.metric_type = os.getenv("MILVUS_METRIC_TYPE", cfg.milvus.metric_type)

        # Qdrant配置
        cfg.qdrant.host = os.getenv("QDRANT_HOST", cfg.qdrant.host)
        cfg.qdrant.port = int(os.getenv("QDRANT_PORT", cfg.qdrant.port))
        cfg.qdrant.https = cls._str_to_bool(os.getenv("QDRANT_HTTPS"), cfg.qdrant.https)
        cfg.qdrant.verify_ssl = cls._str_to_bool(
            os.getenv("QDRANT_VERIFY_SSL"), cfg.qdrant.verify_ssl
        )
        cfg.qdrant.api_key = os.getenv("QDRANT_API_KEY", cfg.qdrant.api_key)
        cfg.qdrant.collection_name = os.getenv(
            "QDRANT_COLLECTION_NAME", cfg.qdrant.collection_name
        )
        cfg.qdrant.dimension = int(os.getenv("QDRANT_DIMENSION", cfg.qdrant.dimension))
        cfg.qdrant.prefer_grpc = cls._str_to_bool(
            os.getenv("QDRANT_PREFER_GRPC"), cfg.qdrant.prefer_grpc
        )
        cfg.qdrant.grpc_port = int(os.getenv("QDRANT_GRPC_PORT", cfg.qdrant.grpc_port))
        cfg.qdrant.root_certificates = os.getenv(
            "QDRANT_ROOT_CERTIFICATES", cfg.qdrant.root_certificates
        )
        cfg.qdrant.certificate_chain = os.getenv(
            "QDRANT_CERTIFICATE_CHAIN", cfg.qdrant.certificate_chain
        )
        cfg.qdrant.private_key = os.getenv("QDRANT_PRIVATE_KEY", cfg.qdrant.private_key)

        # MinIO配置
        cfg.minio.endpoint = os.getenv("MINIO_ENDPOINT", cfg.minio.endpoint)
        cfg.minio.access_key = os.getenv("MINIO_ACCESS_KEY", cfg.minio.access_key)
        cfg.minio.secret_key = os.getenv("MINIO_SECRET_KEY", cfg.minio.secret_key)
        cfg.minio.bucket_name = os.getenv("MINIO_BUCKET_NAME", cfg.minio.bucket_name)
        cfg.minio.uploads_bucket = os.getenv(
            "MINIO_UPLOADS_BUCKET", cfg.minio.uploads_bucket
        )
        cfg.minio.results_bucket = os.getenv(
            "MINIO_RESULTS_BUCKET", cfg.minio.results_bucket
        )
        cfg.minio.api = os.getenv("MINIO_API", cfg.minio.api)
        cfg.minio.path = os.getenv("MINIO_PATH", cfg.minio.path)
        cfg.minio.secure = cls._str_to_bool(os.getenv("MINIO_SECURE"), cfg.minio.secure)

        # 节点重试配置
        cfg.node_acquisition_max_retries = int(
            os.getenv("NODE_ACQUISITION_MAX_RETRIES", cfg.node_acquisition_max_retries)
        )
        cfg.node_acquisition_delay_seconds = int(
            os.getenv(
                "NODE_ACQUISITION_DELAY_SECONDS", cfg.node_acquisition_delay_seconds
            )
        )
        cfg.node_acquisition_timeout_seconds = int(
            os.getenv(
                "NODE_ACQUISITION_TIMEOUT_SECONDS", cfg.node_acquisition_timeout_seconds
            )
        )
        cfg.node_parsing_max_retries = int(
            os.getenv("NODE_PARSING_MAX_RETRIES", cfg.node_parsing_max_retries)
        )
        cfg.node_parsing_delay_seconds = int(
            os.getenv("NODE_PARSING_DELAY_SECONDS", cfg.node_parsing_delay_seconds)
        )
        cfg.node_parsing_timeout_seconds = int(
            os.getenv("NODE_PARSING_TIMEOUT_SECONDS", cfg.node_parsing_timeout_seconds)
        )
        cfg.node_translation_max_retries = int(
            os.getenv("NODE_TRANSLATION_MAX_RETRIES", cfg.node_translation_max_retries)
        )
        cfg.node_translation_delay_seconds = int(
            os.getenv(
                "NODE_TRANSLATION_DELAY_SECONDS", cfg.node_translation_delay_seconds
            )
        )
        cfg.node_translation_timeout_seconds = int(
            os.getenv(
                "NODE_TRANSLATION_TIMEOUT_SECONDS", cfg.node_translation_timeout_seconds
            )
        )
        cfg.node_extraction_max_retries = int(
            os.getenv("NODE_EXTRACTION_MAX_RETRIES", cfg.node_extraction_max_retries)
        )
        cfg.node_extraction_delay_seconds = int(
            os.getenv(
                "NODE_EXTRACTION_DELAY_SECONDS", cfg.node_extraction_delay_seconds
            )
        )
        cfg.node_extraction_timeout_seconds = int(
            os.getenv(
                "NODE_EXTRACTION_TIMEOUT_SECONDS", cfg.node_extraction_timeout_seconds
            )
        )
        cfg.node_acmg_max_retries = int(
            os.getenv("NODE_ACMG_MAX_RETRIES", cfg.node_acmg_max_retries)
        )
        cfg.node_acmg_delay_seconds = int(
            os.getenv("NODE_ACMG_DELAY_SECONDS", cfg.node_acmg_delay_seconds)
        )
        cfg.node_acmg_timeout_seconds = int(
            os.getenv("NODE_ACMG_TIMEOUT_SECONDS", cfg.node_acmg_timeout_seconds)
        )

        return cfg


# Pydantic配置类（保留原有兼容性）
class Settings(BaseSettings):
    # ==================== 应用配置 ====================
    app_name: str = "ACMG-PS3 Intelligence System"
    app_version: str = "2.1.0"
    api_prefix: str = "/api/v1"
    cors_origins: str = '["http://localhost:3000", "http://localhost:8000"]'
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
    postgres_port: int = Field(
        5432, validation_alias=AliasChoices("POSTGRES_PORT", "PGPORT")
    )
    postgres_db: str = Field(
        default="acmg_ps3", validation_alias=AliasChoices("POSTGRES_DB", "PGDATABASE")
    )
    postgres_user: str = Field(
        default="postgres", validation_alias=AliasChoices("POSTGRES_USER", "PGUSER")
    )
    postgres_password: str = Field(
        alias="POSTGRES_PASSWORD",
        validation_alias=AliasChoices("POSTGRES_PASSWORD", "PGPASSWORD"),
    )
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
    # 新增Qdrant TLS配置
    qdrant_grpc_port: int = 6334
    qdrant_root_certificates: Optional[str] = None  # TLS根证书路径
    qdrant_certificate_chain: Optional[str] = None  # TLS证书链路径
    qdrant_private_key: Optional[str] = None  # TLS私钥路径

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


def resolve_llm_triplet(settings: Settings, role: str) -> tuple[str, str, str]:
    """Resolve LLM configuration triplet for a given role.

    Args:
        settings: Settings instance containing LLM configurations
        role: LLM role name (retrieval/parsing/mt/format/vlm/evidence/classification/arbitration)

    Returns:
        tuple containing (api_key, base_url, model) for the role

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
        raise ValueError(
            f"Invalid LLM role: {role}. Valid roles: {', '.join(sorted(valid_roles))}"
        )
        raise ValueError(
            f"Invalid LLM role: {role}. Valid roles: {', '.join(sorted(valid_roles))}"
        )

    api_key = getattr(settings, f"{role}_api_key")
    base_url = getattr(settings, f"{role}_base_url")
    model = getattr(settings, f"{role}_model")

    return api_key, base_url, model


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


# 对于向后兼容性，暴露一个模块级别的配置变量
# 通过 __getattr__ 懒加载
def __getattr__(name: str):
    if name == "settings":
        return get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# 全局配置实例
app_config = AppConfig.from_env()
