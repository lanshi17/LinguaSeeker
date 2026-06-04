"""Typed configuration context — single injection point for all LLM settings."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TranslationConfigContext:
    """Subset of app config needed by translation/formatting modules.

    Built once from ``cfg.llm`` at service init, then injected
    into sub-modules. Prevents raw config leakage into deep code.
    """

    model: str
    api_key: str
    base_url: str
    temperature: float = 0.0
    timeout: int = 60

    @classmethod
    def from_config(cls, cfg: Any) -> TranslationConfigContext:
        """Build from the global config object (``cfg.llm``)."""
        return cls(
            model=cfg.llm.model,
            api_key=cfg.llm.api_key,
            base_url=cfg.llm.base_url,
            temperature=getattr(cfg.llm, "temperature", 0.0),
            timeout=cfg.llm.timeout,
        )
