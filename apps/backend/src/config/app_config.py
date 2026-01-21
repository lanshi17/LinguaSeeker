"""应用配置"""
from typing import Optional
from dataclasses import dataclass
from enum import Enum


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

    @classmethod
    def from_env(cls):
        """从环境变量加载配置"""
        # TODO: 从环境变量读取配置
        pass
