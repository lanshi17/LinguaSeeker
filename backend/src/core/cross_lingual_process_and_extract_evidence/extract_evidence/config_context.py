"""Typed config context for evidence extraction."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvidenceExtractionConfigContext:
    """Subset of app config needed by the evidence extraction module."""

    api_key: str
    base_url: str
    reasoning_api_key: str
    reasoning_base_url: str
    fast_model: str
    standard_model: str
    strong_model: str
    fast_effort: str = ""
    standard_effort: str = ""
    strong_effort: str = "high"
    max_tokens: int = 8192
    temperature: float = 0.0
    timeout: int = 60
    max_retries: int = 3

    @classmethod
    def from_config(cls, cfg: Any) -> EvidenceExtractionConfigContext:
        evidence_cfg = cfg.evidence_extraction
        return cls(
            api_key=evidence_cfg.api_key,
            base_url=evidence_cfg.base_url,
            reasoning_api_key=evidence_cfg.reasoning_api_key,
            reasoning_base_url=evidence_cfg.reasoning_base_url,
            fast_model=evidence_cfg.fast_model,
            standard_model=evidence_cfg.standard_model,
            strong_model=evidence_cfg.strong_model,
            fast_effort=evidence_cfg.fast_effort,
            standard_effort=evidence_cfg.standard_effort,
            strong_effort=evidence_cfg.strong_effort,
            max_tokens=cfg.reasoning.max_tokens,
            temperature=evidence_cfg.temperature,
            timeout=evidence_cfg.timeout,
            max_retries=evidence_cfg.max_retries,
        )
