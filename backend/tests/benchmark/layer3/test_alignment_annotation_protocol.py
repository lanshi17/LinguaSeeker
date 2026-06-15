"""Tests for Benchmark A alignment annotation protocol validation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.layer3.analysis.alignment_annotation_protocol import (
    load_alignment_annotation_file,
    validate_alignment_annotation_payload,
)


def test_alignment_annotation_payload_validates_records() -> None:
    payload = {
        "entry_id": "clingen_000",
        "records": [
            {
                "entry_id": "clingen_000",
                "field_id": "A.gene_symbol",
                "original_value": "GENE1",
                "translated_value": "GENE1",
                "normalized_value": "gene1",
                "original_span_id": "original-p1",
                "translated_span_id": "translated-p1",
                "alignment_label": "aligned",
                "support_label": "supports",
                "confidence": 1.0,
            }
        ],
    }

    model = validate_alignment_annotation_payload(payload)

    assert model.entry_id == "clingen_000"
    assert model.records[0].alignment_label == "aligned"
    assert model.records[0].support_label == "supports"


def test_alignment_annotation_payload_requires_labels() -> None:
    payload = {
        "entry_id": "clingen_000",
        "records": [
            {
                "entry_id": "clingen_000",
                "field_id": "A.gene_symbol",
                "original_value": "GENE1",
                "translated_value": "GENE1",
                "normalized_value": "gene1",
                "original_span_id": "original-p1",
                "translated_span_id": "translated-p1",
                "confidence": 1.0,
            }
        ],
    }

    with pytest.raises(ValueError):
        validate_alignment_annotation_payload(payload)


def test_alignment_annotation_payload_rejects_expected_json_shape(tmp_path: Path) -> None:
    annotation_path = tmp_path / "alignment_annotations.json"
    annotation_path.write_text(
        json.dumps(
            {
                "entry_id": "clingen_000",
                "records": [
                    {
                        "field_id": "A.gene_symbol",
                        "value": "GENE1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_alignment_annotation_file(annotation_path)
