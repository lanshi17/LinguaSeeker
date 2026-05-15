"""Typed config context for evidence extraction."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvidenceExtractionConfigContext:
    """Subset of app config needed by the evidence extraction module."""

    api_key: str
    base_url: str
    fast_model: str
    standard_model: str
    strong_model: str
    temperature: float = 0.0
    timeout: int = 60
    max_retries: int = 3

    @classmethod
    def from_config(cls, cfg: Any) -> EvidenceExtractionConfigContext:
        evidence_cfg = cfg.evidence_extraction
        return cls(
            api_key=evidence_cfg.api_key,
            base_url=evidence_cfg.base_url,
            fast_model=evidence_cfg.fast_model,
            standard_model=evidence_cfg.standard_model,
            strong_model=evidence_cfg.strong_model,
            temperature=evidence_cfg.temperature,
            timeout=evidence_cfg.timeout,
            max_retries=evidence_cfg.max_retries,
        )
