"""Validation helpers for Benchmark A alignment annotation files."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, cast

import json
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from benchmark.core import GROUND_TRUTH_DIR
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceAlignmentRecord,
)


AlignmentAnnotationRecord = EvidenceAlignmentRecord


class AlignmentAnnotationFile(BaseModel):
    """Validated alignment annotation payload for Benchmark A."""

    model_config = ConfigDict(extra="allow")

    entry_id: str = ""
    records: list[AlignmentAnnotationRecord] = Field(default_factory=list)


def load_alignment_annotation_file(path: Path) -> AlignmentAnnotationFile:
    """Load and validate one Benchmark A alignment annotation file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return validate_alignment_annotation_payload(payload, source_path=path)


def validate_alignment_annotation_payload(
    payload: object,
    *,
    source_path: Path | None = None,
) -> AlignmentAnnotationFile:
    """Validate an alignment annotation payload."""
    if not isinstance(payload, Mapping):
        raise ValueError(_error_prefix(source_path) + "expected a JSON object")
    try:
        model = AlignmentAnnotationFile.model_validate(cast(Mapping[str, Any], payload))
    except ValidationError as exc:
        raise ValueError(_error_prefix(source_path) + "invalid alignment annotation payload") from exc
    if not model.records:
        raise ValueError(_error_prefix(source_path) + "alignment annotation payload must contain records")
    return model


def write_alignment_annotation_template(entry_id: str, output_path: Path | None = None) -> Path:
    """Write a minimal alignment annotation template for manual curation."""
    path = output_path or (GROUND_TRUTH_DIR / entry_id / "alignment_annotations.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "entry_id": entry_id,
                "records": [
                    {
                        "entry_id": entry_id,
                        "field_id": "A.gene_symbol",
                        "original_value": "",
                        "translated_value": "",
                        "normalized_value": "",
                        "original_span_id": "",
                        "translated_span_id": "",
                        "alignment_label": "missing",
                        "support_label": "insufficient",
                        "drift_reason": "",
                        "confidence": 0.0,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _error_prefix(source_path: Path | None) -> str:
    if source_path is None:
        return ""
    return f"{source_path}: "
