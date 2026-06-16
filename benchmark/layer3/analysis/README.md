# Layer 3 Analysis

> Offline report generators for BIBM Layer 3 benchmark tables, traceability checks, and multilingual evidence augmentation.

## Quick Start

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.alignment_metrics --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.evidence_augmentation_metrics --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.benchmark_readiness --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.select_benchmark_b_pilot --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.source_inventory --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.benchmark_b_phase2_queue --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.benchmark_b_phase2_sample_runner --limit 1 --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.select_expansion_entries --n 30 --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.expansion_artifact_coverage --write
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

### `benchmark_readiness.py`

| API | Signature | Description |
| --- | --- | --- |
| `BenchmarkReadinessConfig` | `BenchmarkReadinessConfig(ground_truth_root: Path = GROUND_TRUTH_DIR, reports_dir: Path = REPORTS_DIR, entry_ids: tuple[str, ...] = (), limit: int | None = None)` | Selects the frozen Benchmark A entries and output location. |
| `build_benchmark_readiness_report` | `build_benchmark_readiness_report(config: BenchmarkReadinessConfig) -> BenchmarkReadinessReport` | Reports annotated, invalid, and missing alignment-annotation coverage for the frozen N=30 set. |
| `write_benchmark_readiness_report` | `write_benchmark_readiness_report(report: BenchmarkReadinessReport, reports_dir: Path | None = None) -> Path` | Writes `benchmark_readiness_*.json`. |

### `select_benchmark_b_pilot.py`

| API | Signature | Description |
| --- | --- | --- |
| `BenchmarkBPilotSelectionConfig` | `BenchmarkBPilotSelectionConfig(selection_path: Path = GROUND_TRUTH_DIR / "selection.json", source_corpus_root: Path = SOURCE_CORPUS_ROOT, output_path: Path = GROUND_TRUTH_DIR / "benchmark_b_pilot_selection.json", target_size: int = 10)` | Selects the frozen multilingual pilot from the current source corpus. |
| `build_benchmark_b_pilot_selection` | `build_benchmark_b_pilot_selection(config: BenchmarkBPilotSelectionConfig) -> BenchmarkBPilotSelectionReport` | Deterministically freezes a multilingual N=10 pilot with source-language coverage metadata. |
| `write_benchmark_b_pilot_selection` | `write_benchmark_b_pilot_selection(report: BenchmarkBPilotSelectionReport, output_path: Path | None = None) -> Path` | Writes `benchmark_b_pilot_selection.json`. |

### `source_inventory.py`

| API | Signature | Description |
| --- | --- | --- |
| `SourceInventoryConfig` | `SourceInventoryConfig(repo_root: Path = Path(...), reports_dir: Path = REPORTS_DIR, clinvar_root: Path \| None = None, pipeline_input_root: Path \| None = None, rett_download_root: Path \| None = None, download_report_paths: tuple[Path, ...] = ())` | Configures the repo root, ClinVar anchor root, raw PDF roots, and optional acquisition reports used to enrich source metadata. |
| `build_source_inventory_report` | `build_source_inventory_report(config: SourceInventoryConfig) -> SourceInventoryReport` | Freezes a deterministic inventory for ClinVar structured anchors and `zh/ja/ko` raw PDFs with source database, URL, language, local path, SHA-256, access status, and annotation status. |
| `write_source_inventory_report` | `write_source_inventory_report(report: SourceInventoryReport, *, output_path: Path \| None = None, reports_dir: Path \| None = None) -> Path` | Writes `source_inventory_*.json` or a caller-provided output path. |

### `benchmark_b_phase2_queue.py`

