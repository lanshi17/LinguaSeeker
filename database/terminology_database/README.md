# Terminology Database

> Biomedical reference terminology data for ACMG Lingua Phase 3 entity standardization and knowledge alignment.

## Overview

The terminology database contains curated reference data from authoritative biomedical sources. These data are imported into PostgreSQL reference tables and indexed with pgvector embeddings to support deterministic and semantic matching of genes, diseases, phenotypes, and variants extracted from literature.

### Data Sources Summary

| Source | Entity Type | Directory | Key Files |
|--------|------------|-----------|-----------|
| HGNC | Gene | `hgnc/` | `hgnc_complete_set.txt` |
| OMIM | Disease | `omim/` | `mimTitles.txt`, `genemap2.txt`, `morbidmap.txt` |
| HPO | Phenotype | `hpo/` | `hp.json`, `genes_to_phenotype.txt`, `phenotype_to_genes.txt` |
| ClinVar | Variant | `clinvar/` | `variant_summary.txt`, `variant_summary.core.tsv` |
| ClinGen | Gene-Disease | `clingen/` | `Clingen-Gene-Disease-Summary.csv`, `Clingen-Dosage-Sensitivity.csv` |
| MONDO | Disease (ontology) | `mondo/` | `mondo.json`, `mondo_hierarchy_cache.json` |
| dbSNP | Variant (rsID lookup) | `dbSNP/` | `dbsnp_b157.sqlite` |

---

## Download Instructions

### HGNC (Hugo Gene Nomenclature Committee)

The official human gene nomenclature authority. No account required.

```bash
cd database/terminology_database/hgnc

# Complete dataset (~4MB, TSV format)
wget https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt
```

**Key fields:** `HGNC ID`, `Approved symbol`, `Approved name`, `Alias symbols`, `Previous symbols`, `Entrez Gene ID`, `Ensembl gene ID`

---

### OMIM (Online Mendelian Inheritance in Man)

Requires a free API key — apply at <https://www.omim.org/downloads>.

```bash
cd database/terminology_database/omim

# Replace {YOUR_API_KEY} with your registered key
wget "https://data.omim.org/downloads/{YOUR_API_KEY}/genemap2.txt"
wget "https://data.omim.org/downloads/{YOUR_API_KEY}/mimTitles.txt"
wget "https://data.omim.org/downloads/{YOUR_API_KEY}/morbidmap.txt"
```

**Key fields:** `MIM Number`, `Preferred Title; symbol`, `Gene Symbols`, `Phenotypes`

---

### HPO (Human Phenotype Ontology)

```bash
cd database/terminology_database/hpo

# JSON format (preferred, easier to parse)
wget https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/hp.json

# OBO format (alternative, contains ontology hierarchy)
wget https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/hp.obo

# Gene-phenotype association files
wget https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/genes_to_phenotype.txt
wget https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/phenotype_to_genes.txt

# Phenotype annotation file
wget https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/phenotype.hpoa
```

---

### ClinVar

```bash
cd database/terminology_database/clinvar

# Full variant summary (~3.7GB uncompressed)
wget https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz
gunzip variant_summary.txt.gz

# VCF format (optional, for variant-level lookups)
wget https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz
```

**Key fields:** `VariationID`, `Name`, `GeneSymbol`, `ClinicalSignificance`, `ReviewStatus`, `RS# (dbSNP)`, `PhenotypeIDS`

---

### ClinGen

No account required. Downloads are CSV exports from the Clinical Genome Resource.

```bash
cd database/terminology_database/clingen

# Gene-disease validity curations (most important)
wget "https://search.clinicalgenome.org/kb/gene-validity/download" \
  -O Clingen-Gene-Disease-Summary.csv

# Dosage sensitivity scores
wget "https://search.clinicalgenome.org/kb/gene-dosage/download" \
  -O Clingen-Dosage-Sensitivity.csv
```

---

### MONDO Disease Ontology

```bash
cd database/terminology_database/mondo

wget https://github.com/monarch-initiative/mondo/releases/download/v2026-06-02/mondo.json
```

---

### dbSNP

```bash
cd database/terminology_database/dbSNP

wget https://ftp.ncbi.nlm.nih.gov/snp/archive/b157/VCF/GCF_000001405.40.gz
```

In the current pipeline, dbSNP rsIDs are consumed indirectly via the `RS# (dbSNP)` column in ClinVar. The standalone dbSNP data file is stored for potential future direct rsID-to-variant resolution.

---

## Preprocessing

After downloading, several preprocessing steps are needed before importing into PostgreSQL.

### 1. ClinVar Core TSV Extraction

The full `variant_summary.txt` is ~3.7GB. The import pipeline first extracts a reduced TSV with only the fields needed for Phase 3 alignment:

