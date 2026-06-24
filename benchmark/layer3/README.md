# Layer 3 Evaluation -- ClinGen Ground Truth

> **Status: DEPRECATED SHIM.** This package (`benchmark/layer3/`) contains only
> backward-compatible import shims after the 2026-06-18 framework refactor.
> All substantive code now lives in `benchmark.core`, `benchmark.datasets`,
> `benchmark.runners`, and `benchmark.analysis`. The shims will be removed in
> Phase 6 of the refactor.

Automated evaluation of pipeline evidence extraction accuracy against ClinGen gene-disease validity curation data.

## New Module Locations

| Old path | New path | Role |
|----------|----------|------|
| `benchmark.layer3.evaluate` | `benchmark.core` | Matching algorithms, contracts, aggregate metrics, pipeline client |
| `benchmark.layer3.mondo_hierarchy` | `benchmark.core.mondo_hierarchy` | MONDO ontology hierarchy for ancestry matching |
| `benchmark.layer3.select_entries` | `benchmark.datasets.clingen.select_entries` | Entry selection from ClinGen CSV |
| `benchmark.layer3.fetch_literature` | `benchmark.datasets.clingen.fetch_literature` | EuropePMC literature search |
| `benchmark.layer3.download_pdfs` | `benchmark.datasets.clingen.download_pdfs` | PMC full-text download + JATS-to-markdown |
| `benchmark.layer3.generate_ground_truth` | `benchmark.datasets.clingen.generate_ground_truth` | Ground truth JSON generation |
| `benchmark.layer3.visualize` | `benchmark.datasets.clingen.visualize` | Matplotlib charts and HTML report |
| `benchmark.layer3.preprocess` | `benchmark.runners.clingen_preprocess` | Phase 1+2 preprocessing + caching |
| `benchmark.layer3.baselines` | `benchmark.analysis.baselines` | LLM baseline strategies and sweep |
| `benchmark.layer3.clinvar_fused` | `benchmark.datasets.clinvar_fused` | ClinVar fused dataset pipeline |

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Deprecated shim: lazy `__getattr__` redirects to new locations |
| `evaluate.py` | Deprecated shim: re-exports all public symbols from `benchmark.core` |
| `mondo_hierarchy.py` | Deprecated shim: redirects to `benchmark.core.mondo_hierarchy` |
| `analysis/` | Deprecated shim package: redirects to `benchmark.analysis.*` subgroups |
| `baselines/` | Contains `__init__.py` (legacy package marker) |
| `clinvar_fused/` | Contains `__init__.py` + `pdf_generation.log` + `translation*.log` |
| `ground_truth/` | Ground truth data: `clingen_000..029` entries + `rett/` |

## Stable Imports (use these)

```python
from benchmark.core import (
    FieldMatch, EntryMetrics,
    compare_evidence, fuzzy_match_value, normalize_comparison_text,
    compute_aggregate_metrics,
    GROUND_TRUTH_ROOT, REPORTS_ROOT,
)
```

The deprecated `benchmark.layer3.*` shims still work but emit `DeprecationWarning`.

## Data Layout

Ground truth and reports are under `benchmark/data/`:

```
benchmark/data/
  ground_truth/
    clingen/           # 30 entries: clingen_000..clingen_029 + selection.json
    clinvar_fused/     # ClinVar fused entries
    rett/              # Rett syndrome entries
  reports/
    eval/              # Evaluation JSON reports
    reconcile/         # Reconcile ablations & case studies
    baseline/          # LLM baseline reports & summary tables
    traceability/      # Traceability metric reports
    benchmark_b/       # Multilingual pilot Phase 2 outputs
    curation/          # Dataset curation / readiness / inventory
    paper/             # Paper-specific tables & rescue manifests
    diagnostics/       # diagnose_* outputs
    clinvar_fused/     # Fused-dataset eval reports
    pipeline_e2e/      # HTTP pipeline benchmark runs
```

Path constants are centralized in `benchmark.core.paths`:

```python
from benchmark.core.paths import GROUND_TRUTH_ROOT, REPORTS_ROOT, BENCHMARK_ROOT, RAW_PDF_ROOT
```

## Key APIs

### `compare_evidence` (`benchmark.core.matching`)

Core comparison logic. For each expected field:
1. Finds extracted candidates with matching `field_id` and `status="found"`
2. Fuzzy-matches each candidate; picks best (exact > fuzzy > ontology_ancestor)
3. Falls back to MONDO ancestry for disease fields
4. Tracks `extra_found_values` (over-extractions)

### `FieldMatch` (`benchmark.core.contracts`)

Dataclass with: `field_id`, `expected_value`, `matched`, `extracted_value`, `match_type` (exact/fuzzy/ontology_ancestor/missing/wrong_value), `extra_found_values`, scoring fields.

### `EntryMetrics` (`benchmark.core.contracts`)

Dataclass with: `entry_id`, `gene_symbol`, `classification`, `pipeline_status`, `field_matches`, `entity_matches`, `standardization_accuracy`, `track_consistency`, `found_rate`, `grounding_rate`.

### `compute_aggregate_metrics` (`benchmark.core.aggregate`)

Returns nested dict with `overall` (P/R/F1 + over-extractions), `by_field`, `by_classification`, `by_moi`, `by_entity_type`.

### `MondoHierarchy` (`benchmark.core.mondo_hierarchy`)

Parses MONDO ontology (OBO Graph JSON) for disease ancestry checking.

## Ground Truth Selection

30 entries from ClinGen Gene-Disease Summary CSV:

| Classification | Count | MOI Coverage |
|----------------|-------|-------------|
| Definitive | 10 | AD, AR, XL, MT, SD |
| Strong | 5 | AD, AR, XL |
| Moderate | 5 | AD, AR, XL |
| Limited | 5 | AD, AR, XL |
| Refuted | 3 | AD, AR |
| Disputed | 2 | AD, XL |

## Usage

```bash
cd backend

# Evaluate all 30 entries
uv run python -m benchmark.layer3.evaluate --base-url http://localhost:8000 --concurrency 2

# Specific entries
uv run python -m benchmark.layer3.evaluate --entries clingen_000 clingen_001

# Preprocess for fast re-evaluation
uv run python -m benchmark.runners.clingen_preprocess --entries clingen_000 clingen_001

# Generate visualization
uv run python -m benchmark.datasets.clingen.visualize
```

## Testing

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_evaluate_matching.py -v
```
