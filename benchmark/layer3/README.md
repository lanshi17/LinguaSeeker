# Layer 3 Evaluation — ClinGen Ground Truth

Automated evaluation of pipeline evidence extraction accuracy against ClinGen gene-disease validity curation data.

## Overview

Uses 30 ClinGen gene-disease entries as ground truth, with PMC full-text articles, to measure:

| Metric | Description |
|--------|-------------|
| **Field P/R/F1** | Precision/Recall/F1 for key evidence fields (gene_symbol, disease_diagnosis, gene_disease_relationship) |
| **Entity Standardization Accuracy** | Whether pipeline resolved gene→HGNC and disease→MONDO IDs correctly |
| **Cross-lingual Consistency** | Original vs translated track field value agreement |
| **By Classification** | Metrics broken down by ClinGen classification (Definitive/Strong/Moderate/Limited/Refuted/Disputed) |
| **By MOI** | Metrics broken down by mode of inheritance (AD/AR/XL/MT/SD) |

## Files

| File | Purpose |
|------|---------|
| `select_entries.py` | Selects 30 representative entries from ClinGen CSV |
| `fetch_literature.py` | Searches EuropePMC for PMID/PMC ID per entry |
| `download_pdfs.py` | Downloads PMC full text via NCBI efetch → markdown |
| `generate_ground_truth.py` | Generates ground truth JSON with expected fields |
| `evaluate.py` | Main evaluator: submits articles to pipeline, compares to ground truth |
| `visualize.py` | Generates charts and HTML report from evaluation JSON |

## Usage

### Prerequisites

- Backend running on `http://localhost:8000`
- PostgreSQL with terminology data imported
- `benchmark/layer3/ground_truth/*/source.md` files present (30 entries)

### Run Evaluation

```bash
cd backend
# Evaluate all 30 entries (slow: ~5-10 min each)
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

Output: `benchmark/layer3/reports/report.html` + 5 PNG charts.

### Regenerate Ground Truth

```bash
cd backend
uv run python -m benchmark.layer3.select_entries    # Select 30 entries
uv run python -m benchmark.layer3.fetch_literature  # Query EuropePMC
uv run python -m benchmark.layer3.download_pdfs     # Download PMC articles
uv run python -m benchmark.layer3.generate_ground_truth  # Build expected.json
```

## Report Structure

```json
{
  "evaluation_id": "eval_clingen_xxx",
  "timestamp": "2026-06-08T...",
  "total_entries": 30,
  "aggregates": {
    "overall": {
      "precision": 0.89,
      "recall": 1.0,
      "f1": 0.94,
      "entity_standardization_accuracy": 0.65,
      "cross_lingual_consistency": 0.82
    },
    "by_field": { "A.gene_symbol": {...}, "B.disease_diagnosis": {...}, ... },
    "by_classification": { "Definitive": {...}, "Strong": {...}, ... },
    "by_moi": { "AD": {...}, "AR": {...}, "XL": {...} },
    "by_entity_type": { "gene": 0.85, "disease": 0.45 }
  },
  "per_entry": [ ... ]
}
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

Each entry has 3 expected evidence fields:
- `A.gene_symbol` — gene name (exact match)
- `B.disease_diagnosis` — disease name (fuzzy word-overlap ≥60%)
- `A.gene_disease_relationship` — causative/uncertain/disputed/refuted

## History

| Date | Entries | F1 | Notes |
|------|---------|-----|-------|
| 2026-06-06 | 3 | 50% | Baseline |
| 2026-06-07 | 3 | 94% | After prompt improvements |
| 2026-06-07 | 10 | 87.5% | Expanded to 10 entries |
| 2026-06-08 | 30 | — | Full 30-entry evaluation with entity std + track consistency |
