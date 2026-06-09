# Layer 3 Evaluation -- ClinGen Ground Truth

Automated evaluation of pipeline evidence extraction accuracy against ClinGen gene-disease validity curation data.

## Files

| File | Purpose |
|------|---------|
| `evaluate.py` | Main evaluator: submits articles to pipeline, compares to ground truth |
| `visualize.py` | Generates charts and HTML report from evaluation JSON |
| `select_entries.py` | Selects 30 representative entries from ClinGen CSV |
| `fetch_literature.py` | Searches EuropePMC for PMID/PMC ID per entry |
| `download_pdfs.py` | Downloads PMC full text via NCBI efetch |
| `generate_ground_truth.py` | Generates ground truth JSON with expected fields |
| `mondo_hierarchy.py` | MONDO ontology hierarchy utilities for disease matching |
| `ground_truth/` | 30 entries: `clingen_000`..`clingen_029`, each with `source.md` + `expected.json`, plus `selection.json` |
| `reports/` | Evaluation JSON reports, PNG charts, `report.html` |

## Metrics

| Metric | Description |
|--------|-------------|
| **Field P/R/F1** | Precision/Recall/F1 for gene_symbol, disease_diagnosis, gene_disease_relationship |
| **Entity Standardization** | Whether gene->HGNC and disease->MONDO IDs resolved correctly |
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

# Quick test with 3 entries
uv run python -m benchmark.layer3.evaluate --limit 3

# Custom backend URL
uv run python -m benchmark.layer3.evaluate --base-url http://192.168.1.100:8000
```

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
- `B.disease_diagnosis` -- disease name (fuzzy word-overlap >= 60%)
- `A.gene_disease_relationship` -- causative/uncertain/disputed/refuted

## History

| Date | Entries | F1 | Notes |
|------|---------|-----|-------|
| 2026-06-06 | 3 | 50% | Baseline |
| 2026-06-07 | 3 | 94% | After prompt improvements |
| 2026-06-07 | 10 | 87.5% | Expanded to 10 entries |
| 2026-06-08 | 30 | -- | Full 30-entry evaluation with entity std + track consistency |