| API | Signature | Description |
| --- | --- | --- |
| `BenchmarkBPhase2QueueConfig` | `BenchmarkBPhase2QueueConfig(selection_path: Path = GROUND_TRUTH_DIR / "selection.json", pilot_selection_path: Path = GROUND_TRUTH_DIR / "benchmark_b_pilot_selection.json", source_inventory_path: Path \| None = None, output_path: Path = GROUND_TRUTH_DIR / "benchmark_b_phase2_queue.json", allowed_languages: tuple[str, ...] = ("ja", "ko", "zh"))` | Configures the frozen pilot, source inventory, output path, and paper-facing multilingual languages. |
| `build_benchmark_b_phase2_queue` | `build_benchmark_b_phase2_queue(config: BenchmarkBPhase2QueueConfig) -> BenchmarkBPhase2QueueReport` | Joins the N=10 pilot with the source inventory and emits target-aware zh/ja/ko Phase 2 queue items. |
| `write_benchmark_b_phase2_queue` | `write_benchmark_b_phase2_queue(report: BenchmarkBPhase2QueueReport, output_path: Path \| None = None) -> Path` | Writes `benchmark_b_phase2_queue.json`. |

### `select_expansion_entries.py`

| API | Signature | Description |
| --- | --- | --- |
| `ExpansionSelectionConfig` | `ExpansionSelectionConfig(core_selection_path: Path = GROUND_TRUTH_DIR / "selection.json", source_csv_path: Path = CLINGEN_CSV, output_path: Path = GROUND_TRUTH_DIR / "expansion_selection_20260615.json", target_size: int = 30)` | Selects the Benchmark C expansion slice from the ClinGen CSV while excluding the frozen N=30 core. |
| `build_expansion_selection` | `build_expansion_selection(config: ExpansionSelectionConfig) -> ExpansionSelectionReport` | Builds a deterministic, diversity-scored expansion manifest with frozen ids and provenance. |
| `write_expansion_selection` | `write_expansion_selection(report: ExpansionSelectionReport, output_path: Path | None = None) -> Path` | Writes `expansion_selection_20260615.json`. |

### `expansion_artifact_coverage.py`

| API | Signature | Description |
| --- | --- | --- |
| `build_expansion_artifact_coverage` | `build_expansion_artifact_coverage(ground_truth_root: Path = GROUND_TRUTH_DIR, selection_path: Path | None = None) -> ExpansionArtifactCoverageReport` | Reports which frozen expansion ids already have usable Phase 2 artifacts. |
| `write_expansion_artifact_coverage` | `write_expansion_artifact_coverage(report: ExpansionArtifactCoverageReport, reports_dir: Path = REPORTS_DIR) -> Path` | Writes `expansion_artifact_coverage_*.json`. |

## Internal Design

`alignment_metrics` uses `alignment_annotations.json` as the only gold source for alignment labels. If an artifact already contains `alignment_records`, the module validates those records directly. If not, it derives field-level records from `original_result` and `translated_result` with `build_alignment_records`.

`evidence_augmentation_metrics` prefers `reconciled_result.evidence_items`. When no reconciled result exists, it falls back to the union of `original_result.evidence_items` and `translated_result.evidence_items`. It treats `article_language`, `evidence_source_language`, and `is_english` as the evidence source metadata used for English-only and non-English counts. Items with missing language metadata are counted as `unknown_language_evidence_count` and excluded from non-English yield and cross-language conflict counts.

`benchmark_readiness` reports whether the frozen Benchmark A entries have valid `alignment_annotations.json` files and surfaces invalid annotation payloads separately from missing files.

`select_benchmark_b_pilot` freezes a deterministic multilingual Benchmark B pilot from `benchmark/pipeline/input/ground_truth/<lang>/case_report/<entry_id>.pdf`, keeping only entries that have at least one non-English source PDF.

`source_inventory` freezes the source-provenance layer before any Benchmark B claim is made. It keeps ClinVar as `structured_anchor`, scans only the paper-facing multilingual languages (`zh`, `ja`, `ko`) under the configured raw-PDF roots, merges optional acquisition report metadata, and leaves unlabeled local PDFs outside scored denominators by marking them `unlabeled` or `spot_check`. Local pressure-test PDFs without acquisition report metadata use `source_database="local_pdf"` rather than inferring PubScholar, J-STAGE, or KoreaMed from language alone.

