# Benchmark Framework

Reorganized layout of the ACMG-Lingua benchmark suite (2026-06-18 refactor).

## Top-level map

```
benchmark/
├── core/         shared primitives: contracts, matching, aggregate, paths, pdf,
│                 pipeline_client, evidence_metrics, mondo_hierarchy
├── datasets/     dataset-specific dataset assembly + evaluators
│   ├── clingen/        ClinGen entries + Rett curation
│   ├── clinvar_fused/  ClinVar-fused variants
│   └── rett_annotation/ MinerU-driven annotation toolkit (independent uv project)
├── runners/      experiment entry points that hit pipelines / providers / LLMs
├── analysis/     offline reporters that read previously generated reports
│   ├── reconcile/         ablation, case studies, oracle bound, contextual diagnosis
│   ├── traceability/      citation validity / span boundary / traceable F1
│   ├── baselines/         B0..B10 LLM baselines + prompt-only sweeps + summary tables
│   ├── arbitrator/        arbitrator dataset + policy evaluator
│   ├── benchmark_b/       multilingual pilot selection + Phase 2 metrics
│   ├── dataset_curation/  readiness, source inventory, expansion, alignment, leakage
│   ├── paper_artifacts/   paper-specific tables (G1/G2/main paper/rescue)
│   └── diagnostics/       grounding, native gain, extraction, baselines, block recall, reconcile errors
└── data/         every artifact (gitignored where appropriate)
    ├── ground_truth/{clingen,clinvar_fused,rett}
    ├── inputs/{pipeline,literature_acquisition}
    ├── reports/{eval,reconcile,traceability,baseline,benchmark_b,
    │            curation,paper,diagnostics,clinvar_fused,pipeline_e2e}
    └── baselines/manifests
```

## Stable imports

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

`GROUND_TRUTH_ROOT` and `REPORTS_ROOT` always resolve to `benchmark/data/...`. The
legacy `GROUND_TRUTH_DIR` / `REPORTS_DIR` aliases are still exported but will be
removed once the deprecation shims drop.

## Common entry points

|Goal|Command|
|---|---|
|Run pipeline benchmark|`python -m benchmark.runners.pipeline_e2e --help`|
|Layer-3 ClinGen eval|`python -m benchmark.layer3.evaluate --help` _(legacy, shim — prefer running via `benchmark.runners`)_|
|Download literature|`python -m benchmark.runners.literature_acquisition download --help`|
|Rett literature pipeline|`python -m benchmark.runners.literature_rett --help`|
|Build paper tables|`python -m benchmark.analysis.paper_artifacts.main_paper_tables --help`|
|Pilot selection|`python -m benchmark.analysis.benchmark_b.pilot_selection --help`|
|Grounding diagnostics|`python -m benchmark.analysis.diagnostics.grounding`|

## Compat shims (deprecation, removed in Phase 6)

The 2026-06-18 refactor preserved every legacy dotted path while the codebase
caught up. Imports under these prefixes still resolve but emit a
`DeprecationWarning` pointing at the new home:

* `benchmark.layer3.evaluate` → `benchmark.core`
* `benchmark.layer3.mondo_hierarchy` → `benchmark.core.mondo_hierarchy`
* `benchmark.layer3.analysis.<x>` → `benchmark.analysis.<group>.<module>`
* `benchmark.layer3.baselines.<x>` → `benchmark.analysis.baselines.<x>`
* `benchmark.layer3.{select_entries,fetch_literature,download_pdfs,generate_*,visualize,preprocess}` → `benchmark.datasets.clingen.*` / `benchmark.runners.clingen_preprocess`
* `benchmark.layer3.clinvar_fused.<x>` → `benchmark.datasets.clinvar_fused.<x>`
* `benchmark.pipeline.benchmark` → `benchmark.runners.pipeline_e2e`
* `benchmark.pipeline.evidence_metrics` → `benchmark.core.evidence_metrics`
* `benchmark.literature_acquisition.{benchmark,rett_download}` → `benchmark.runners.{literature_acquisition,literature_rett}`
* `benchmark.annotation.<x>` → `benchmark.datasets.rett_annotation.<x>`
* `benchmark.analysis.diagnose_grounding` / `benchmark.analysis.diagnose_native_gain` → `benchmark.analysis.diagnostics.{grounding,native_gain}`

## See also

* Plan: `docs/active/2026-06-18-benchmark-framework-refactor-plan.md`
* Migration script: `scripts/refactor_benchmark_imports.py`
* Reports bucketing: `scripts/refactor_benchmark_reports.py`
* Per-bucket README is kept in each subpackage.
