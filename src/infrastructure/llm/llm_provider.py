"""LLM provider factory."""

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

# Using absolute imports from src root
from src.infrastructure.utils.config import AppConfig


class LLMProvider:
    """Factory for LLM instances."""

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg

    def get_primary_llm(self) -> ChatOpenAI:
        """Get primary LLM (DeepSeek)."""
        return ChatOpenAI(
            api_key=self.cfg.llm.deepseek_api_key,
            base_url=self.cfg.llm.deepseek_base_url,
            model=self.cfg.llm.deepseek_model,
            temperature=0,
            timeout=self.cfg.llm.timeout,
            max_retries=self.cfg.llm.max_retries,
        )

    def get_arbiter_llm(self) -> ChatAnthropic:
        """Get arbiter LLM (Claude)."""
        base_url = self._normalize_anthropic_base(self.cfg.llm.anthropic_base_url)
        return ChatAnthropic(
            api_key=self.cfg.llm.claude_api_key,
            base_url=base_url,
            model=self.cfg.llm.claude_model,
            temperature=0,
            timeout=self.cfg.llm.timeout,
            max_retries=self.cfg.llm.max_retries,
        )

    @staticmethod
    def _normalize_anthropic_base(url: str) -> str:
        if not url:
            return url
        clean = url.rstrip("/")
        if clean.endswith("/v1"):
            clean = clean[:-3]
        return clean
