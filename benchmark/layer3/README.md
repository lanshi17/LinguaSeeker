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

## Data Layout

Ground truth and reports have moved to `benchmark/data/`:

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
  inputs/
    pipeline/          # Pipeline E2E manifest + case-report PDFs
    literature_acquisition/  # Provider configs, query lists, downloads
```

Path constants are centralized in `benchmark.core.paths`:

```python
from benchmark.core.paths import GROUND_TRUTH_ROOT, REPORTS_ROOT, BENCHMARK_ROOT, RAW_PDF_ROOT
```

## Architecture

```
benchmark.datasets.clingen.select_entries   --> data/ground_truth/clingen/selection.json
benchmark.datasets.clingen.download_pdfs    --> data/ground_truth/clingen/{id}/source.md
benchmark.datasets.clingen.generate_ground_truth --> data/ground_truth/clingen/{id}/expected.json
benchmark.runners.clingen_preprocess        --> data/ground_truth/clingen/{id}/preprocessed/phase_2/
benchmark.core.pipeline_client.run_evaluation --> data/reports/eval/eval_{timestamp}.json
benchmark.datasets.clingen.visualize        --> data/reports/eval/report.html + PNG charts
```

### Evaluation Flow

Each entry follows one of two paths:

1. **Preprocessed path** (fast): loads `preprocessed/phase_2/extraction_result.json`, extracts evidence items from both tracks, compares directly against expected fields.
2. **Pipeline path** (live): submits `source.md` as pre-parsed markdown to the pipeline API, polls until terminal status, queries PostgreSQL for evidence items, entity bindings, and track consistency.

Both paths then run `compare_evidence()` to produce `FieldMatch` results.

## Public API

All imports below use the **canonical** `benchmark.core` paths. The deprecated `benchmark.layer3.*` shims still work but emit `DeprecationWarning`.

### Stable Imports

```python
from benchmark.core import (
    FieldMatch, EntryMetrics,
    compare_evidence, fuzzy_match_value, normalize_comparison_text,
    compute_aggregate_metrics,
    GROUND_TRUTH_ROOT, REPORTS_ROOT,
)
```

### `normalize_comparison_text(value: str) -> str` (`benchmark.core.matching`)

Normalizes harmless typography differences for benchmark comparison. Applies NFKC normalization, translates Unicode dash/quote variants to ASCII equivalents, translates CJK/ASCII punctuation to spaces, and collapses whitespace. Used internally by `fuzzy_match_value()` but does **not** modify `FieldMatch.extracted_value` -- reports always show raw extracted output.

```python
from benchmark.core import normalize_comparison_text

normalize_comparison_text("Charcot-Marie-Tooth disease")  # -> "Charcot-Marie-Tooth disease"
normalize_comparison_text("AARS2-related  disease")       # -> "AARS2-related disease"
normalize_comparison_text("AARS2-related disease")        # -> "AARS2-related disease"
```

### `fuzzy_match_value(expected: str, extracted: str) -> bool` (`benchmark.core.matching`)

Multi-strategy value matching. Comparison uses normalized text internally:

1. **Exact match** (case-insensitive, after normalization)
2. **Substring containment** -- one value contains the other
3. **Word-overlap** -- splits on non-word characters, requires >=60% overlap of expected words

### `compare_evidence(expected_fields, extracted_items, mondo=None, expected_standardization=None) -> list[FieldMatch]` (`benchmark.core.matching`)

Core comparison logic. For each expected field:
1. Finds all extracted candidates with matching `field_id` and `status="found"`
2. Fuzzy-matches each candidate; picks best (exact > fuzzy > ontology_ancestor)
3. Falls back to MONDO ancestry for disease fields when fuzzy match fails
4. Tracks `extra_found_values` -- extracted values that don't match any expected value

### `FieldMatch` (`benchmark.core.contracts`)

```python
@dataclass
class FieldMatch:
    field_id: str
    expected_value: str
    matched: bool
    extracted_value: str | None = None
    extracted_confidence: float | None = None
    source_span: dict[str, object] | None = None
    match_type: str = "none"       # "exact" | "fuzzy" | "ontology_ancestor" | "missing" | "wrong_value"
    extra_found_values: list[str]  # over-extracted values not matching any expected value
    best_score: float | None = None
    source_score: float | None = None
    confidence_score: float | None = None
    agreement_score: float | None = None
    status_score: float | None = None
    verifier_support_score: float | None = None
    target_specificity_score: float | None = None
    contradiction_penalty: float | None = None
    accepted_track: str | None = None
    normalized_value: str | None = None
```

### `EntryMetrics` (`benchmark.core.contracts`)

```python
@dataclass
class EntryMetrics:
    entry_id: str
    gene_symbol: str
    classification: str
    language: str
    moi: str = ""
    run_id: str | None = None
    status_url: str | None = None
    pipeline_status: str = "pending"  # "preprocessed" | "completed" | "error" | "timeout" | ...
    error_message: str | None = None
    last_pipeline_status: str | None = None
    last_current_phase: str | None = None
    duration_s: float = 0.0
    field_matches: list[FieldMatch] = field(default_factory=list)
    entity_matches: dict[str, bool] = field(default_factory=dict)
    standardization_accuracy: float = 0.0
    track_consistency: float = 0.0
    evidence_count: int = 0
    found_rate: float = 0.0
    grounding_rate: float = 0.0
