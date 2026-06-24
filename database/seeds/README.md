# database/seeds

> Reserved for database seed scripts that populate initial reference data.

## Current Status

This directory is currently empty (only `.gitkeep`). Seed data is loaded at runtime via the terminology import script:

```bash
# Import terminology database files into PostgreSQL
uv run python scripts/data/import/import_terminology.py \
  --terminology-root database/terminology_database \
  --version 2026.05

# Import specific sources
uv run python scripts/data/import/import_terminology.py \
  --terminology-root database/terminology_database \
  --version 2026.05 \
  --sources hgnc clinvar

# Import with pgvector embeddings
uv run python scripts/data/import/import_terminology.py \
  --terminology-root database/terminology_database \
  --version 2026.05 \
  --generate-embeddings
```

## Purpose

This directory is intended for SQL or Python seed scripts that populate:
- Default system configurations
- Initial user accounts (development only)
- Reference/lookup data

Seed scripts should be idempotent (safe to re-run).
