"""Typed contracts for fused-75 optimization split manifests."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Fused75Split = Literal["auto_pool", "adjudication_dev", "adjudication_test"]
Fused75SelectionMethod = Literal["sorted_entry_id_v1"]
_LOWERCASE_HEX_CHARS = frozenset("0123456789abcdef")


@dataclass(frozen=True)
class Fused75SplitEntry:
    """One fused-75 entry assigned to an optimization split."""

    entry_id: str
    split: Fused75Split
    source_path: Path
    expected_path: Path
    selection_reason: str
    sha256: str


class Fused75SplitMetadata(BaseModel):
    """Stable metadata describing how a fused-75 split manifest was built."""

    model_config = ConfigDict(frozen=True)

    dataset_root: Path
    selection_path: Path
    selection_method: Fused75SelectionMethod
    split_seed: str
    dev_count: int = Field(ge=0)
    test_count: int = Field(ge=0)
    total_entries: int = Field(ge=0)


class Fused75SplitManifest(BaseModel):
    """Validated manifest for fused-75 optimization split entries."""

    model_config = ConfigDict(frozen=True, revalidate_instances="always")

    metadata: Fused75SplitMetadata
    entries: tuple[Fused75SplitEntry, ...]

    @model_validator(mode="after")
    def validate_unique_entry_ids(self) -> Fused75SplitManifest:
        """Reject manifests that assign the same entry more than once."""
        seen: set[str] = set()
        for entry in self.entries:
            if entry.entry_id in seen:
                raise ValueError(f"Duplicate entry_id: {entry.entry_id}")
            seen.add(entry.entry_id)
        return self

    @model_validator(mode="after")
    def validate_entry_sha256_values(self) -> Fused75SplitManifest:
        """Reject manifests containing invalid SHA-256 digests."""
        for entry in self.entries:
            if len(entry.sha256) != 64 or any(char not in _LOWERCASE_HEX_CHARS for char in entry.sha256):
                raise ValueError(f"Invalid sha256 for entry_id: {entry.entry_id}")
        return self
