# database/migrations

> Alembic async migration environment for the CrossEvidence PostgreSQL schema.

## Quick Start

```bash
cd backend

# Apply all pending migrations
uv run alembic upgrade head

# Create a new migration
uv run alembic revision --autogenerate -m "add_feature_table"

# Downgrade one version
uv run alembic downgrade -1

# Show current version
uv run alembic current
```

## Structure

```
migrations/
├── env.py              # Async Alembic environment (reads DSN from src.core.config)
├── env.py.jinja        # Jinja template for env.py generation
├── script.py.mako      # Mako template for new migration scripts
└── versions/           # Migration version files (15 migrations)
```

## Key Details

- **Async engine:** Uses `create_async_engine` with `asyncpg` driver.
- **Schema-aware:** Migrations target a configurable PostgreSQL schema (not `public`).
- **Config source:** Reads database connection from `backend/src/core/config.py` via `config_loader.py`.

## Migration History

| Date | Migration | Description |
|------|-----------|-------------|
| 2026-05-18 | `init_mvp_schema` | Initial MVP schema |
| 2026-05-25 | `add_terminology_embeddings_pgvector` | pgvector extension for terminology embeddings |
| 2026-05-25 | `add_terminology_reference_tables` | Terminology reference tables (hgnc, omim, hpo, etc.) |
| 2026-05-27 | `add_nulls_not_distinct_relationship_constraint` | NULLS NOT DISTINCT constraint |
| 2026-05-28 | `add_review_and_chat_tables` | Review/feedback and chat session tables |
| 2026-05-30 | `initial_schema` | Schema reset/restructure |
| 2026-06-01 | `add_fk_chat_message_evidence_entity` | FK from chat messages to evidence entities |
| 2026-06-08 | `add_literature_profiles` | Literature profile table |
| 2026-06-08 | `add_performance_indexes` | Performance indexes for search |
| 2026-06-08 | `add_reviewed_unmappable_status` | Unmappable entity review status |
| 2026-06-08 | `extract_pipeline_status_column` | Extract pipeline status column |
| 2026-06-08 | `remove_run_evidence_canonical_fk` | Remove FK constraint |
| 2026-06-10 | `add_created_at_to_search_index` | Created_at for search indexing |
| 2026-06-11 | `add_pipeline_run_leases` | Pipeline run lease management |
| 2026-06-11 | `allow_standalone_chat_sessions` | Standalone chat sessions support |
