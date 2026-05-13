"""Typed configuration context — single injection point for all LLM settings."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TranslationConfigContext:
    """Subset of app config needed by translation/formatting modules.

    Built once from ``cfg.translation`` at service init, then injected
    into sub-modules. Prevents raw config leakage into deep code.
    """

    model: str
    api_key: str
    base_url: str
    temperature: float = 0.0

    @classmethod
    def from_config(cls, cfg: Any) -> TranslationConfigContext:
        """Build from the global config object (``cfg.translation``)."""
        return cls(
            model=cfg.translation.model,
            api_key=cfg.translation.api_key,
            base_url=cfg.translation.base_url,
            temperature=getattr(cfg.translation, "temperature", 0.0),
        )
