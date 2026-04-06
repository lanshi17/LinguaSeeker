# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportCallIssue=false, reportGeneralTypeIssues=false, reportMissingImports=false, reportRedeclaration=false, reportFunctionMemberAccess=false, reportPossiblyUnboundVariable=false, reportReturnType=false

"""Base configuration for automated web crawlers."""

from dataclasses import dataclass
from typing import Optional

from src.config import Settings, get_settings, resolve_llm_triplet


@dataclass(frozen=True)
class LLMTriplet:
    api_key: Optional[str]
    base_url: str
    model: str


class AutomatedWebConfig:
    """Configuration helper for automated web crawlers."""

    @classmethod
    def get_settings(cls) -> Settings:
        """Get the global Settings instance."""
        return get_settings()

    @classmethod
    def get_retrieval_config(cls) -> LLMTriplet:
        """Get retrieval LLM configuration from Settings."""
        settings = cls.get_settings()
        api_key, base_url, model = resolve_llm_triplet(settings, "retrieval")
        return LLMTriplet(api_key=api_key, base_url=base_url, model=model)

    @classmethod
    def get_default_llm_provider(cls) -> str:
        """Get default LLM provider from retrieval config."""
        triplet = cls.get_retrieval_config()
        # Extract provider from base_url or use generic
        if "deepseek" in triplet.base_url.lower():
            return "deepseek"
        elif "openai" in triplet.base_url.lower():
            return "openai"
        elif "anthropic" in triplet.base_url.lower():
            return "anthropic"
        elif "dashscope" in triplet.base_url.lower():
            return "dashscope"
        else:
            return "generic"

    @classmethod
    def get_default_llm_api_key(cls) -> Optional[str]:
        """Get default LLM API key from retrieval config."""
        triplet = cls.get_retrieval_config()
        return triplet.api_key

    @classmethod
    def get_default_llm_base_url(cls) -> str:
        """Get default LLM base URL from retrieval config."""
        triplet = cls.get_retrieval_config()
        return triplet.base_url

    @classmethod
    def get_default_llm_model(cls) -> str:
        """Get default LLM model name from retrieval config."""
        triplet = cls.get_retrieval_config()
        return triplet.model
