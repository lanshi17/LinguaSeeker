# Benchmark Framework

Benchmark suite for the Lingua Seeker evidence extraction pipeline. Covers literature acquisition, cross-lingual evidence extraction, entity standardization, and pipeline end-to-end evaluation.

## Directory Layout

```
benchmark/
├── core/              Shared primitives: contracts, matching, aggregate, paths, pdf,
│                      pipeline_client, evidence_metrics, field_normalize, mondo_hierarchy
├── config/            Centralized configuration: Ansible-managed file configs + runtime defaults
├── datasets/          Dataset-specific assembly + evaluators
│   ├── clingen/       ClinGen entries + Rett curation
│   ├── clinvar_fused/ ClinVar-fused variants (Dataset 2)
│   ├── parkinson_literature/  Parkinson XLSX workbook curation + PDF fetching
│   └── rett_annotation/       MinerU-driven annotation toolkit (independent uv project)
├── runners/           Experiment entry points that hit pipelines / providers / LLMs
├── analysis/          Offline reporters organized by theme
│   ├── reconcile/     Ablation, case studies, oracle bound, contextual diagnosis
│   ├── traceability/  Citation validity / span boundary / traceable F1
│   ├── baselines/     B0..B10 LLM baselines + prompt-only sweeps + summary tables
│   ├── arbitrator/    Arbitrator dataset + policy evaluator
│   ├── benchmark_b/   Multilingual pilot selection + Phase 2 metrics
│   ├── dataset_curation/  Readiness, source inventory, expansion, alignment, leakage
│   ├── paper_artifacts/   Paper-specific tables (G1/G2/main paper/rescue)
│   └── diagnostics/   Grounding, native gain, extraction, baselines, block recall, reconcile errors
├── layer3/            DEPRECATED SHIM: redirects to core/datasets/runners/analysis (Phase 6 removal)
├── literature_acquisition/  DEPRECATED SHIM: redirects to runners (Phase 6 removal)
├── pipeline/          DEPRECATED SHIM + test PDFs + reports (runner moved to runners/)
├── annotation/        Legacy annotation data (source PDFs + markdown)
├── optimization/      Prompt optimization experiments (fused75 ablations, adjudication)
├── scripts/           Benchmark utility scripts
├── data/              All artifacts (gitignored where appropriate)
│   ├── ground_truth/  {unified, clingen, clinvar_fused, rett, parkinson}
│   ├── inputs/        {pipeline, literature_acquisition}
│   └── reports/       {eval, reconcile, traceability, baseline, benchmark_b,
│                       curation, paper, diagnostics, clinvar_fused, pipeline_e2e}
└── README.md
```

## Stable Imports

Cross-cutting primitives live in `benchmark.core`:

```python
from benchmark.core import (
    FieldMatch, EntryMetrics,
    compare_evidence, fuzzy_match_value, normalize_comparison_text,
    compute_aggregate_metrics,
    GROUND_TRUTH_ROOT, GROUND_TRUTH_UNIFIED_ROOT, GROUND_TRUTH_CLINGEN_ROOT,
    REPORTS_ROOT, RAW_PDF_ROOT,
    submit_and_poll, evaluate_one, run_evaluation,
)
```

`GROUND_TRUTH_ROOT` points to the **unified** dataset (150 entries) by default.
Legacy dataset roots (`GROUND_TRUTH_CLINGEN_ROOT`, etc.) remain available for
dataset-specific analysis tools.

## Common Entry Points

| Goal | Command |
|------|---------|
| Run unified benchmark (default) | `python -m benchmark.layer3.evaluate --help` |
| Run unified benchmark (shard) | `python -m benchmark.layer3.evaluate --shard-index 0 --shard-size 10` |
| Run unified benchmark (subset) | `python -m benchmark.layer3.evaluate --entries gs_000 gs_001 gs_002` |
| Run legacy ClinGen eval | `python -m benchmark.layer3.evaluate --ground-truth-root benchmark/data/ground_truth/clingen` |
| Run pipeline benchmark | `python -m benchmark.runners.pipeline_e2e --help` |
| Download literature | `python -m benchmark.runners.literature_acquisition download --help` |
| Rett literature pipeline | `python -m benchmark.runners.literature_rett --help` |
| ClinVar fused selection | `python -m benchmark.datasets.clinvar_fused.select_fused_entries` |
| ClinVar fused evaluation | `python -m benchmark.datasets.clinvar_fused.evaluate_fused --write` |
| Build paper tables | `python -m benchmark.analysis.paper_artifacts.main_paper_tables --help` |
| Pilot selection | `python -m benchmark.analysis.benchmark_b.pilot_selection --help` |
| Grounding diagnostics | `python -m benchmark.analysis.diagnostics.grounding` |

