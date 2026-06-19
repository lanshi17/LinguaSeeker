"""Tests for fused-75 optimization split contracts."""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from benchmark.optimization.fused75.contracts import (
    Fused75SplitEntry,
    Fused75SplitManifest,
    Fused75SplitMetadata,
)


def _metadata() -> Fused75SplitMetadata:
    return Fused75SplitMetadata(
        dataset_root=Path("benchmark/data/ground_truth/clinvar_fused"),
        selection_path=Path("benchmark/data/ground_truth/clinvar_fused/selection.json"),
        selection_method="sorted_entry_id_v1",
        split_seed="sorted-entry-id-v1",
        dev_count=10,
        test_count=10,
        total_entries=75,
    )


def test_valid_manifest_accepts_one_entry() -> None:
    entry = Fused75SplitEntry(
        entry_id="fused-001",
        split="auto_pool",
        source_path=Path("sources/fused-001.pdf"),
        expected_path=Path("expected/fused-001.json"),
        selection_reason="deterministic pool member",
        sha256="a" * 64,
    )

    manifest = Fused75SplitManifest(metadata=_metadata(), entries=(entry,))

    assert manifest.metadata.split_seed == "sorted-entry-id-v1"
    assert manifest.entries == (entry,)


def test_manifest_rejects_invalid_split_value() -> None:
    with pytest.raises(ValidationError, match="split"):
        Fused75SplitManifest(
            metadata=_metadata(),
            entries=(
                {
                    "entry_id": "fused-001",
                    "split": "dev",
                    "source_path": "sources/fused-001.pdf",
                    "expected_path": "expected/fused-001.json",
                    "selection_reason": "bad split",
                    "sha256": "a" * 64,
                },
            )
        )


def test_manifest_rejects_duplicate_entry_ids() -> None:
    entry = {
        "entry_id": "fused-001",
        "split": "adjudication_dev",
        "source_path": "sources/fused-001.pdf",
        "expected_path": "expected/fused-001.json",
        "selection_reason": "stable dev selection",
        "sha256": "a" * 64,
    }

    with pytest.raises(ValidationError, match="Duplicate entry_id"):
        Fused75SplitManifest(metadata=_metadata(), entries=(entry, {**entry, "split": "adjudication_test"}))


@pytest.mark.parametrize(
    "sha256",
    (
        "a" * 63,
        "g" * 64,
        "A" * 64,
    ),
)
def test_manifest_rejects_invalid_sha256_values(sha256: str) -> None:
    entry = Fused75SplitEntry(
        entry_id="fused-001",
        split="auto_pool",
        source_path=Path("sources/fused-001.pdf"),
        expected_path=Path("expected/fused-001.json"),
        selection_reason="deterministic pool member",
        sha256=sha256,
    )

    with pytest.raises(ValidationError, match="sha256"):
        Fused75SplitManifest(metadata=_metadata(), entries=(entry,))


def test_entry_paths_serialize_as_stable_json_strings() -> None:
    manifest = Fused75SplitManifest(
        metadata=_metadata(),
        entries=(
            Fused75SplitEntry(
                entry_id="fused-001",
                split="adjudication_test",
                source_path=Path("sources/fused-001.pdf"),
                expected_path=Path("expected/fused-001.json"),
                selection_reason="held out test",
                sha256="a" * 64,
            ),
        )
    )

    payload = manifest.model_dump(mode="json")

    assert payload["entries"][0]["source_path"] == "sources/fused-001.pdf"
    assert payload["entries"][0]["expected_path"] == "expected/fused-001.json"
    assert payload["metadata"]["dataset_root"] == "benchmark/data/ground_truth/clinvar_fused"
