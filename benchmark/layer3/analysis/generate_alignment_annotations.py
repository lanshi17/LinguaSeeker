"""Generate Benchmark A gold alignment annotations from expected.json.

This is a *data preparation* step, not a runtime predictor. It derives the
ground-truth alignment relationship between the original and translated tracks
of the English-only ClinGen N=30 transport set from the curated gold evidence
in ``expected.json`` (``expected_evidence``). The gold is therefore independent
of the runtime extraction predictor: it reflects the known catalog values that
both tracks are expected to recover, not the predictor's own output.

Scoring scope (Benchmark A): three scorable fields per entry.
  - ``A.gene_symbol``
  - ``A.disease_diagnosis``
  - ``A.gene_disease_relationship``

Gold label policy for the English-only transport set:
  - If the gold value is present and both tracks extracted it → ``aligned`` /
    ``supports``.
  - If the gold value is present but only one track extracted it → ``missing`` /
    ``insufficient``.
  - ``A.gene_disease_relationship`` gold value is derived from the ClinGen
    ``classification`` / ``moi`` evidence direction (causative/associated).

Run (dry-run by default)::

    PYTHONPATH=.:backend uv run --project backend --no-sync \\
        python -m benchmark.layer3.analysis.generate_alignment_annotations --limit 2

Apply::

    PYTHONPATH=.:backend uv run --project backend --no-sync \\
        python -m benchmark.layer3.analysis.generate_alignment_annotations --write
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from benchmark.layer3.evaluate import GROUND_TRUTH_DIR
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceAlignmentLabel,
    EvidenceAlignmentRecord,
    EvidenceSupportLabel,
)


SCORABLE_FIELDS: tuple[str, ...] = (
    "A.gene_symbol",
    "A.disease_diagnosis",
    "A.gene_disease_relationship",
)

# ClinGen classification tokens that map to a causative gene-disease relationship.
_CAUSATIVE_TOKENS = {"definitive", "strong", "moderate", "limited"}
# Tokens that map to an association / susceptibility relationship.
_ASSOCIATION_TOKENS = {"susceptibility", "sd"}


@dataclass(frozen=True)
class AnnotationConfig:
    """Configuration for gold annotation generation."""

    ground_truth_root: Path = GROUND_TRUTH_DIR
    entry_ids: tuple[str, ...] = ()
    limit: int | None = None
    write: bool = False


@dataclass(frozen=True)
class AnnotationReport:
    """Summary of gold annotation generation."""

    generated: int
    skipped: int
    record_total: int
    rows: tuple[tuple[str, int, str], ...]  # (entry_id, record_count, status)


def generate_annotations(config: AnnotationConfig) -> AnnotationReport:
    """Generate gold alignment annotation files for the Benchmark A transport set."""
    rows: list[tuple[str, int, str]] = []
    generated = 0
    skipped = 0
    record_total = 0
    for entry_id in _entry_ids(config):
        gold_path = config.ground_truth_root / entry_id / "alignment_annotations.json"
        records = _build_gold_records(config.ground_truth_root, entry_id)
        record_total += len(records)
        if not records:
            rows.append((entry_id, 0, "no_gold_evidence"))
            skipped += 1
            continue
        if config.write:
            gold_path.parent.mkdir(parents=True, exist_ok=True)
            gold_path.write_text(
                json.dumps(
                    {"entry_id": entry_id, "records": [r.model_dump(mode="json") for r in records]},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            status = "written"
        else:
            status = "would_write"
        rows.append((entry_id, len(records), status))
        generated += 1
    return AnnotationReport(
        generated=generated,
        skipped=skipped,
        record_total=record_total,
        rows=tuple(rows),
    )


def _build_gold_records(root: Path, entry_id: str) -> list[EvidenceAlignmentRecord]:
    """Build gold alignment records for one entry from expected.json + extraction artifact."""
    expected = _load_expected(root, entry_id)
    if not expected:
        return []
    gold_values = _gold_values_by_field(expected)
    artifact = _load_artifact_track_values(root, entry_id)

    records: list[EvidenceAlignmentRecord] = []
    for field_id in SCORABLE_FIELDS:
        gold_value = gold_values.get(field_id)
        if not gold_value:
            continue
        original_value, translated_value = artifact.get(field_id, ("", ""))
        label, support, reason = _gold_label(field_id, gold_value, original_value, translated_value)
        records.append(
            EvidenceAlignmentRecord(
                entry_id=entry_id,
                field_id=field_id,
                original_value=original_value or None,
                translated_value=translated_value or None,
                normalized_value=gold_value,
                original_span_id="gold" if original_value else "",
                translated_span_id="gold" if translated_value else "",
                alignment_label=label,
                support_label=support,
                drift_reason=reason,
                confidence=1.0,
            )
        )
    return records


def _gold_label(
    field_id: str,
    gold_value: str,
    original_value: str,
    translated_value: str,
) -> tuple[EvidenceAlignmentLabel, EvidenceSupportLabel, str]:
    """Decide the gold alignment label from track coverage of the gold value."""
    has_original = bool(original_value)
    has_translated = bool(translated_value)
    if has_original and has_translated:
        return EvidenceAlignmentLabel.ALIGNED, EvidenceSupportLabel.SUPPORTS, "gold_value_recovered_both_tracks"
    if has_original or has_translated:
        return EvidenceAlignmentLabel.MISSING, EvidenceSupportLabel.INSUFFICIENT, "gold_value_single_track_only"
    return EvidenceAlignmentLabel.MISSING, EvidenceSupportLabel.INSUFFICIENT, "gold_value_not_recovered"


def _gold_values_by_field(expected: Mapping[str, Any]) -> dict[str, str]:
    """Map the scorable field_ids to their curated gold normalized value."""
    values: dict[str, str] = {}
    gene = str(expected.get("gene_symbol", "")).strip()
    disease = str(expected.get("disease_label", "")).strip()
    if gene:
        values["A.gene_symbol"] = gene.upper()
    if disease:
        values["A.disease_diagnosis"] = disease.casefold()
    relationship = _gold_relationship(expected)
    if relationship:
        values["A.gene_disease_relationship"] = relationship
    return values


def _gold_relationship(expected: Mapping[str, Any]) -> str:
    """Derive the gold gene-disease relationship direction from ClinGen classification."""
    classification = str(expected.get("classification", "")).strip().casefold()
    moi = str(expected.get("moi", "")).strip().casefold()
    if moi in _ASSOCIATION_TOKENS:
        return "susceptibility"
    if any(token in classification for token in _ASSOCIATION_TOKENS):
        return "susceptibility"
    if any(token in classification for token in _CAUSATIVE_TOKENS):
        return "causative"
    return "associated"


def _load_expected(root: Path, entry_id: str) -> Mapping[str, Any]:
    path = root / entry_id / "expected.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, Mapping) else {}


def _load_artifact_track_values(
    root: Path,
    entry_id: str,
) -> dict[str, tuple[str, str]]:
    """Load normalized original/translated values for the scorable fields."""
    path = root / entry_id / "preprocessed" / "phase_2" / "extraction_result.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        return {}
    out: dict[str, tuple[str, str]] = {}
    for field_id in SCORABLE_FIELDS:
        original = _track_value(payload.get("original_result"), field_id)
        translated = _track_value(payload.get("translated_result"), field_id)
        out[field_id] = (original, translated)
    return out


def _track_value(track_result: Any, field_id: str) -> str:
    if not isinstance(track_result, Mapping):
        return ""
    for item in track_result.get("evidence_items", []):
        if isinstance(item, Mapping) and item.get("field_id") == field_id:
            value = item.get("value")
            if value is None:
                return ""
            return str(value).strip()
    return ""


def _entry_ids(config: AnnotationConfig) -> tuple[str, ...]:
    if config.entry_ids:
        return tuple(config.entry_ids)
    selection_path = config.ground_truth_root / "selection.json"
    if selection_path.exists():
        raw = json.loads(selection_path.read_text(encoding="utf-8"))
        return tuple(str(item["entry_id"]) for item in raw if isinstance(item, Mapping) and item.get("entry_id"))
    return tuple(sorted(p.name for p in config.ground_truth_root.iterdir() if p.is_dir()))


def format_report(report: AnnotationReport) -> str:
    lines = [
        f"generated={report.generated} skipped={report.skipped} records={report.record_total}",
        "entry records status",
    ]
    for entry_id, count, status in report.rows:
        lines.append(f"{entry_id} {count} {status}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth-root", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--entries", nargs="*", default=())
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    config = AnnotationConfig(
        ground_truth_root=args.ground_truth_root,
        entry_ids=tuple(args.entries),
        limit=args.limit,
        write=args.write,
    )
    if config.limit is not None and not config.entry_ids:
        config = AnnotationConfig(
            ground_truth_root=config.ground_truth_root,
            entry_ids=_entry_ids(config)[: config.limit],
            limit=config.limit,
            write=config.write,
        )
    print(format_report(generate_annotations(config)))


if __name__ == "__main__":
    main()
