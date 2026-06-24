# ClinVar Fused Benchmark (Dataset 2)

ClinGen provides gene-disease gold labels; ClinVar provides variant-level candidate gold labels. The fused dataset joins both sources on GeneSymbol + MONDO ID to produce entries with gene-disease fields (P/R/F1) and variant fields (precision-only).

## Files

| File | Purpose |
|------|---------|
| `select_fused_entries.py` | Select entries: ClinGen Definitive/Strong x ClinVar >=2-star Pathogenic/LP |
| `fetch_variant_literature.py` | EuropePMC search for open-access literature per fused entry |
| `download_articles.py` | Download PMC full text via NCBI efetch, convert JATS XML to markdown |
| `translate_to_multilingual.py` | Translate source.md into zh/ja/ko using LLM |
| `generate_pdfs.py` | Generate PDFs from source markdown (supports CJK via Noto Sans CJK) |
| `evaluate_fused.py` | Three-layer evaluation against preprocessed Phase 2 extraction data |
| `hgvs_normalize.py` | HGVS normalization: transcript prefix removal, 3-letter AA conversion, stop codon normalization |

## Quick Start

```bash
cd /data/[redacted-user]/Projects/01_ACMG_Lingua

# 1. Select entries (ClinGen Definitive/Strong x ClinVar >=2 star)
PYTHONPATH=.:backend uv run --project backend python -m benchmark.datasets.clinvar_fused.select_fused_entries

# 2. Fetch literature
PYTHONPATH=.:backend uv run --project backend python -m benchmark.datasets.clinvar_fused.fetch_variant_literature

# 3. Download PMC full text
PYTHONPATH=.:backend uv run --project backend python -m benchmark.datasets.clinvar_fused.download_articles

# 4. Translate to multilingual (zh/ja/ko)
PYTHONPATH=.:backend uv run --project backend python -m benchmark.datasets.clinvar_fused.translate_to_multilingual --langs zh ja ko

# 5. Generate PDFs for pipeline input
PYTHONPATH=.:backend uv run --project backend python -m benchmark.datasets.clinvar_fused.generate_pdfs --langs en zh ja ko

# 6. Evaluate against preprocessed Phase 2 data
PYTHONPATH=.:backend uv run --project backend python -m benchmark.datasets.clinvar_fused.evaluate_fused --write
```

All scripts accept `--limit N` and `--entries fused_000 fused_001` for subset runs.

## Evaluation Layers

### Layer 1: Gene-Disease (full P/R/F1)

Fields evaluated with `precision_recall` semantics:

| Field | Matching |
|-------|----------|
| `A.gene_symbol` | Exact match |
| `B.disease_diagnosis` | Multi-strategy: exact -> substring -> word overlap (>=60%) -> field normalization |
| `A.gene_disease_relationship` | Enum match (causative/uncertain/disputed/refuted) |
| `B.mode_of_inheritance_reported` | Enum match with field-specific normalization (AD/AR/XL etc.) |

### Layer 2: Variant (precision-only)

Fields evaluated with `precision_only` semantics -- no recall counting because articles may contain variants not in ClinVar:

| Field | Matching |
|-------|----------|
| `A.variant_hgvs_c` | Normalized candidate match |
| `A.variant_hgvs_p` | Normalized candidate match |
| `A.variant_type` | Enum match (missense/nonsense/frameshift/etc.) |
| `J.clinvar_assertion` | Enum match |

### Layer 3: Entity Standardization

| Target | Standard ID | Matching |
|--------|-------------|----------|
| Gene -> HGNC | `HGNC:XXXXX` | Exact |
| Disease -> MONDO | `MONDO:XXXXXXX` | Exact / ancestor |
| Variant -> ClinVar | `ClinVarVariation:XXXXX` | Candidate set match |

## HGVS Normalization (`hgvs_normalize.py`)

Handles common format variations between literature and ClinVar:

- Transcript prefix removal (`NM_xxxxx.x(GENE):`)
- Three-letter to one-letter amino acid conversion (`Arg` -> `R`)
- Stop codon normalization (`Ter`/`X`/`stop` -> `*`)
- Frameshift normalization (`fsTer74` -> `fs*74`)
- Variant type mapping (ClinVar `Type` to pipeline enum)

## Multilingual Translation (`translate_to_multilingual.py`)

Translates English `source.md` files into zh/ja/ko using LLM. Splits long articles by markdown headings to stay within context limits (max 12000 chars per chunk). Preserves gene symbols, variant notation, database IDs, and citation numbers unchanged.

Provider configuration: set `BENCHMARK_TRANSLATE_PROVIDERS` (JSON array of `{base_url, api_key, model}`) or fall back to `FAST_LLM_*` env vars.

## PDF Generation (`generate_pdfs.py`)

Converts markdown source files to PDF using `fpdf2`. CJK articles use Noto Sans CJK font. Output goes to `benchmark/pipeline/input/ground_truth/{lang}/case_report/{entry_id}.pdf`.

## Data Layout

```
clinvar_fused/
  ground_truth/
    selection.json          # All selected entries with expected evidence
    fused_NNN/
      expected.json         # Entry-specific ground truth
      source.md             # PMC full text (English)
      source_zh.md          # Chinese translation
      source_ja.md          # Japanese translation
      source_ko.md          # Korean translation
  reports/
    fused_eval_*.json       # Evaluation reports
```

## Selection Strategy

1. Parse ClinGen CSV, keep Definitive + Strong entries
2. Parse ClinVar `variant_summary.txt`, keep germline Pathogenic/LP with >=2 review stars
3. Join on GeneSymbol + MONDO ID (from ClinVar PhenotypeIDS)
4. For each fused group, keep top-3 variants by review stars
5. Score by diversity (MOI, GCEP, variant count) and select top N (default 75)

## Known Limitations

- Variant layer is precision-only; recall cannot be measured without full human annotation
- Literature may not contain ClinVar target variants
- Only English source articles; translations are LLM-generated
- ClinVar ClinicalSignificance is an aggregated value; article text may differ

## Testing

```bash
cd backend
uv run pytest tests/benchmark/layer3/clinvar_fused/ -v
```
