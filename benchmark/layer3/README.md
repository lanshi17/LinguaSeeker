# Layer 3 Evaluation -- ClinGen Ground Truth

Automated evaluation of pipeline evidence extraction accuracy against ClinGen gene-disease validity curation data.

## Files

| File | Purpose |
|------|---------|
| `evaluate.py` | Main evaluator: submits articles to pipeline, compares to ground truth, computes P/R/F1 |
| `visualize.py` | Generates matplotlib charts and HTML report from evaluation JSON |
| `select_entries.py` | Selects 30 representative entries from ClinGen CSV with balanced classification/MOI coverage |
| `fetch_literature.py` | Searches EuropePMC for PMID/PMC ID per entry |
| `download_pdfs.py` | Downloads PMC full text via NCBI efetch, converts JATS XML to markdown |
| `generate_ground_truth.py` | Generates ground truth JSON with expected fields |
| `mondo_hierarchy.py` | MONDO ontology hierarchy for disease ancestry matching |
| `preprocess.py` | Runs Phase 1+2 via pipeline API, caches outputs for fast re-evaluation |
| `ground_truth/` | 30 entries: `clingen_000`..`clingen_029`, each with `source.md` + `expected.json`, plus `selection.json` |
| `reports/` | Evaluation JSON reports, PNG charts, `report.html` |

## Architecture

```
select_entries.py          --> ground_truth/selection.json (30 entries)
       |
download_pdfs.py           --> ground_truth/{id}/source.md (PMC articles)
       |
generate_ground_truth.py   --> ground_truth/{id}/expected.json
       |
preprocess.py              --> ground_truth/{id}/preprocessed/phase_1/ + phase_2/  (optional)
       |
evaluate.py                --> reports/eval_{timestamp}.json
       |
visualize.py               --> reports/report.html + PNG charts
```

### Evaluation Flow

Each entry follows one of two paths:

1. **Preprocessed path** (fast): loads `preprocessed/phase_2/extraction_result.json`, extracts evidence items from both tracks, compares directly against expected fields.
2. **Pipeline path** (live): submits `source.md` as pre-parsed markdown to the pipeline API, polls until terminal status, queries PostgreSQL for evidence items, entity bindings, and track consistency.

Both paths then run `compare_evidence()` to produce `FieldMatch` results.

## Public API

### `normalize_comparison_text(value: str) -> str`

Normalizes harmless typography differences for benchmark comparison. Applies NFKC normalization, translates Unicode dash/quote variants to ASCII equivalents, and collapses whitespace. Used internally by `fuzzy_match_value()` but does **not** modify `FieldMatch.extracted_value` — reports always show raw extracted output.

```python
from benchmark.layer3.evaluate import normalize_comparison_text

normalize_comparison_text("Charcot–Marie–Tooth disease")  # → "Charcot-Marie-Tooth disease"
normalize_comparison_text("AARS2‑related  disease")       # → "AARS2-related disease"
normalize_comparison_text("AARS2－related disease")       # → "AARS2-related disease"
```

### `fuzzy_match_value(expected: str, extracted: str) -> bool`

Multi-strategy value matching. Comparison uses normalized text internally:

1. **Exact match** (case-insensitive, after normalization)
2. **Substring containment** — one value contains the other
3. **Gene symbol exact match** (case-sensitive, after normalization)
4. **Word-overlap** — splits on whitespace/hyphens, removes stop words, requires ≥60% overlap of expected words

### `compare_evidence(expected_fields, extracted_items, mondo=None, expected_standardization=None) -> list[FieldMatch]`

Core comparison logic. For each expected field:
1. Finds all extracted candidates with matching `field_id` and `status="found"`
2. Fuzzy-matches each candidate; picks best (exact > fuzzy > ontology_ancestor)
3. Falls back to MONDO ancestry for disease fields when fuzzy match fails
4. Tracks `extra_found_values` — extracted values that don't match any expected value