```

### `compute_aggregate_metrics(all_metrics: list[EntryMetrics]) -> dict` (`benchmark.core.aggregate`)

Returns a nested dict with:

| Key | Contents |
|-----|----------|
| `overall` | `true_positives`, `false_positives` (wrong_value + over_extractions), `false_negatives`, `precision`, `recall`, `f1`, `over_extractions`, `entity_standardization_accuracy`, `cross_lingual_consistency` |
| `by_field` | Per-field P/R/F1 + `over_extractions` count |
| `by_classification` | Per-classification P/R/F1 + `over_extractions` count |
| `by_moi` | Per-MOI P/R/F1 + `standardization_accuracy` + `track_consistency` + `over_extractions` |
| `by_entity_type` | Per-entity-type accuracy (gene->HGNC, disease->MONDO) |

### `MondoHierarchy` (`benchmark.core.mondo_hierarchy`)

Parses MONDO ontology (OBO Graph JSON) into an in-memory hierarchy for disease ancestry checking.

```python
from benchmark.core.mondo_hierarchy import MondoHierarchy

mondo = MondoHierarchy.load()  # from database/terminology_database/mondo/
mondo.is_label_descendant_of("MODY12", "MONDO:0015967")  # True -- MODY12 is_a monogenic diabetes
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `load` | `(mondo_dir=None) -> MondoHierarchy` | Loads from cache or parses mondo.json/.json.gz |
| `find_id_by_label` | `(label: str) -> str \| None` | Case-insensitive normalized lookup with substring fallback |
| `get_ancestors` | `(mondo_id: str, max_depth=20) -> set[str]` | BFS traversal of is_a edges upward |
| `is_descendant_of` | `(child_id, ancestor_id) -> bool` | Checks ancestry relationship |
| `is_label_descendant_of` | `(extracted_label, expected_mondo_id) -> bool` | Combined lookup + ancestry check |

## Metrics

| Metric | Description |
|--------|-------------|
| **Field P/R/F1** | Precision/Recall/F1 for gene_symbol, disease_diagnosis, gene_disease_relationship |
| **Over-extractions** | Extracted values that don't match any expected value -- counts toward FP |
| **Entity Standardization** | Whether gene->HGNC and disease->MONDO IDs resolved correctly |
| **Cross-lingual Consistency** | Original vs translated track field value agreement |
| **By Classification** | Broken down by ClinGen classification (Definitive/Strong/Moderate/Limited/Refuted/Disputed) |
| **By MOI** | Broken down by mode of inheritance (AD/AR/XL/MT/SD) |

## Usage

### Prerequisites

- Backend running on `http://localhost:8000`
- PostgreSQL with terminology data imported
- `benchmark/data/ground_truth/clingen/*/source.md` files present (30 entries)

### Run Evaluation

```bash
cd backend

# Evaluate all 30 entries (uses the shim; import from benchmark.core for new code)
uv run python -m benchmark.layer3.evaluate --base-url http://localhost:8000 --concurrency 2

# Quick preprocessed regression for specific entries
uv run python -m benchmark.layer3.evaluate --entries clingen_000 clingen_001 clingen_002

# Custom backend URL
uv run python -m benchmark.layer3.evaluate --base-url http://192.168.1.100:8000
```

### Preprocess Entries (Optional)

Run Phase 1+2 once and cache outputs for fast re-evaluation:

```bash
cd backend
uv run python -m benchmark.runners.clingen_preprocess --entries clingen_000 clingen_001 clingen_002
```

Preprocessed entries evaluate in milliseconds instead of minutes.

### Generate Visualization

```bash
cd backend
uv run python -m benchmark.datasets.clingen.visualize
```

Output: `benchmark/data/reports/eval/report.html` + PNG charts.

### Regenerate Ground Truth

```bash
cd backend
uv run python -m benchmark.datasets.clingen.select_entries
uv run python -m benchmark.datasets.clingen.fetch_literature
uv run python -m benchmark.datasets.clingen.download_pdfs
uv run python -m benchmark.datasets.clingen.generate_ground_truth
```

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

Each entry has 3 expected fields:
- `A.gene_symbol` -- gene name (exact match)
- `B.disease_diagnosis` -- disease name (fuzzy word-overlap >=60%, MONDO ancestry fallback)
- `A.gene_disease_relationship` -- causative/uncertain/disputed/refuted

## Testing

```bash
cd backend
uv run pytest tests/benchmark/layer3/test_evaluate_matching.py -v
```

Covers: typography normalization (dash/quote/fullwidth variants), over-extraction counting, deduplication.

## History

| Date | Entries | F1 | Notes |
|------|---------|-----|-------|
| 2026-06-06 | 3 | 50% | Baseline |
| 2026-06-07 | 3 | 94% | After prompt improvements |
| 2026-06-07 | 10 | 87.5% | Expanded to 10 entries |
| 2026-06-08 | 30 | -- | Full 30-entry evaluation with entity std + track consistency |
| 2026-06-10 | 30 | -- | Typography normalization, over-extraction metrics, MONDO ancestry fallback |
| 2026-06-18 | 30 | -- | Framework refactor: code moved to benchmark.core/datasets/runners/analysis |