## Configuration

Two complementary mechanisms in `benchmark/config/`:

- **Ansible** renders tunable/secret config files into consumer locations (Rett annotation config, acquisition configs)
- **`defaults.py`** is the canonical source for runtime code constants (pipeline URL, status sets, filter thresholds, seed queries)

See `benchmark/config/README.md` for full documentation.

## Deprecation Shims

The 2026-06-18 refactor preserved every legacy dotted path while the codebase caught up. Imports under these prefixes still resolve but emit `DeprecationWarning`:

| Legacy prefix | New location |
|---------------|-------------|
| `benchmark.layer3.evaluate` | `benchmark.core` |
| `benchmark.layer3.mondo_hierarchy` | `benchmark.core.mondo_hierarchy` |
| `benchmark.layer3.analysis.<x>` | `benchmark.analysis.<group>.<module>` |
| `benchmark.layer3.baselines.<x>` | `benchmark.analysis.baselines.<x>` |
| `benchmark.layer3.{select_entries,fetch_literature,...}` | `benchmark.datasets.clingen.*` / `benchmark.runners.clingen_preprocess` |
| `benchmark.layer3.clinvar_fused.<x>` | `benchmark.datasets.clinvar_fused.<x>` |
| `benchmark.pipeline.benchmark` | `benchmark.runners.pipeline_e2e` |
| `benchmark.pipeline.evidence_metrics` | `benchmark.core.evidence_metrics` |
| `benchmark.literature_acquisition.{benchmark,rett_download}` | `benchmark.runners.{literature_acquisition,literature_rett}` |
| `benchmark.annotation.<x>` | `benchmark.datasets.rett_annotation.<x>` |

All shims are scheduled for removal in Phase 6.

## Datasets

### Unified Gold-Standard Dataset (Default)

**The default benchmark dataset since 2026-06-25.** Schema-unified superset of all four source datasets. 150 entries under `benchmark/data/ground_truth/unified/gs_NNN/`. `GROUND_TRUTH_ROOT` points here by default.

Schema-unified superset of the four source datasets, materialized under
`benchmark/data/ground_truth/unified/gs_NNN/` by
`benchmark.analysis.dataset_curation.build_unified_dataset`. Built from
`gold_standard_selection.json` (the 151-entry output of
`gold_standard_filter.py`). Each `gs_NNN/` directory is **fully
self-contained**: `expected.json` (unified schema), `source.md`
(+ multilingual `source_*.md`), and `source.pdf` (+ multilingual
`source_*.pdf` for clingen/clinvar_fused). Every entry shares one flat,
field-complete schema: gene/disease/mondo/moi identifiers, ClinGen
classification metadata, locatable source (PMID/DOI/PMC/PDF), language,
fidelity-unified `variants[]`, and a dynamically generated
`evaluation_config`. Missing fields are back-filled from the HGNC
terminology file, the ClinGen Gene-Disease Summary CSV (with
approved-symbol fallback), `meta.json`, materialized local PDFs, and
EuropePMC (doi/journal/year by PMID, cached). `gold_source` tags each
entry as `database` (clingen/clinvar_fused) or `article`
(rett/parkinson); `annotation_provenance` records the curation origin;
`backfilled` records each supplemented field's source. A top-level
`manifest.json` indexes all entries. Original source datasets are never
modified.

#### Source Provenance

Every unified entry carries provenance back to its original dataset. The
authoritative source is `unified/manifest.json` (schema version 1.1.0).
Each manifest entry includes:

| Field | Description |
|-------|-------------|
| `unified_id` / `entry_id` | `gs_NNN` identifier |
| `source_dataset` | Origin dataset: `clingen`, `clinvar_fused`, `rett`, `parkinson` |
| `original_entry_id` / `source_entry_id` | Original ID before unification (e.g. `rett_001`) |
| `source_path` | Original ground-truth directory path |
| `gene_symbol`, `disease_name` | Gene and disease identifiers |
| `classification` | ClinGen classification or curation label |
| `moi` | Mode of inheritance |
| `language` | Source article language |
| `has_multilingual_sources` | Whether multilingual PDFs/MDs are present |

`expected.json` inside each `gs_NNN/` also carries `source_dataset` and
`original_entry_id` for convenience, but the manifest is authoritative.

#### Stratified Evaluation

When reporting benchmark metrics on the unified dataset, **stratify
results by `source_dataset`**. Aggregate numbers alone obscure
per-dataset performance differences (e.g. clingen gene-disease entries
vs. rett variant-heavy entries). Use the manifest to group entries and
compute per-stratum precision, recall, and F1.

#### Validation

Run the manifest integrity check before any evaluation:

```bash
python benchmark/scripts/validate_manifest.py
```

This verifies: every `gs_NNN` directory has a manifest entry, every
manifest entry points to an existing `expected.json`, no duplicate IDs,
and required provenance fields are non-empty.

#### Batch / Shard Execution

The unified dataset supports batch execution for incremental evaluation:

```bash
# Run the full unified dataset (150 entries)
cd backend && uv run python -m benchmark.layer3.evaluate

# Run a single shard (10 entries per shard)
uv run python -m benchmark.layer3.evaluate --shard-index 0 --shard-size 10

# Run specific entries
uv run python -m benchmark.layer3.evaluate --entries gs_000 gs_001 gs_002 gs_003 gs_004

# Resume from a failed shard — re-run only the failed entries
uv run python -m benchmark.layer3.evaluate --entries gs_007 gs_015

# Run with concurrency
uv run python -m benchmark.layer3.evaluate --shard-index 0 --shard-size 20 --concurrency 4
```

Each shard produces an independent report file (`eval_unified_<ts>_shardN.json`),
so completed shards are never overwritten. Results include `by_source_dataset`
stratification and full provenance (`source_dataset`, `original_entry_id`).

#### Queued Task Handling

The pipeline client treats `queued` as a normal waiting state (PostgreSQL
single-task queue). Tasks transition `queued` → `running` → `completed/failed`
automatically; the poll loop logs progress every 60 seconds while queued.

### Legacy Datasets (Deprecated)

The following datasets are retained for backward compatibility but are **no
longer the default**. Use them by passing `--ground-truth-root` explicitly:

```bash
# ClinGen-30 (3 entries, 3 expected fields)
uv run python -m benchmark.layer3.evaluate \
    --ground-truth-root benchmark/data/ground_truth/clingen

# ClinVar Fused (76 entries, 8 expected fields)
uv run python -m benchmark.layer3.evaluate \
    --ground-truth-root benchmark/data/ground_truth/clinvar_fused
```

| Dataset | Path | Entries | Status |
|---------|------|---------|--------|
| ClinGen-30 (Benchmark A) | `ground_truth/clingen/` | 34 | **Deprecated** — use unified |
| ClinVar Fused | `ground_truth/clinvar_fused/` | 76 | **Deprecated** — use unified |
| Rett Syndrome / MECP2 | `ground_truth/rett/` | 54 | **Deprecated** — use unified |
| Parkinson Literature | `ground_truth/parkinson/` | 21 | **Deprecated** — use unified |
| Merged 73 | `ground_truth/merged_73/` | 73 | **Deprecated** — use unified |

## Testing

```bash
# Full benchmark test suite
cd backend && uv run pytest tests/benchmark/ -q
```

## See Also

- Plan: `docs/active/2026-06-18-benchmark-framework-refactor-plan.md`
- Migration script: `scripts/refactor_benchmark_imports.py`
- Reports bucketing: `scripts/refactor_benchmark_reports.py`
- Per-bucket README in each subpackage