### `FieldMatch`

```python
@dataclass
class FieldMatch:
    field_id: str
    expected_value: str
    matched: bool
    extracted_value: str | None = None
    extracted_confidence: float | None = None
    match_type: str = "none"       # "exact" | "fuzzy" | "ontology_ancestor" | "missing" | "wrong_value"
    extra_found_values: list[str]  # over-extracted values not matching any expected value
```

### `EntryMetrics`

```python
@dataclass
class EntryMetrics:
    entry_id: str
    gene_symbol: str
    classification: str
    language: str
    moi: str = ""
    pipeline_status: str = "pending"  # "preprocessed" | "completed" | "error" | "timeout" | ...
    field_matches: list[FieldMatch] = field(default_factory=list)
    entity_matches: dict[str, bool] = field(default_factory=dict)
    standardization_accuracy: float = 0.0
    track_consistency: float = 0.0
    evidence_count: int = 0
    found_rate: float = 0.0
    grounding_rate: float = 0.0
```

### `compute_aggregate_metrics(all_metrics: list[EntryMetrics]) -> dict`

Returns a nested dict with:

| Key | Contents |
|-----|----------|
| `overall` | `true_positives`, `false_positives` (wrong_value + over_extractions), `false_negatives`, `precision`, `recall`, `f1`, `over_extractions`, `entity_standardization_accuracy`, `cross_lingual_consistency` |
| `by_field` | Per-field P/R/F1 + `over_extractions` count |
| `by_classification` | Per-classification P/R/F1 + `over_extractions` count |
| `by_moi` | Per-MOI P/R/F1 + `standardization_accuracy` + `track_consistency` + `over_extractions` |
| `by_entity_type` | Per-entity-type accuracy (gene→HGNC, disease→MONDO) |

### `MondoHierarchy` (`mondo_hierarchy.py`)

Parses MONDO ontology (OBO Graph JSON) into an in-memory hierarchy for disease ancestry checking.

```python
from benchmark.layer3.mondo_hierarchy import MondoHierarchy

mondo = MondoHierarchy.load()  # from database/terminology_database/mondo/
mondo.is_label_descendant_of("MODY12", "MONDO:0015967")  # True — MODY12 is_a monogenic diabetes
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
| **Over-extractions** | Extracted values that don't match any expected value — counts toward FP |
| **Entity Standardization** | Whether gene→HGNC and disease→MONDO IDs resolved correctly |
| **Cross-lingual Consistency** | Original vs translated track field value agreement |
| **By Classification** | Broken down by ClinGen classification (Definitive/Strong/Moderate/Limited/Refuted/Disputed) |
| **By MOI** | Broken down by mode of inheritance (AD/AR/XL/MT/SD) |

## Usage

### Prerequisites

- Backend running on `http://localhost:8000`
- PostgreSQL with terminology data imported
- `benchmark/layer3/ground_truth/*/source.md` files present (30 entries)

### Run Evaluation

```bash
cd backend

# Evaluate all 30 entries
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
uv run python -m benchmark.layer3.preprocess --entries clingen_000 clingen_001 clingen_002
```

Preprocessed entries evaluate in milliseconds instead of minutes.

### Generate Visualization

```bash
cd backend
uv run python -m benchmark.layer3.visualize
```

Output: `benchmark/layer3/reports/report.html` + PNG charts (overall_summary.png, field_f1.png, classification_heatmap.png, entity_standardization.png, moi_comparison.png).

### Regenerate Ground Truth

```bash
cd backend
uv run python -m benchmark.layer3.select_entries
uv run python -m benchmark.layer3.fetch_literature
uv run python -m benchmark.layer3.download_pdfs
uv run python -m benchmark.layer3.generate_ground_truth
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
- `B.disease_diagnosis` -- disease name (fuzzy word-overlap ≥60%, MONDO ancestry fallback)
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
