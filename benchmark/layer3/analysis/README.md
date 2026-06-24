# Layer 3 Analysis

> **Status: DEPRECATED SHIM.** This package (`benchmark/layer3/analysis/`) contains only
> backward-compatible import shims after the 2026-06-18 framework refactor.
> All analysis modules now live under `benchmark.analysis.*` in thematic subgroups.
> The shims will be removed in Phase 6 of the refactor.

Offline report generators for BIBM Layer 3 benchmark tables, traceability checks, multilingual evidence augmentation, diagnostics, and paper artifacts.

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

All commands use the **canonical** import paths. The deprecated shims still work but emit `DeprecationWarning`.

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

Analysis modules are intentionally offline. They read frozen artifacts from `benchmark/data/ground_truth`, compute deterministic metrics, and optionally write JSON reports under `benchmark/data/reports`.

## Report Output Groups

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

## Testing

```bash
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_alignment_metrics.py backend/tests/benchmark/layer3/test_evidence_augmentation_metrics.py
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_source_inventory.py
PYTHONPATH=.:backend uv run --project backend --no-sync pytest backend/tests/benchmark/layer3/test_benchmark_b_phase2_queue.py
```
