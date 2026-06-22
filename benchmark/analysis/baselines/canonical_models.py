"""Canonical model metadata shared by benchmark datasets."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class CanonicalModelMetadata:
    """Paper-facing model identity copied from the first benchmark dataset."""

    model_baseline_id: str
    model_baseline_name: str
    provider_family: str
    model: str
    release_cohort: str
    release_date: str
    release_notes_url: str

    def as_metadata(self) -> Mapping[str, str]:
        """Return JSON-serializable metadata for benchmark reports."""
        return {
            "model_baseline_id": self.model_baseline_id,
            "model_baseline_name": self.model_baseline_name,
            "provider_family": self.provider_family,
            "model": self.model,
            "release_cohort": self.release_cohort,
            "release_date": self.release_date,
            "release_notes_url": self.release_notes_url,
        }


CANONICAL_GPT5_PROMPT_CITE = CanonicalModelMetadata(
    model_baseline_id="B6_GPT5_PROMPT_CITE",
    model_baseline_name="GPT-5 prompt-only citation-required",
    provider_family="openai",
    model="gpt-5-2025-08-07",
    release_cohort="frontier_2025q3_aug07_sep30",
    release_date="2025-08-07",
    release_notes_url="https://openai.com/index/introducing-gpt-5-for-developers/",
)
