"""Typed config context for evidence extraction.

Reads directly from FAST_LLM and REASONING_LLM config — no separate
evidence_extraction config section needed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceExtractionConfigContext:
    """Subset of app config needed by the evidence extraction module.

    FAST tier uses cfg.llm (FAST_LLM), STANDARD/STRONG tiers use cfg.reasoning (REASONING_LLM).
    """

    api_key: str
    api_keys: list[str] = field(default_factory=list)
    base_url: str = ""
    reasoning_api_key: str = ""
    reasoning_api_keys: list[str] = field(default_factory=list)
    reasoning_base_url: str = ""
    fast_model: str = ""
    standard_model: str = ""
    strong_model: str = ""
    fast_effort: str = ""
    standard_effort: str = ""
    strong_effort: str = "high"
    max_tokens: int = 8192
    temperature: float = 0.0
    timeout: int = 180
    max_retries: int = 1

    @classmethod
    def from_config(cls, cfg: Any) -> EvidenceExtractionConfigContext:
        llm = cfg.llm
        reasoning = cfg.reasoning
        return cls(
            api_key=llm.api_key,
            api_keys=llm.all_api_keys,
            base_url=llm.base_url,
            reasoning_api_key=reasoning.api_key,
            reasoning_api_keys=reasoning.all_api_keys,
            reasoning_base_url=reasoning.base_url,
            fast_model=llm.model,
            standard_model=reasoning.model or llm.model,
            strong_model=reasoning.model,
            fast_effort="",
            standard_effort=reasoning.reasoning_effort,
            strong_effort=reasoning.reasoning_effort,
            max_tokens=reasoning.max_tokens,
            temperature=0.0,
            timeout=reasoning.timeout,
            max_retries=1,
        )
