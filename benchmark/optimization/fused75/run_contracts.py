"""Typed contracts for fused-75 pipeline variant runs."""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PipelineDatasetSplit = Literal["dev", "test", "auto_pool"]
PipelineDecisionValue = Literal["accepted", "rejected", "checkpoint_only"]
PipelineFlagValue = bool | int | float | str


class PipelineFlag(BaseModel):
    """One deterministic pipeline flag entry for a variant run."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(min_length=1)
    value: PipelineFlagValue


class PipelineVariantConfig(BaseModel):
    """Configuration identity for one fused-75 pipeline variant."""

    model_config = ConfigDict(frozen=True)

    variant_id: str = Field(min_length=1)
    git_commit: str = Field(min_length=1)
    dataset_split: PipelineDatasetSplit
    pipeline_flags: tuple[PipelineFlag, ...]
    model_config_names: tuple[str, ...]

    @model_validator(mode="after")
    def normalize_ordered_fields(self) -> PipelineVariantConfig:
        """Keep repeated fields in deterministic order for stable reports."""
        sorted_flags = tuple(sorted(self.pipeline_flags, key=lambda flag: (flag.key, str(flag.value))))
        sorted_model_names = tuple(sorted(self.model_config_names))
        object.__setattr__(self, "pipeline_flags", sorted_flags)
        object.__setattr__(self, "model_config_names", sorted_model_names)
        return self


class PipelineRunMetric(BaseModel):
    """Runtime, cost, and quality metrics for one fused-75 pipeline run."""

    model_config = ConfigDict(frozen=True)

    runtime_seconds: float = Field(ge=0)
    llm_call_count: int = Field(ge=0)
    prompt_token_count: int = Field(ge=0)
    completion_token_count: int = Field(ge=0)
    total_token_count: int = Field(ge=0)
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    f1: float = Field(ge=0, le=1)
    source_visible_f1: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_token_total(self) -> PipelineRunMetric:
        """Reject reports with inconsistent token accounting."""
        expected_total = self.prompt_token_count + self.completion_token_count
        if self.total_token_count != expected_total:
            raise ValueError("total_token_count must equal prompt_token_count + completion_token_count")
        return self


class PipelineVariantDecision(BaseModel):
    """Promotion decision for a fused-75 pipeline variant."""

    model_config = ConfigDict(frozen=True)

    decision: PipelineDecisionValue
    reason: str = Field(min_length=1)


class PipelineRunReport(BaseModel):
    """Complete deterministic report for one fused-75 pipeline run."""

    model_config = ConfigDict(frozen=True)

    config: PipelineVariantConfig
    metric: PipelineRunMetric
    decision: PipelineVariantDecision

    def to_stable_json(self) -> str:
        """Serialize the report with stable key ordering and compact separators."""
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