```python
# Extracted fields: VariationID, Name, GeneSymbol, ClinicalSignificance,
#                   ReviewStatus, RS# (dbSNP), PhenotypeIDS
# Rows with zero-star review status are filtered out.
# Consecutive duplicate rows are deduplicated.
```

This produces `variant_summary.core.tsv` (~700MB), which is the file actually consumed during import.

To generate it programmatically:

```python
from pathlib import Path
from src.core.standardize_entities_and_align_knowledge.importers import build_clinvar_core_tsv

build_clinvar_core_tsv(
    source_path=Path("database/terminology_database/clinvar/variant_summary.txt"),
    target_path=Path("database/terminology_database/clinvar/variant_summary.core.tsv"),
)
```

### 2. MONDO Hierarchy Cache

The `mondo_hierarchy_cache.json` is a derived lookup structure built from `mondo.json` for fast disease ancestry matching. It contains:

- `label_to_id`: disease name → MONDO ID mapping
- `id_to_parents`: MONDO ID → list of parent MONDO IDs (transitive closure)

This cache is used during benchmark evaluation to check whether a predicted disease is an ancestor or descendant of the gold-standard disease in the ontology hierarchy.

### 3. dbSNP SQLite Conversion

The raw dbSNP VCF is converted to a SQLite database (`dbsnp_b157.sqlite`) for efficient rsID-based lookups without loading the full VCF into memory.

---

## Import into PostgreSQL

All terminology sources are imported via the unified CLI script:

```bash
cd /data/yangzs/Projects/01_ACMG_Lingua

# Import all sources (default: hgnc, omim, hpo, clingen, clinvar)
uv run python scripts/import_terminology.py \
  --terminology-root database/terminology_database \
  --version 2026.05

# Import specific sources only
uv run python scripts/import_terminology.py \
  --terminology-root database/terminology_database \
  --version 2026.05 \
  --sources hgnc clinvar

# Import and generate pgvector embeddings
uv run python scripts/import_terminology.py \
  --terminology-root database/terminology_database \
  --version 2026.05 \
  --generate-embeddings
```

### Standalone Embedding Build

If embeddings need to be rebuilt independently (e.g., after model server upgrade):

```bash
uv run python scripts/build_terminology_embeddings.py
```

---

## Import Pipeline Architecture

```
Raw Files (database/terminology_database/*)
    │
    ▼
importers.py — Source-specific parsers
    │  parse_hgnc_rows()     → ImportBatch (gene entries + aliases)
    │  parse_omim_rows()     → ImportBatch (disease entries + aliases)
    │  parse_hpo_rows()      → ImportBatch (phenotype entries + aliases)
    │  parse_clingen_rows()  → ImportBatch (disease entries + gene-disease relationships)
    │  parse_clinvar_rows()  → ImportBatch (variant entries + clinical significance relationships)
    │
    ▼
ImportBatch dataclasses
    │  ImportEntry       — entity: type, source_db, external_id, display_name, aliases
    │  ImportAlias       — queryable alias: text, normalized form, alias_type
    │  ImportRelationship — structured link: subject → object, evidence_level
    │
    ▼
repositories.py — PostgreSQL upsert into reference tables
    │
    ▼
providers.py — ModelServer embedding generation (pgvector)
```

### Entity Type Mapping

| Source DB | Entity Type | ID Format | Examples |
|-----------|------------|-----------|----------|
| HGNC | `gene` | `HGNC:12345` | BRCA1, TP53, CFTR |
| OMIM | `disease` | `OMIM:123456` | Marfan syndrome |
| HPO | `phenotype` | `HP:0001250` | Seizures, Short stature |
| ClinVar | `variant` | `ClinVarVariation:12345` | NM_000059.3:c.7397C>T |
| MONDO | `disease` | `MONDO:0007252` | Ehlers-Danlos syndrome |
| ClinGen | (relationships) | — | gene ↔ disease validity, dosage sensitivity |

### Normalization

All text values are normalized before import to ensure consistent matching:

- **Gene symbols**: uppercase, stripped whitespace (`normalize_gene_symbol`)
- **Lookup text**: lowercase, collapsed whitespace (`normalize_lookup_text`)
- **Variant text**: HGVS-specific normalization, 3-letter → 1-letter amino acid conversion (`normalize_variant_text`)

---

## Updating Data

When updating terminology data to a new release:

1. Re-download the source files using the commands above
2. Re-run preprocessing (ClinVar core TSV, MONDO hierarchy cache)
3. Import with a new `--version` tag:
   ```bash
   uv run python scripts/import_terminology.py \
     --terminology-root database/terminology_database \
     --version 2026.06 \
     --generate-embeddings
   ```
4. Verify import counts in the logs
