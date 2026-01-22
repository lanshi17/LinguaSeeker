"""应用配置"""

import os
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Environment(str, Enum):
    """环境类型"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class LLMConfig:
    """大语言模型配置"""
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
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 60
    max_retries: int = 3


@dataclass
class EmbeddingConfig:
    """向量嵌入模型配置"""
    provider: str = "nomic"  # nomic | openai
    model_name: str = "nomic-embed-text"
    dimension: int = 1536
    batch_size: int = 32


@dataclass
class MinerUConfig:
    """MinerU解析服务配置"""
    api_url: str = "http://localhost:8080"
    timeout: int = 300
    max_file_size_mb: int = 100


@dataclass
class AppConfig:
    """应用配置"""
    app_name: str = "ACMG-PS3 Intelligence System"
    version: str = "2.0.0"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True

    # API配置
    api_prefix: str = "/api"
    api_version: str = "v1"
    host: str = "0.0.0.0"
    port: int = 8000

    # 服务配置
    llm: LLMConfig = None
    embedding: EmbeddingConfig = None
    mineru: MinerUConfig = None

    # 任务配置
    max_reasoning_iterations: int = 3
    task_timeout_seconds: int = 3600

    def __post_init__(self):
        if self.llm is None:
            self.llm = LLMConfig()
        if self.embedding is None:
            self.embedding = EmbeddingConfig()
        if self.mineru is None:
            self.mineru = MinerUConfig()

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
            env_path = Path(f".env.{env_name}")
            if env_path.exists():
                load_dotenv(dotenv_path=env_path, override=True)

            # 显式ENV_FILE优先级最高
            env_file = os.getenv("ENV_FILE")
            if env_file:
                env_file_path = Path(env_file)
                if env_file_path.exists():
                    load_dotenv(dotenv_path=env_file_path, override=True)

    @classmethod
    def from_env(cls):
        """从环境变量加载配置"""
        cls._load_dotenv()
        cfg = cls()

        cfg.app_name = os.getenv("APP_NAME", cfg.app_name)
        cfg.version = os.getenv("APP_VERSION", cfg.version)

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
        llm.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", llm.deepseek_api_key)
        llm.deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", llm.deepseek_base_url)
        llm.deepseek_model = os.getenv("DEEPSEEK_MODEL", llm.deepseek_model)
        llm.claude_api_key = os.getenv("CLAUDE_API_KEY", llm.claude_api_key)
        llm.anthropic_base_url = os.getenv(
            "ANTHROPIC_BASE_URL", llm.anthropic_base_url
        )
        llm.claude_model = os.getenv("CLAUDE_MODEL", llm.claude_model)
        llm.temperature = float(os.getenv("LLM_TEMPERATURE", llm.temperature))
        llm.max_tokens = int(os.getenv("LLM_MAX_TOKENS", llm.max_tokens))
        llm.timeout = int(os.getenv("LLM_TIMEOUT", llm.timeout))
        llm.max_retries = int(os.getenv("LLM_MAX_RETRIES", llm.max_retries))

        # Embedding配置
        embedding = cfg.embedding
        embedding.provider = os.getenv("EMBEDDING_PROVIDER", embedding.provider)
        embedding.model_name = os.getenv("EMBEDDING_MODEL", embedding.model_name)
        embedding.dimension = int(
            os.getenv("EMBEDDING_DIMENSION", embedding.dimension)
        )
        embedding.batch_size = int(
            os.getenv("EMBEDDING_BATCH_SIZE", embedding.batch_size)
        )

        # MinerU配置
        mineru = cfg.mineru
        mineru.api_url = os.getenv("MINERU_API_URL", mineru.api_url)
        mineru.timeout = int(os.getenv("MINERU_TIMEOUT", mineru.timeout))
        mineru.max_file_size_mb = int(
            os.getenv("MINERU_MAX_FILE_SIZE_MB", mineru.max_file_size_mb)
        )

        return cfg
