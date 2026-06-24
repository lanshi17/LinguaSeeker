# Rett Syndrome Benchmark Annotation Tool

AI-assisted annotation tool for the third benchmark dataset (Rett syndrome / MECP2). Supports LLM-generated annotations with file-based human review workflow.

## Overview

End-to-end annotation pipeline for Rett syndrome literature:

1. **PDF Parsing** -- MinerU cloud API converts PDFs to structured markdown
2. **AI Annotation** -- LLM extracts gene, variant, clinical features, and other evidence fields
3. **Human Review** -- File-based review: edit JSON directly, manage status via CLI
4. **Benchmark Dataset** -- Approved entries enter `ground_truth/` for evaluation

**Data source**: `benchmark/literature_acquisition/downloads/rett/`, 89 PDFs across 11 languages (en=25, fr=14, ja=14, zh=10, de=8, tr=7, es=4, ru=3, ko=2, it=1, pt=1).

## Independent Configuration

This tool's configuration is **fully independent** from the main project's `backend/config/` system. It uses local `config.yaml` + `.env`:

```bash
cp .env.example .env
# Edit .env with your API keys
```

- `config.yaml` -- LLM model, MinerU API, paths
- `.env` -- API keys (`ANNOTATION_LLM_API_KEY`, `ANNOTATION_MINERU_TOKEN`), not version-controlled

Configuration is managed by Ansible via `benchmark/config/` (see `benchmark/config/README.md`).

## Installation

```bash
cd benchmark/datasets/rett_annotation
uv sync
```

## Usage

### 1. PDF Parsing

```bash
# All 89 PDFs (MinerU batch)
uv run python cli/parse_pdfs.py

# Specific language and count
uv run python cli/parse_pdfs.py --lang en zh --limit 10

# Fallback to pymupdf on MinerU failure
uv run python cli/parse_pdfs.py --fallback

# Force re-parse
uv run python cli/parse_pdfs.py --force
```

Output: `draft/rett_NNN/source.md` + `source.pdf` + `meta.json`

### 2. AI Annotation Generation

```bash
# All undrafted entries (concurrency=3)
uv run python cli/generate_drafts.py

# Specific entries
uv run python cli/generate_drafts.py --entries rett_000 rett_005

# Adjust concurrency
uv run python cli/generate_drafts.py --concurrency 5

# Force re-generate
uv run python cli/generate_drafts.py --force
```

Output: `draft/rett_NNN/expected.json`

### 2.1 Catalog-Driven Re-annotation

When the main project's field catalog is updated, use `cli/catalog_reannotate.py` to re-annotate using the current `knowledges/evidence-field-catalog.json`. This script extracts A-J single-article fields only, automatically excluding K-class cross-paper GDV curation fields.

```bash
# Quick field coverage scan (no write)
uv run python cli/catalog_reannotate.py \
  --model gpt-5-nano --limit 5 --concurrency 2 \
  --report reports/gpt5_nano_field_scan_sample.json

# Full ground_truth re-annotation (writes expected.json)
uv run python cli/catalog_reannotate.py \
  --model claude-opus-4-8 --concurrency 3 --write \
  --report reports/claude_opus_4_8_reannotation.json

# Retry specific entries with reduced context
uv run python cli/catalog_reannotate.py \
  --model claude-opus-4-8 --entries rett_020 rett_030 \
  --concurrency 1 --max-tokens 16384 --chunk-size 6000 --write \
  --report reports/claude_opus_4_8_reannotation_retry_compact.json
```

### 3. Human Review

Reviewers edit `draft/rett_NNN/expected.json` directly, then manage status via CLI:

```bash
# List all entries
uv run python cli/review_status.py --list

# Filter by status
uv run python cli/review_status.py --list --status draft

# Show statistics
uv run python cli/review_status.py --stats

# Approve
uv run python cli/review_status.py --approve rett_005 --reviewer "Name" --notes "Verified"

# Reject
uv run python cli/review_status.py --reject rett_010 --reason "Unreadable PDF"

# Promote to ground_truth (single)
uv run python cli/review_status.py --promote rett_005

# Batch promote all reviewed entries
uv run python cli/review_status.py --promote-all
```

