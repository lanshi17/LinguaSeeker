"""Typed contracts for fused-75 adjudication payloads."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Fused75Visibility = Literal[
    "source_visible",
    "not_source_visible",
    "ambiguous_boundary",
    "unsupported_prediction",
]
Fused75AdjudicationSplit = Literal["adjudication_dev", "adjudication_test"]


class Fused75FieldAdjudication(BaseModel):
    """One adjudicated expected field label for a fused-75 entry."""

    model_config = ConfigDict(frozen=True)

    field_id: str = Field(min_length=1)
    expected_value: str
    visibility: Fused75Visibility | None = None
    source_quote: str | None = Field(default=None, min_length=1, max_length=500)
    source_location: str | None = Field(default=None, min_length=1)
    adjudicator: str | None = Field(default=None, min_length=1)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_source_visible_evidence(self) -> Fused75FieldAdjudication:
        """Require compact source evidence for source-visible labels."""
        if self.visibility != "source_visible":
            return self

        missing_fields = [
            field_name
            for field_name in ("source_quote", "source_location", "adjudicator")
            if getattr(self, field_name) is None
        ]
        if missing_fields:
            raise ValueError(f"source_visible labels require: {', '.join(missing_fields)}")
        return self


class Fused75EntryAdjudication(BaseModel):
    """Completed adjudication payload for one fused-75 entry."""

    model_config = ConfigDict(frozen=True)

    entry_id: str = Field(min_length=1)
    split: Fused75AdjudicationSplit
    source_path: Path
    expected_path: Path
    is_complete: bool = False
    labels: tuple[Fused75FieldAdjudication, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_field_ids(self) -> Fused75EntryAdjudication:
        """Reject adjudication payloads with duplicate field labels."""
        seen: set[str] = set()
        for label in self.labels:
            if label.field_id in seen:
                raise ValueError(f"Duplicate field_id: {label.field_id}")
            seen.add(label.field_id)
        return self

    @model_validator(mode="after")
    def validate_completed_labels(self) -> Fused75EntryAdjudication:
        """Require every label to carry an adjudication decision when complete."""
        if not self.is_complete:
            return self
        missing = tuple(label.field_id for label in self.labels if label.visibility is None)
        if missing:
            raise ValueError(f"Completed adjudication has unlabeled fields: {', '.join(missing)}")
        return self
