"""Embedding provider implementation."""

from langchain_openai import OpenAIEmbeddings

from src.infrastructure.utils.config import AppConfig


class EmbeddingProvider:
    """Factory for embedding providers."""

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg

    def get_embeddings(self) -> OpenAIEmbeddings:
        """Get embedding model instance."""
        # Use dedicated embedding config if available, otherwise fall back to DeepSeek
        api_key = self.cfg.embedding.api_key or self.cfg.llm.deepseek_api_key
        base_url = self.cfg.embedding.base_url or self.cfg.llm.deepseek_base_url
        
        # For DashScope (Alibaba Cloud), we need to specify dimensions
        # and ensure compatibility with their API
        if "dashscope" in base_url.lower():
            return OpenAIEmbeddings(
                api_key=api_key,
                base_url=base_url,
                model=self.cfg.embedding.model_name,
                dimensions=self.cfg.embedding.dimension,
                # DashScope specific settings
                check_embedding_ctx_length=False,
                chunk_size=min(self.cfg.embedding.batch_size, 10),  # DashScope限制最大10
            )
        else:
            return OpenAIEmbeddings(
                api_key=api_key,
                base_url=base_url,
                model=self.cfg.embedding.model_name,
            )
