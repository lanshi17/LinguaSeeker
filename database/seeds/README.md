# database/seeds

> Reserved for database seed scripts that populate initial reference data.

## Current Status

This directory is currently empty. Seed data is loaded at runtime via:

```bash
# Import terminology database files into PostgreSQL
python scripts/import_terminology.py --sources hgnc omim hpo clingen clinvar

# With embedding generation
python scripts/import_terminology.py --sources hgnc --generate-embeddings
```

## Purpose

This directory is intended for SQL or Python seed scripts that populate:
- Default system configurations
- Initial user accounts (development only)
- Reference/lookup data

Seed scripts should be idempotent (safe to re-run).