Status flow: `parsed -> draft -> approved -> ground_truth` (or `draft -> rejected`)

### 4. Additional CLI Tools

| Script | Purpose |
|--------|---------|
| `cli/filter_entries.py` | Filter entries by criteria |
| `cli/review_backfill.py` | Backfill review metadata |
| `cli/catalog_reannotate.py` | Catalog-driven re-annotation with current field catalog |

## Source Code Layout

```
src/
  config.py           # Standalone config loader (Pydantic + YAML + .env)
  models.py           # Pydantic schemas: RettExpectedJson, ExpectedEvidenceField, ArticleVariant, DraftMeta, Manifest
  pdf_parser.py       # MinerU cloud API + pymupdf fallback
  annotator.py        # LLM-driven annotation generation (langchain-core + langchain-openai)
  catalog_annotation.py  # Catalog-aware prompt building and expected.json construction
  manifest.py         # Status tracking manifest
  review.py           # Review workflow logic
  utils.py            # HGVS / MECP2 variant / HPO constants
```

## Directory Structure

```
rett_annotation/
  pyproject.toml          # Independent uv project
  config.yaml             # LLM / MinerU / paths config
  .env.example            # API key template
  src/                    # Core library code
  cli/                    # CLI entry points
  tests/                  # Unit tests
  draft/                  # AI-generated annotation drafts
  approved/               # Human-reviewed approved
  rejected/               # Rejected (audit trail)
  ground_truth/           # Final benchmark dataset
    manifest.json         # Main manifest
    selection.json        # Entry index
    rett_NNN/             # Per-entry data
      expected.json       # Annotated evidence
      source.md           # Parsed markdown
      source.pdf          # Original PDF
      meta.json           # Entry metadata
  reports/                # Run reports
```

## Schema Compatibility

`expected.json` evidence fields use the main project's field catalog (`knowledges/evidence-field-catalog.json` schema 2.0.0): 143 literature-extractable fields in categories A-J. K-class Gene-Disease Validity Curation fields are cross-paper and excluded.

Each `expected_evidence` record corresponds to one actually-occurring field in the article, containing `field_id`, `value`, `evaluation_type` (`precision_recall` or `precision_only`), and optional `candidates` for multi-variant entries. Empty fields are omitted.

**Rett dataset characteristics**:
- Gene: **MECP2** (HGNC:6992); atypical Rett may show CDKL5/FOXG1
- Disease: **Rett syndrome** (MONDO:0010726), inheritance: **XD** (X-linked dominant)
- Common variants: p.R255X, p.R270X, p.R306C, p.T158M, p.R168X, p.R133C
- Protein domains: MBD (aa 78-162), TRD (aa 201-310)
- Clinical features: developmental regression, hand stereotypies, seizures, breathing abnormalities, microcephaly

## Complete Workflow

```bash
# 1. Environment setup
cd benchmark/datasets/rett_annotation
cp .env.example .env && $EDITOR .env
uv sync

# 2. Parse all PDFs (MinerU API, ~10-30 min)
uv run python cli/parse_pdfs.py

# 3. AI annotation (legacy 55-field prompt; prefer catalog_reannotate.py for current catalog)
uv run python cli/generate_drafts.py

# 3b. Re-annotate with current field catalog
uv run python cli/catalog_reannotate.py --model claude-opus-4-8 --write

# 4. Human review (iterate)
uv run python cli/review_status.py --list --status draft
# -> edit draft/rett_NNN/expected.json
uv run python cli/review_status.py --approve rett_000
uv run python cli/review_status.py --stats

# 5. Batch promote to ground_truth
uv run python cli/review_status.py --promote-all

# 6. Verify
cat ground_truth/selection.json
```

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `pydantic` + `pydantic-settings` | Data models + config loading |
| `pyyaml` | config.yaml parsing |
| `loguru` | Logging |
| `pymupdf` | PDF parsing fallback |
| `langchain-core` + `langchain-openai` | LLM calls |
| `httpx` | MinerU API HTTP client |

Managed independently via `uv`; does not affect main project dependencies.

## Testing

```bash
uv run pytest tests/ -v
```
