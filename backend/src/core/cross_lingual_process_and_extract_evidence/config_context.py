"""Typed configuration context — single injection point for all LLM settings."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TranslationConfigContext:
    """Subset of app config needed by translation/formatting modules.

    Built once from ``cfg.llm`` at service init, then injected
    into sub-modules. Prevents raw config leakage into deep code.
    """

    model: str
    api_key: str
    api_keys: list[str] = field(default_factory=list)
    base_url: str = ""
    temperature: float = 0.0
    max_tokens: int = 8192
    timeout: int = 60

    @classmethod
    def from_config(cls, cfg: Any) -> TranslationConfigContext:
        """Build from the global config object (``cfg.llm``)."""
        llm = cfg.llm
        return cls(
            model=llm.model,
            api_key=llm.api_key,
            api_keys=llm.all_api_keys,
            base_url=llm.base_url,
            temperature=getattr(llm, "temperature", 0.0),
            max_tokens=getattr(llm, "max_tokens", 8192),
            timeout=llm.timeout,
        )
