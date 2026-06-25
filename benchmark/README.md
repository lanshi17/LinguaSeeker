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
│   ├── ground_truth/  {clingen, clinvar_fused, rett}
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
    GROUND_TRUTH_ROOT, REPORTS_ROOT, RAW_PDF_ROOT,
    submit_and_poll, evaluate_one, run_evaluation,
)
```

`GROUND_TRUTH_ROOT` and `REPORTS_ROOT` always resolve to `benchmark/data/...`.

## Common Entry Points

| Goal | Command |
|------|---------|
| Run pipeline benchmark | `python -m benchmark.runners.pipeline_e2e --help` |
| Layer-3 ClinGen eval | `python -m benchmark.layer3.evaluate --help` (legacy shim) |
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

### Dataset 1: ClinGen-30 (Benchmark A)

30 entries from ClinGen Gene-Disease Summary CSV. 3 expected fields per entry (gene_symbol, disease_diagnosis, gene_disease_relationship). Full P/R/F1 evaluation.

### Dataset 2: ClinVar Fused

ClinGen Definitive/Strong x ClinVar >=2-star Pathogenic/LP variants. 8 expected fields across gene-disease (P/R/F1) and variant (precision-only) layers. Supports multilingual source articles (en + zh/ja/ko translations).

### Dataset 3: Rett Syndrome / MECP2

89 PDFs across 11 languages. AI-assisted annotation with human review. Covers all A-J evidence field categories (up to 143 fields per entry).

### Parkinson Literature

XLSX workbook curation utility (7 sheets, 6291 rows) with PMC PDF downloading. Structural audit, not yet a benchmark ground truth dataset.

### Unified Gold-Standard Dataset

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
