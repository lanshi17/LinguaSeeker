# Scripts

> Operational and end-to-end testing scripts for the ACMG Lingua backend. Run from the `backend/` directory with `uv run python scripts/<script>.py`.

## Script Map

| Script | Purpose | Usage |
|--------|---------|-------|
| `e2e_full.py` | Full end-to-end pipeline with composable stages | `uv run python scripts/e2e_full.py --stages parse,translate,extract,standardize,visualize` |
| `e2e_translate.py` | End-to-end translation pipeline only | `uv run python scripts/e2e_translate.py` |
| `e2e_extract_evidence.py` | End-to-end evidence extraction only | `uv run python scripts/e2e_extract_evidence.py` |
| `e2e_standardize_entities.py` | End-to-end entity standardization only | `uv run python scripts/e2e_standardize_entities.py` |
| `e2e_visualize_feedback.py` | End-to-end Phase 4 visualization + feedback | `uv run python scripts/e2e_visualize_feedback.py` |
| `build_terminology_embeddings.py` | Build pgvector embeddings for terminology subsets | `uv run python scripts/build_terminology_embeddings.py [--entity-types ...] [--source-dbs ...]` |
| `render_config.py` | Render merged layered config for debugging | `uv run python scripts/render_config.py --env development` |

## Quick Start

```bash
cd backend

# Full pipeline (all 5 stages)
uv run python scripts/e2e_full.py --stages parse,translate,extract,standardize,visualize

# Parse + translate only
uv run python scripts/e2e_full.py

# Build embeddings for specific entity types
uv run python scripts/build_terminology_embeddings.py --entity-types gene disease

# Debug merged config
uv run python scripts/render_config.py --env development --output /tmp/config.yaml
```

## e2e_full.py Stages

| Stage | Description | Input | Output |
|-------|-------------|-------|--------|
| `parse` | MinerU remote PDF parsing | PDF file | `parsed.json` |
| `translate` | Cross-lingual translation | `parsed.json` | `translated.json`, `metadata.json` |
| `extract` | Dual-track evidence extraction | Translation output | `result.json`, per-track results |
| `standardize` | Entity standardization + alignment | Extraction output | `matches.json` |
| `visualize` | Evidence review + expert feedback | DB canonical evidence | Audit events, feedback |

## Dependencies

All scripts use the backend's virtual environment (`uv run`). No separate dependencies needed.

## Notes

- E2E scripts require configured external services (LLM endpoints, MinerU API, PostgreSQL).
- `build_terminology_embeddings.py` requires a populated `terminology_entries` table in PostgreSQL.
- `render_config.py` outputs merged YAML for debugging; the output is not read by the runtime loader.
- Scripts are not part of the test suite -- they are manual operational tools.
