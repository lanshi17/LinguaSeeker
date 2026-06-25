"""Extract labeled candidate dataset for learned arbitrator policy evaluation.

Builds candidate-level samples from Phase 2 artifacts and expected.json,
labels each candidate against gold field values, and extracts feature vectors.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from benchmark.core import GROUND_TRUTH_DIR, REPORTS_DIR
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
    EvidenceItem,
    Track,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.contextual import (
    reconcile_with_context,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.contracts import (
    CandidateScore,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.core import (
    _build_candidates,
    _Candidate,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.contextual import (
    _score_candidate,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.features import (
    CandidateFeatureVector,
    extract_features,
)
from src.core.standardize_entities_and_align_knowledge.context_pack.core import (
    build_context_pack_from_expected_json,
)


@dataclass(frozen=True)
class CandidateSample:
    """One labeled candidate sample for policy learning."""

    entry_id: str
    field_id: str
    track: str
    normalized_value: str
    label: int
    features: CandidateFeatureVector
    span_id: str
    source_snippet_hash: str
    selected_by_contextual: bool


@dataclass(frozen=True)
class DatasetSummary:
    """Summary statistics for the extracted dataset."""

    entries_covered: int
    entries_missing_artifact: int
    candidate_count: int
    positive_count: int
    negative_count: int
    per_field_counts: dict[str, int]
    per_label_counts: dict[int, int]
    missing_entries: list[str]


def build_dataset(ground_truth_dir: Path = GROUND_TRUTH_DIR) -> tuple[list[CandidateSample], DatasetSummary]:
    """Build the labeled candidate dataset from Phase 2 artifacts."""
    from benchmark.core.pipeline_client import _load_entries

    selection_items = _load_entries(ground_truth_dir)

    samples: list[CandidateSample] = []
    entries_covered = 0
    entries_missing = 0
    missing_entries: list[str] = []
    per_field: Counter[str] = Counter()

    for selection_item in selection_items:
        entry_id = str(selection_item["entry_id"])
        artifact_path = ground_truth_dir / entry_id / "preprocessed" / "phase_2" / "extraction_result.json"
        expected_path = ground_truth_dir / entry_id / "expected.json"

        if not artifact_path.exists() or not expected_path.exists():
            entries_missing += 1
            missing_entries.append(entry_id)
            continue

        expected = cast(dict[str, Any], json.loads(expected_path.read_text(encoding="utf-8")))
        gold_fields = {
            str(item["field_id"]): _normalize_gold(item["value"])
            for item in expected.get("expected_evidence", [])
        }
        if not gold_fields:
            entries_missing += 1
            missing_entries.append(entry_id)
            continue

        result = DualEvidenceExtractionResult.model_validate_json(
            artifact_path.read_text(encoding="utf-8")
        )
        context_pack = build_context_pack_from_expected_json(expected_path)

        contextual_output = reconcile_with_context(
            result.original_result,
            result.translated_result,
            context_pack,
        )
        contextual_selections: dict[str, str] = {}
        for decision in contextual_output.decisions:
            if decision.accepted is not None and decision.accepted_score is not None:
                contextual_selections[decision.field_id] = decision.accepted_score.normalized_value

        candidates = _build_candidates(result.original_result, result.translated_result, phenotype=False)
        scorable = [c for c in candidates if c.item.field_id in gold_fields]

        for field_id in sorted({c.item.field_id for c in scorable}):
            field_candidates = tuple(c for c in scorable if c.item.field_id == field_id)
            for candidate in field_candidates:
                score = _score_candidate(candidate, field_candidates, context_pack)
                gold_value = gold_fields[field_id]
                label = 1 if candidate.normalized_value == gold_value else 0
                source = candidate.item.source or candidate.item.raw_source
                features = extract_features(score, candidate.item, candidate.track)
                samples.append(
                    CandidateSample(
                        entry_id=entry_id,
                        field_id=field_id,
                        track=candidate.track.value,
                        normalized_value=candidate.normalized_value,
                        label=label,
                        features=features,
                        span_id=source.span_id if source is not None else "",
                        source_snippet_hash=_snippet_hash(source),
                        selected_by_contextual=(
                            contextual_selections.get(field_id) == candidate.normalized_value
                        ),
                    )
                )
                per_field[field_id] += 1

        entries_covered += 1

    label_counts = Counter(s.label for s in samples)
    summary = DatasetSummary(
        entries_covered=entries_covered,
        entries_missing_artifact=entries_missing,
        candidate_count=len(samples),
        positive_count=label_counts.get(1, 0),
        negative_count=label_counts.get(0, 0),
        per_field_counts=dict(per_field),
        per_label_counts=dict(label_counts),
        missing_entries=missing_entries,
    )
    return samples, summary


def _normalize_gold(value: object) -> str:
    if isinstance(value, list):
        return "|".join(sorted(str(v).strip().casefold() for v in value))
    return str(value).strip().casefold()


def _snippet_hash(source: object | None) -> str:
    if source is None:
        return ""
    snippet = getattr(source, "text_snippet", "")
    if not snippet:
        return ""
    import hashlib
    return hashlib.sha256(snippet.encode("utf-8")).hexdigest()[:16]


def _print_summary(summary: DatasetSummary) -> None:
    print(f"Entries covered: {summary.entries_covered}")
    print(f"Entries missing: {summary.entries_missing_artifact}")
    print(f"Total candidates: {summary.candidate_count}")
    print(f"Positive (match gold): {summary.positive_count}")
    print(f"Negative (competing): {summary.negative_count}")
    print(f"Per-field distribution:")
    for field_id, count in sorted(summary.per_field_counts.items()):
        print(f"  {field_id}: {count}")
    if summary.missing_entries:
        print(f"Missing entries: {', '.join(summary.missing_entries[:5])}")


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for arbitrator dataset extraction."""
    parser = argparse.ArgumentParser(description="Extract labeled arbitrator candidate dataset.")
    parser.add_argument("--ground-truth-dir", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--summary", action="store_true", help="Print dataset summary only")
    args = parser.parse_args(argv)

    samples, summary = build_dataset(args.ground_truth_dir)
    _print_summary(summary)

    if not args.summary:
        output_path = REPORTS_DIR / f"arbitrator_dataset_{time.strftime('%Y%m%d_%H%M%S')}.json"
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(_serialize_dataset(samples, summary), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Dataset written to: {output_path}")


def _serialize_dataset(
    samples: list[CandidateSample],
    summary: DatasetSummary,
) -> dict[str, Any]:
    return {
        "summary": {
            "entries_covered": summary.entries_covered,
            "entries_missing_artifact": summary.entries_missing_artifact,
            "candidate_count": summary.candidate_count,
            "positive_count": summary.positive_count,
            "negative_count": summary.negative_count,
            "per_field_counts": summary.per_field_counts,
            "missing_entries": summary.missing_entries,
        },
        "samples": [
            {
                "entry_id": s.entry_id,
                "field_id": s.field_id,
                "track": s.track,
                "normalized_value": s.normalized_value,
                "label": s.label,
                "features": s.features.to_list(),
                "span_id": s.span_id,
                "source_snippet_hash": s.source_snippet_hash,
                "selected_by_contextual": s.selected_by_contextual,
            }
            for s in samples
        ],
    }


if __name__ == "__main__":
    main()