`benchmark_b_phase2_queue` is the bridge between source provenance and execution. It reads the frozen N=10 Benchmark B pilot, the raw source inventory, and `selection.json`, then queues only `zh/ja/ko` `case_report/<entry_id>.pdf` sources that can be mapped to target gene/disease metadata. It deliberately excludes `de/es/fr/pt/ru` and unlabeled non-case-report PDFs from the Phase 2 pilot queue.

`select_expansion_entries` reads the frozen N=30 core selection, excludes those report URLs from the ClinGen summary CSV, and freezes a separate expansion manifest with stable `clingen_030+` ids. It should remain deterministic and offline.

`expansion_artifact_coverage` reuses the Phase 2 artifact coverage machinery for the expansion manifest. It should report missing expansion source artifacts without trying to reconstruct or acquire them.

## Usage Patterns

Run a small smoke check without writing files:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.alignment_metrics --limit 2
```

Run a pilot augmentation report for selected cases:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.evidence_augmentation_metrics --entries case_001 case_002 --write
```

Freeze the current raw-source inventory with existing acquisition report metadata:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.source_inventory \
  --download-report benchmark/literature_acquisition/downloads/report_260520.json \
  --write
```

Freeze the Benchmark B Phase 2 queue after a source inventory exists:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.benchmark_b_phase2_queue \
  --source-inventory-path benchmark/layer3/reports/source_inventory_20260616_095316.json \
  --write
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

Benchmark A readiness is intentionally conservative: if annotation files are missing or malformed, the report should say so instead of borrowing `expected.json`.

Benchmark B pilot selection is a frozen offline snapshot. Keep the output file in `benchmark/layer3/ground_truth/` and do not re-randomize it during later report generation.

Source inventories are provenance artifacts, not scoring artifacts. Do not count `unlabeled` or `spot_check` raw PDFs in a metric denominator until a separate gold annotation file has been frozen for that subset.

Phase 2 queues are execution manifests, not gold labels. They define which raw PDFs should be processed next, while scoring still requires accepted evidence items and source-valid spans.

## Performance Notes

The modules load JSON artifacts entry by entry and keep only aggregate dataclasses in memory. This is sufficient for the current N=30 benchmark and small Benchmark B pilots. If the dataset grows substantially, stream per-entry payloads to report rows instead of accumulating full per-case objects.

`source_inventory` streams file hashing in 1 MiB chunks, so it can scan large ClinVar and PDF files without loading them fully into memory.

## Dependencies

| Dependency | Purpose |
| --- | --- |
| `benchmark.layer3.evaluate` | Shared `GROUND_TRUTH_DIR` and `REPORTS_DIR`. |
| `EvidenceAlignmentRecord` | Typed alignment schema used by annotations and artifacts. |
| `build_alignment_records` | Deterministic fallback when artifacts do not yet persist alignment records. |
| `hashlib` | SHA-256 provenance hashing for local source files. |
| `benchmark_b_pilot_selection.json` | Frozen N=10 Benchmark B case list consumed by the Phase 2 queue builder. |

## Testing

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_alignment_metrics.py backend/tests/benchmark/layer3/test_evidence_augmentation_metrics.py
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check benchmark/layer3/analysis/alignment_metrics.py benchmark/layer3/analysis/evidence_augmentation_metrics.py
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_source_inventory.py
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check benchmark/layer3/analysis/source_inventory.py backend/tests/benchmark/layer3/test_source_inventory.py
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_benchmark_b_phase2_queue.py
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check benchmark/layer3/analysis/benchmark_b_phase2_queue.py backend/tests/benchmark/layer3/test_benchmark_b_phase2_queue.py
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.benchmark_b_phase2_sample_runner --limit 1 --write
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_benchmark_b_phase2_sample_runner.py
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check benchmark/layer3/analysis/benchmark_b_phase2_sample_runner.py backend/tests/benchmark/layer3/test_benchmark_b_phase2_sample_runner.py
```
