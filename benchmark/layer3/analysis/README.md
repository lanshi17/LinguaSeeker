# Layer 3 Analysis

> **Status: DEPRECATED SHIM.** This package (`benchmark/layer3/analysis/`) contains only
> backward-compatible import shims after the 2026-06-18 framework refactor.
> All analysis modules now live under `benchmark.analysis.*` in thematic subgroups.
> The shims will be removed in Phase 6 of the refactor.

Offline report generators for BIBM Layer 3 benchmark tables, traceability checks, and multilingual evidence augmentation.

## New Module Locations

The legacy flat `benchmark.layer3.analysis.<name>` imports are preserved as shims. New code MUST import from the canonical locations below.

### Dataset Curation (`benchmark.analysis.dataset_curation`)

| Old name | New path | Purpose |
|----------|----------|---------|
| `alignment_metrics` | `benchmark.analysis.dataset_curation.alignment_metrics` | Alignment annotation accuracy |
| `alignment_annotation_protocol` | `benchmark.analysis.dataset_curation.alignment_annotation_protocol` | Annotation protocol definitions |
| `generate_alignment_annotations` | `benchmark.analysis.dataset_curation.generate_alignment_annotations` | Generate alignment annotation files |
| `evidence_augmentation_metrics` | `benchmark.analysis.dataset_curation.evidence_augmentation_metrics` | English-only vs multilingual evidence matrices |
| `benchmark_readiness` | `benchmark.analysis.dataset_curation.readiness` | Frozen Benchmark A annotation coverage |
| `source_inventory` | `benchmark.analysis.dataset_curation.source_inventory` | ClinVar anchor + multilingual PDF inventory |
| `select_expansion_entries` | `benchmark.analysis.dataset_curation.select_expansion` | Benchmark C expansion slice selection |
| `expansion_artifact_coverage` | `benchmark.analysis.dataset_curation.expansion_artifact_coverage` | Expansion Phase 2 artifact coverage |
| `leakage_check` | `benchmark.analysis.dataset_curation.leakage_check` | Data leakage detection |
| `inventory_system_runs` | `benchmark.analysis.dataset_curation.inventory_system_runs` | System run inventory |
| `phase2_artifact_coverage` | `benchmark.analysis.dataset_curation.phase2_artifact_coverage` | Phase 2 artifact coverage |
| `materialize_phase2_artifacts` | `benchmark.analysis.dataset_curation.materialize_phase2_artifacts` | Materialize Phase 2 artifacts |
| `report_from_system_runs` | `benchmark.analysis.dataset_curation.report_from_system_runs` | Report generation from system runs |

### Benchmark B (`benchmark.analysis.benchmark_b`)

| Old name | New path | Purpose |
|----------|----------|---------|
| `select_benchmark_b_pilot` | `benchmark.analysis.benchmark_b.pilot_selection` | Freeze multilingual N=10 pilot |
| `benchmark_b_phase2_queue` | `benchmark.analysis.benchmark_b.phase2_queue` | Queue zh/ja/ko Phase 2 items |
| `benchmark_b_phase2_runtime_metrics` | `benchmark.analysis.benchmark_b.phase2_runtime_metrics` | Phase 2 runtime performance metrics |

### Reconcile (`benchmark.analysis.reconcile`)

| Old name | New path | Purpose |
|----------|----------|---------|
| `reconcile_ablation` | `benchmark.analysis.reconcile.ablation` | Reconcile ablation studies |
| `reconcile_case_studies` | `benchmark.analysis.reconcile.case_studies` | Reconcile case studies |
| `reconcile_oracle_upper_bound` | `benchmark.analysis.reconcile.oracle_upper_bound` | Oracle upper bound analysis |
| `contextual_reconcile_diagnosis` | `benchmark.analysis.reconcile.contextual_diagnosis` | Contextual reconcile diagnosis |

### Traceability (`benchmark.analysis.traceability`)

| Old name | New path | Purpose |
|----------|----------|---------|
| `traceability_metrics` | `benchmark.analysis.traceability.metrics` | Traceability metric reports |

### Arbitrator (`benchmark.analysis.arbitrator`)

| Old name | New path | Purpose |
|----------|----------|---------|
| `arbitrator_dataset` | `benchmark.analysis.arbitrator.dataset` | Arbitrator dataset builder |
| `arbitrator_policy_eval` | `benchmark.analysis.arbitrator.policy_eval` | Arbitrator policy evaluation |

