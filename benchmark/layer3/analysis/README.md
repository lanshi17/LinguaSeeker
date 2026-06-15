# Layer 3 Analysis

> Offline report generators for BIBM Layer 3 benchmark tables, traceability checks, and multilingual evidence augmentation.

## Quick Start

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.alignment_metrics --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.evidence_augmentation_metrics --write
```

## Architecture

```text
ground_truth/selection.json
  -> per-entry expected files and phase_2/extraction_result.json
  -> analysis module
  -> typed dataclass report
  -> reports/*.json
```

The analysis modules are intentionally offline. They read frozen Layer 3 artifacts from `benchmark/layer3/ground_truth`, compute deterministic metrics, and optionally write JSON reports under `benchmark/layer3/reports`.

## Public API

### `alignment_metrics.py`

| API | Signature | Description |
| --- | --- | --- |
| `AlignmentMetricConfig` | `AlignmentMetricConfig(ground_truth_root: Path = GROUND_TRUTH_DIR, reports_dir: Path = REPORTS_DIR, entry_ids: tuple[str, ...] = (), limit: int | None = None)` | Selects entries and output location. |
| `build_alignment_metric_report` | `build_alignment_metric_report(config: AlignmentMetricConfig) -> AlignmentMetricReport` | Compares gold `alignment_annotations.json` records with predicted or derived `EvidenceAlignmentRecord` values. |
| `write_alignment_metric_report` | `write_alignment_metric_report(report: AlignmentMetricReport, reports_dir: Path | None = None) -> Path` | Writes `alignment_metrics_*.json`. |

### `evidence_augmentation_metrics.py`

| API | Signature | Description |
| --- | --- | --- |
| `AugmentationMetricConfig` | `AugmentationMetricConfig(ground_truth_root: Path = GROUND_TRUTH_DIR, reports_dir: Path = REPORTS_DIR, entry_ids: tuple[str, ...] = (), limit: int | None = None)` | Selects variant / gene-disease cases and output location. |
| `build_evidence_augmentation_report` | `build_evidence_augmentation_report(config: AugmentationMetricConfig) -> EvidenceAugmentationReport` | Builds English-only vs multilingual evidence matrices from Phase 2 artifacts. |
| `write_evidence_augmentation_report` | `write_evidence_augmentation_report(report: EvidenceAugmentationReport, reports_dir: Path | None = None) -> Path` | Writes `evidence_augmentation_metrics_*.json`. |

## Internal Design

`alignment_metrics` uses `alignment_annotations.json` as the only gold source for alignment labels. If an artifact already contains `alignment_records`, the module validates those records directly. If not, it derives field-level records from `original_result` and `translated_result` with `build_alignment_records`.

`evidence_augmentation_metrics` prefers `reconciled_result.evidence_items`. When no reconciled result exists, it falls back to the union of `original_result.evidence_items` and `translated_result.evidence_items`. It treats `article_language`, `evidence_source_language`, and `is_english` as the evidence source metadata used for English-only and non-English counts.

## Usage Patterns

Run a small smoke check without writing files:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.alignment_metrics --limit 2
```

Run a pilot augmentation report for selected cases:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.evidence_augmentation_metrics --entries case_001 case_002 --write
```

Use the Python API in tests:

```python
from benchmark.layer3.analysis.alignment_metrics import AlignmentMetricConfig, build_alignment_metric_report

report = build_alignment_metric_report(AlignmentMetricConfig(limit=10))
print(report.overall.alignment_accuracy)
```

## Extension Guide

Add new alignment labels in `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py`, then update `reconcile/alignment.py` and `alignment_metrics.py` together. Keep gold labels in `alignment_annotations.json`; do not read `expected.json` for alignment gold.

Add new augmentation categories by extending `_potential_acmg_types` in `evidence_augmentation_metrics.py`. The output should remain evidence-category only and must not claim autonomous ACMG classification.

## Performance Notes

The modules load JSON artifacts entry by entry and keep only aggregate dataclasses in memory. This is sufficient for the current N=30 benchmark and small Benchmark B pilots. If the dataset grows substantially, stream per-entry payloads to report rows instead of accumulating full per-case objects.

## Dependencies

| Dependency | Purpose |
| --- | --- |
| `benchmark.layer3.evaluate` | Shared `GROUND_TRUTH_DIR` and `REPORTS_DIR`. |
| `EvidenceAlignmentRecord` | Typed alignment schema used by annotations and artifacts. |
| `build_alignment_records` | Deterministic fallback when artifacts do not yet persist alignment records. |

## Testing

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_alignment_metrics.py backend/tests/benchmark/layer3/test_evidence_augmentation_metrics.py
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check benchmark/layer3/analysis/alignment_metrics.py benchmark/layer3/analysis/evidence_augmentation_metrics.py
```
