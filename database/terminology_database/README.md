# Terminology Database

> Biomedical reference terminology data for ACMG Lingua Phase 3 entity standardization and knowledge alignment.

## Directory Structure

```
terminology_database/
├── clinvar/
│   ├── variant_summary.txt              Full ClinVar variant summary (~3.7 GB)
│   ├── clinvar.vcf.gz                   ClinVar VCF format (GRCh38)
│   └── variant_summary.core.tsv         Reduced TSV for import (~700 MB)
├── clingen/
│   ├── Clingen-Dosage-Sensitivity.csv   Dosage sensitivity scores
│   └── Clingen-Gene-Disease-Summary.csv Gene-disease validity curations
├── dbSNP/
│   └── dbsnp_b157.sqlite               dbSNP b157 SQLite for rsID lookups
├── hgnc/
│   └── hgnc_complete_set.txt            Complete HGNC gene nomenclature dataset
├── hpo/
│   ├── hp.obo                           HPO ontology (OBO format)
│   ├── hp.json                          HPO ontology (JSON format)
│   ├── phenotype.hpoa                   Phenotype annotation file
│   ├── genes_to_phenotype.txt           Gene-to-phenotype associations
│   └── phenotype_to_genes.txt           Phenotype-to-gene associations
├── omim/
│   ├── mimTitles.txt                    OMIM title entries
│   ├── genemap2.txt                     OMIM gene map
│   └── morbidmap.txt                    OMIM morbid map
└── mondo/
    ├── mondo.json                       MONDO disease ontology
    └── mondo_hierarchy_cache.json       Derived hierarchy lookup (label_to_id, id_to_parents)
```

## Data Sources Summary

| Source | Entity Type | Directory | Key Files |
|--------|------------|-----------|-----------|
| ClinVar | Variant | `clinvar/` | `variant_summary.txt`, `clinvar.vcf.gz`, `variant_summary.core.tsv` |
| ClinGen | Gene-Disease | `clingen/` | `Clingen-Dosage-Sensitivity.csv`, `Clingen-Gene-Disease-Summary.csv` |
| dbSNP | Variant (rsID) | `dbSNP/` | `dbsnp_b157.sqlite` |
| HGNC | Gene | `hgnc/` | `hgnc_complete_set.txt` |
| HPO | Phenotype | `hpo/` | `hp.obo`, `hp.json`, `phenotype.hpoa`, `genes_to_phenotype.txt`, `phenotype_to_genes.txt` |
| OMIM | Disease | `omim/` | `mimTitles.txt`, `genemap2.txt`, `morbidmap.txt` |
| MONDO | Disease (ontology) | `mondo/` | `mondo.json`, `mondo_hierarchy_cache.json` |

## Download Instructions

### HGNC

```bash
cd database/terminology_database/hgnc
wget https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt
```

### OMIM (requires free API key)

```bash
cd database/terminology_database/omim
wget "https://data.omim.org/downloads/{YOUR_API_KEY}/genemap2.txt"
wget "https://data.omim.org/downloads/{YOUR_API_KEY}/mimTitles.txt"
wget "https://data.omim.org/downloads/{YOUR_API_KEY}/morbidmap.txt"
```

### HPO

```bash
cd database/terminology_database/hpo
wget https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/hp.json
wget https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/hp.obo
wget https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/genes_to_phenotype.txt
wget https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/phenotype_to_genes.txt
wget https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/phenotype.hpoa
```

### ClinVar

```bash
cd database/terminology_database/clinvar
wget https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz
gunzip variant_summary.txt.gz
wget https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz
```

### ClinGen

```bash
cd database/terminology_database/clingen
wget "https://search.clinicalgenome.org/kb/gene-validity/download" -O Clingen-Gene-Disease-Summary.csv
wget "https://search.clinicalgenome.org/kb/gene-dosage/download" -O Clingen-Dosage-Sensitivity.csv
```

### MONDO

```bash
cd database/terminology_database/mondo
wget https://github.com/monarch-initiative/mondo/releases/download/v2026-06-02/mondo.json
```

### dbSNP

```bash
cd database/terminology_database/dbSNP
wget https://ftp.ncbi.nlm.nih.gov/snp/archive/b157/VCF/GCF_000001405.40.gz
```

## Preprocessing

### ClinVar Core TSV Extraction

The full `variant_summary.txt` (~3.7 GB) is reduced to `variant_summary.core.tsv` (~700 MB) by extracting key fields and filtering zero-star reviews:

```python
from pathlib import Path
from src.core.standardize_entities_and_align_knowledge.importers import build_clinvar_core_tsv

build_clinvar_core_tsv(
    source_path=Path("database/terminology_database/clinvar/variant_summary.txt"),
    target_path=Path("database/terminology_database/clinvar/variant_summary.core.tsv"),
)
```

### MONDO Hierarchy Cache

`mondo_hierarchy_cache.json` is derived from `mondo.json` for fast disease ancestry matching. Contains `label_to_id` (disease name to MONDO ID) and `id_to_parents` (MONDO ID to parent MONDO IDs, transitive closure).

### dbSNP SQLite Conversion

The raw dbSNP VCF is converted to `dbsnp_b157.sqlite` for efficient rsID-based lookups.

## Import into PostgreSQL

```bash
cd /data/[redacted-user]/Projects/01_ACMG_Lingua

# Import all sources
uv run python scripts/import_terminology.py \
  --terminology-root database/terminology_database \
  --version 2026.05

# Import specific sources
uv run python scripts/import_terminology.py \
  --terminology-root database/terminology_database \
  --version 2026.05 \
  --sources hgnc clinvar

# Import with pgvector embeddings
uv run python scripts/import_terminology.py \
  --terminology-root database/terminology_database \
  --version 2026.05 \
  --generate-embeddings
```

## Entity Type Mapping

| Source DB | Entity Type | ID Format |
|-----------|------------|-----------|
| HGNC | `gene` | `HGNC:12345` |
| OMIM | `disease` | `OMIM:123456` |
| HPO | `phenotype` | `HP:0001250` |
| ClinVar | `variant` | `ClinVarVariation:12345` |
| MONDO | `disease` | `MONDO:0007252` |
| ClinGen | (relationships) | gene-disease validity, dosage sensitivity |

## Updating Data

1. Re-download source files.
2. Re-run preprocessing (ClinVar core TSV, MONDO hierarchy cache).
3. Import with a new `--version` tag:
   ```bash
   uv run python scripts/import_terminology.py \
     --terminology-root database/terminology_database \
     --version 2026.06 \
     --generate-embeddings
   ```
4. Verify import counts in logs.