### Baselines (`benchmark.analysis.baselines`)

| Old name | New path | Purpose |
|----------|----------|---------|
| `prompt_model_baseline_tables` | `benchmark.analysis.baselines.prompt_model_baseline_tables` | Prompt/model baseline summary tables |
| `naive_llm` | `benchmark.analysis.baselines.naive_llm` | Naive LLM baseline |
| `translate_then_extract` | `benchmark.analysis.baselines.translate_then_extract` | Translate-then-extract baseline |
| `original_only` | `benchmark.analysis.baselines.original_only` | Original-only baseline |
| `rag_llm` | `benchmark.analysis.baselines.rag_llm` | RAG LLM baseline |
| `single_agent_cot` | `benchmark.analysis.baselines.single_agent_cot` | Single-agent CoT baseline |
| `prompt_model_sweep` | `benchmark.analysis.baselines.prompt_model_sweep` | Prompt/model sweep |

### Diagnostics (`benchmark.analysis.diagnostics`)

| Old name | New path | Purpose |
|----------|----------|---------|
| `diagnose_baselines` | `benchmark.analysis.diagnostics.baselines` | Baseline diagnostics |
| `diagnose_block_recall` | `benchmark.analysis.diagnostics.block_recall` | Block recall diagnostics |
| `diagnose_extraction` | `benchmark.analysis.diagnostics.extraction` | Extraction diagnostics |
| `diagnose_reconcile_errors` | `benchmark.analysis.diagnostics.reconcile_errors` | Reconcile error diagnostics |

### Paper Artifacts (`benchmark.analysis.paper_artifacts`)

| Old name | New path | Purpose |
|----------|----------|---------|
| `g1_decision` | `benchmark.analysis.paper_artifacts.g1_decision` | G1 decision tables |
| `g2_statistics` | `benchmark.analysis.paper_artifacts.g2_statistics` | G2 statistics tables |
| `main_paper_tables` | `benchmark.analysis.paper_artifacts.main_paper_tables` | Main paper tables |
| `main_paper_rescue_manifest` | `benchmark.analysis.paper_artifacts.main_paper_rescue_manifest` | Rescue manifest |

### Runners (moved out of analysis)

| Old name | New path | Purpose |
|----------|----------|---------|
| `run_phase2_artifact_batch` | `benchmark.runners.phase2_batch` | Phase 2 artifact batch runner |
| `benchmark_b_phase2_sample_runner` | `benchmark.runners.benchmark_b_phase2_sample` | Benchmark B Phase 2 sample runner |

## Quick Start

All commands below use the **new canonical** import paths. The deprecated `benchmark.layer3.analysis.*` shims still work but emit `DeprecationWarning`.

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.analysis.dataset_curation.alignment_metrics --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.analysis.dataset_curation.evidence_augmentation_metrics --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.analysis.dataset_curation.readiness --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.analysis.benchmark_b.pilot_selection --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.analysis.dataset_curation.source_inventory --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.analysis.benchmark_b.phase2_queue --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.runners.benchmark_b_phase2_sample --limit 1 --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.analysis.dataset_curation.select_expansion --n 30 --write
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.analysis.dataset_curation.expansion_artifact_coverage --write
```

## Architecture

```text
data/ground_truth/clingen/selection.json
  -> per-entry expected files and phase_2/extraction_result.json
  -> analysis module (under benchmark.analysis.*)
  -> typed dataclass report
  -> data/reports/{group}/*.json
```

The analysis modules are intentionally offline. They read frozen Layer 3 artifacts from `benchmark/data/ground_truth`, compute deterministic metrics, and optionally write JSON reports under `benchmark/data/reports`.

Report output is second-level bucketed by group:

| Report group | Path | Contents |
|---|---|---|
| `eval` | `data/reports/eval/` | End-to-end evaluation reports |
| `reconcile` | `data/reports/reconcile/` | Reconcile ablations & case studies |
| `baseline` | `data/reports/baseline/` | LLM baseline reports & summary tables |
| `traceability` | `data/reports/traceability/` | Traceability metric reports |
| `benchmark_b` | `data/reports/benchmark_b/` | Multilingual pilot Phase 2 outputs |
| `curation` | `data/reports/curation/` | Dataset curation / readiness / inventory |
| `paper` | `data/reports/paper/` | Paper-specific tables & rescue manifests |
| `diagnostics` | `data/reports/diagnostics/` | diagnose_* outputs |
| `clinvar_fused` | `data/reports/clinvar_fused/` | Fused-dataset eval reports |
| `pipeline_e2e` | `data/reports/pipeline_e2e/` | HTTP pipeline benchmark runs |

## Public API

### `alignment_metrics.py` (`benchmark.analysis.dataset_curation.alignment_metrics`)

| API | Signature | Description |
| --- | --- | --- |
| `AlignmentMetricConfig` | `AlignmentMetricConfig(ground_truth_root: Path, reports_dir: Path, entry_ids: tuple, limit: int | None)` | Selects entries and output location. |
| `build_alignment_metric_report` | `build_alignment_metric_report(config) -> AlignmentMetricReport` | Compares gold `alignment_annotations.json` with predicted or derived `EvidenceAlignmentRecord` values. |
| `write_alignment_metric_report` | `write_alignment_metric_report(report, reports_dir) -> Path` | Writes `alignment_metrics_*.json`. |

### `evidence_augmentation_metrics.py` (`benchmark.analysis.dataset_curation.evidence_augmentation_metrics`)

| API | Signature | Description |
| --- | --- | --- |
| `AugmentationMetricConfig` | `AugmentationMetricConfig(ground_truth_root: Path, reports_dir: Path, entry_ids: tuple, limit: int | None)` | Selects variant / gene-disease cases and output location. |
| `build_evidence_augmentation_report` | `build_evidence_augmentation_report(config) -> EvidenceAugmentationReport` | Builds English-only vs multilingual evidence matrices from Phase 2 artifacts. |
| `write_evidence_augmentation_report` | `write_evidence_augmentation_report(report, reports_dir) -> Path` | Writes `evidence_augmentation_metrics_*.json`. |

### `readiness.py` (`benchmark.analysis.dataset_curation.readiness`)

| API | Signature | Description |
| --- | --- | --- |
| `BenchmarkReadinessConfig` | `BenchmarkReadinessConfig(ground_truth_root: Path, reports_dir: Path, entry_ids: tuple, limit: int | None)` | Selects the frozen Benchmark A entries and output location. |
| `build_benchmark_readiness_report` | `build_benchmark_readiness_report(config) -> BenchmarkReadinessReport` | Reports annotated, invalid, and missing alignment-annotation coverage for the frozen N=30 set. |
| `write_benchmark_readiness_report` | `write_benchmark_readiness_report(report, reports_dir) -> Path` | Writes `benchmark_readiness_*.json`. |

### `pilot_selection.py` (`benchmark.analysis.benchmark_b.pilot_selection`)

| API | Signature | Description |
| --- | --- | --- |
| `BenchmarkBPilotSelectionConfig` | `BenchmarkBPilotSelectionConfig(selection_path, source_corpus_root, output_path, target_size)` | Selects the frozen multilingual pilot from the current source corpus. |
| `build_benchmark_b_pilot_selection` | `build_benchmark_b_pilot_selection(config) -> BenchmarkBPilotSelectionReport` | Deterministically freezes a multilingual N=10 pilot with source-language coverage metadata. |
| `write_benchmark_b_pilot_selection` | `write_benchmark_b_pilot_selection(report, output_path) -> Path` | Writes `benchmark_b_pilot_selection.json`. |

### `source_inventory.py` (`benchmark.analysis.dataset_curation.source_inventory`)

| API | Signature | Description |
| --- | --- | --- |
| `SourceInventoryConfig` | `SourceInventoryConfig(repo_root, reports_dir, clinvar_root, pipeline_input_root, rett_download_root, download_report_paths)` | Configures the repo root, ClinVar anchor root, raw PDF roots, and optional acquisition reports used to enrich source metadata. |
| `build_source_inventory_report` | `build_source_inventory_report(config) -> SourceInventoryReport` | Freezes a deterministic inventory for ClinVar structured anchors and `zh/ja/ko` raw PDFs with source database, URL, language, local path, SHA-256, access status, and annotation status. |
| `write_source_inventory_report` | `write_source_inventory_report(report, output_path, reports_dir) -> Path` | Writes `source_inventory_*.json` or a caller-provided output path. |

### `phase2_queue.py` (`benchmark.analysis.benchmark_b.phase2_queue`)

| API | Signature | Description |
| --- | --- | --- |
| `BenchmarkBPhase2QueueConfig` | `BenchmarkBPhase2QueueConfig(selection_path, pilot_selection_path, source_inventory_path, output_path, allowed_languages)` | Configures the frozen pilot, source inventory, output path, and paper-facing multilingual languages. |
| `build_benchmark_b_phase2_queue` | `build_benchmark_b_phase2_queue(config) -> BenchmarkBPhase2QueueReport` | Joins the N=10 pilot with the source inventory and emits target-aware zh/ja/ko Phase 2 queue items. |
| `write_benchmark_b_phase2_queue` | `write_benchmark_b_phase2_queue(report, output_path) -> Path` | Writes `benchmark_b_phase2_queue.json`. |

### `select_expansion.py` (`benchmark.analysis.dataset_curation.select_expansion`)

| API | Signature | Description |
| --- | --- | --- |
| `ExpansionSelectionConfig` | `ExpansionSelectionConfig(core_selection_path, source_csv_path, output_path, target_size)` | Selects the Benchmark C expansion slice from the ClinGen CSV while excluding the frozen N=30 core. |
| `build_expansion_selection` | `build_expansion_selection(config) -> ExpansionSelectionReport` | Builds a deterministic, diversity-scored expansion manifest with frozen ids and provenance. |
| `write_expansion_selection` | `write_expansion_selection(report, output_path) -> Path` | Writes `expansion_selection_*.json`. |

### `expansion_artifact_coverage.py` (`benchmark.analysis.dataset_curation.expansion_artifact_coverage`)

| API | Signature | Description |
| --- | --- | --- |
| `build_expansion_artifact_coverage` | `build_expansion_artifact_coverage(ground_truth_root, selection_path) -> ExpansionArtifactCoverageReport` | Reports which frozen expansion ids already have usable Phase 2 artifacts. |
| `write_expansion_artifact_coverage` | `write_expansion_artifact_coverage(report, reports_dir) -> Path` | Writes `expansion_artifact_coverage_*.json`. |

## Internal Design

`alignment_metrics` uses `alignment_annotations.json` as the only gold source for alignment labels. If an artifact already contains `alignment_records`, the module validates those records directly. If not, it derives field-level records from `original_result` and `translated_result` with `build_alignment_records`.

`evidence_augmentation_metrics` prefers `reconciled_result.evidence_items`. When no reconciled result exists, it falls back to the union of `original_result.evidence_items` and `translated_result.evidence_items`. It treats `article_language`, `evidence_source_language`, and `is_english` as the evidence source metadata used for English-only and non-English counts. Items with missing language metadata are counted as `unknown_language_evidence_count` and excluded from non-English yield and cross-language conflict counts.

`readiness` (formerly `benchmark_readiness`) reports whether the frozen Benchmark A entries have valid `alignment_annotations.json` files and surfaces invalid annotation payloads separately from missing files.

`pilot_selection` (formerly `select_benchmark_b_pilot`) freezes a deterministic multilingual Benchmark B pilot from `benchmark/pipeline/input/ground_truth/<lang>/case_report/<entry_id>.pdf`, keeping only entries that have at least one non-English source PDF.

`source_inventory` freezes the source-provenance layer before any Benchmark B claim is made. It keeps ClinVar as `structured_anchor`, scans only the paper-facing multilingual languages (`zh`, `ja`, `ko`) under the configured raw-PDF roots, merges optional acquisition report metadata, and leaves unlabeled local PDFs outside scored denominators by marking them `unlabeled` or `spot_check`. Local pressure-test PDFs without acquisition report metadata use `source_database="local_pdf"` rather than inferring PubScholar, J-STAGE, or KoreaMed from language alone.

`phase2_queue` (formerly `benchmark_b_phase2_queue`) is the bridge between source provenance and execution. It reads the frozen N=10 Benchmark B pilot, the raw source inventory, and `selection.json`, then queues only `zh/ja/ko` `case_report/<entry_id>.pdf` sources that can be mapped to target gene/disease metadata. It deliberately excludes `de/es/fr/pt/ru` and unlabeled non-case-report PDFs from the Phase 2 pilot queue.

`select_expansion` reads the frozen N=30 core selection, excludes those report URLs from the ClinGen summary CSV, and freezes a separate expansion manifest with stable `clingen_030+` ids. It should remain deterministic and offline.

`expansion_artifact_coverage` reuses the Phase 2 artifact coverage machinery for the expansion manifest. It should report missing expansion source artifacts without trying to reconstruct or acquire them.

## Usage Patterns

Run a small smoke check without writing files:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.analysis.dataset_curation.alignment_metrics --limit 2
```

Run a pilot augmentation report for selected cases:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.analysis.dataset_curation.evidence_augmentation_metrics --entries case_001 case_002 --write
```

Freeze the current raw-source inventory with existing acquisition report metadata:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.analysis.dataset_curation.source_inventory \
  --download-report benchmark/runners/downloads/report_260520.json \
  --write
```

Freeze the Benchmark B Phase 2 queue after a source inventory exists:

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.analysis.benchmark_b.phase2_queue \
  --source-inventory-path benchmark/data/reports/curation/source_inventory_20260616_095316.json \
  --write
```

Use the Python API in tests:

```python
from benchmark.analysis.dataset_curation.alignment_metrics import AlignmentMetricConfig, build_alignment_metric_report

report = build_alignment_metric_report(AlignmentMetricConfig(limit=10))
print(report.overall.alignment_accuracy)
```

## Extension Guide

Add new alignment labels in `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py`, then update `reconcile/alignment.py` and `alignment_metrics.py` together. Keep gold labels in `alignment_annotations.json`; do not read `expected.json` for alignment gold.

Add new augmentation categories by extending `_potential_acmg_types` in `evidence_augmentation_metrics.py`. The output should remain evidence-category only and must not claim autonomous ACMG classification.

Benchmark A readiness is intentionally conservative: if annotation files are missing or malformed, the report should say so instead of borrowing `expected.json`.

Benchmark B pilot selection is a frozen offline snapshot. Keep the output file in `benchmark/data/ground_truth/` and do not re-randomize it during later report generation.

Source inventories are provenance artifacts, not scoring artifacts. Do not count `unlabeled` or `spot_check` raw PDFs in a metric denominator until a separate gold annotation file has been frozen for that subset.

Phase 2 queues are execution manifests, not gold labels. They define which raw PDFs should be processed next, while scoring still requires accepted evidence items and source-valid spans.

## Performance Notes

The modules load JSON artifacts entry by entry and keep only aggregate dataclasses in memory. This is sufficient for the current N=30 benchmark and small Benchmark B pilots. If the dataset grows substantially, stream per-entry payloads to report rows instead of accumulating full per-case objects.

`source_inventory` streams file hashing in 1 MiB chunks, so it can scan large ClinVar and PDF files without loading them fully into memory.

## Dependencies

| Dependency | Purpose |
| --- | --- |
| `benchmark.core` | Shared `GROUND_TRUTH_ROOT`, `REPORTS_ROOT`, `FieldMatch`, `EntryMetrics`. |
| `EvidenceAlignmentRecord` | Typed alignment schema used by annotations and artifacts. |
| `build_alignment_records` | Deterministic fallback when artifacts do not yet persist alignment records. |
| `hashlib` | SHA-256 provenance hashing for local source files. |
| `benchmark_b_pilot_selection.json` | Frozen N=10 Benchmark B case list consumed by the Phase 2 queue builder. |

## Testing

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_alignment_metrics.py backend/tests/benchmark/layer3/test_evidence_augmentation_metrics.py
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check benchmark/analysis/dataset_curation/alignment_metrics.py benchmark/analysis/dataset_curation/evidence_augmentation_metrics.py
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_source_inventory.py
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check benchmark/analysis/dataset_curation/source_inventory.py backend/tests/benchmark/layer3/test_source_inventory.py
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_benchmark_b_phase2_queue.py
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check benchmark/analysis/benchmark_b/phase2_queue.py backend/tests/benchmark/layer3/test_benchmark_b_phase2_queue.py
PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.runners.benchmark_b_phase2_sample --limit 1 --write
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_benchmark_b_phase2_sample_runner.py
PYTHONPATH=.:backend uv run --project backend --no-sync ruff check benchmark/runners/benchmark_b_phase2_sample.py backend/tests/benchmark/layer3/test_benchmark_b_phase2_sample_runner.py
```
