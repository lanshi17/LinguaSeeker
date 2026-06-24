# database/migrations

> Alembic async migration environment for the Lingua Seeker PostgreSQL schema.

## Structure

```
migrations/
├── env.py              # Async Alembic environment (reads DSN from src.core.config)
├── env.py.jinja        # Jinja template for env.py generation
├── script.py.mako      # Mako template for new migration scripts
└── versions/           # Migration version files (23 migrations)
```

## Key Details

- **Async engine:** Uses `create_async_engine` with `asyncpg` driver and `NullPool`.
- **Schema-aware:** Migrations target a configurable PostgreSQL schema (from `cfg.postgresql.schema_`), not `public`. The `search_path` is set to `<schema>,public`.
- **Config source:** Reads database connection from `backend/src/core/config.py` via `get_config()`.
- **Offline mode:** Generates SQL to stdout without connecting to a database, useful for review.
- **Path handling:** `env.py` inserts `backend/` into `sys.path` at runtime so `src.*` imports resolve from the repo root.

## Quick Start

```bash
cd /data/[redacted-user]/Projects/01_ACMG_Lingua

# Apply all pending migrations
uv run alembic -c database/alembic.ini upgrade head

# Create a new migration
uv run alembic -c database/alembic.ini revision --autogenerate -m "add_feature_table"

# Downgrade one version
uv run alembic -c database/alembic.ini downgrade -1

# Show current version
uv run alembic -c database/alembic.ini current

# Offline SQL generation
uv run alembic -c database/alembic.ini upgrade head --sql
```

## Migration History

| Date | Migration | Description |
|------|-----------|-------------|
| 2026-05-18 | `init_mvp_schema` | Initial MVP schema (9 core tables) |
| 2026-05-25 | `add_terminology_embeddings_pgvector` | pgvector extension for terminology embeddings |
| 2026-05-25 | `add_terminology_reference_tables` | Terminology reference tables (hgnc, omim, hpo, etc.) |
| 2026-05-27 | `add_nulls_not_distinct_relationship_constraint` | NULLS NOT DISTINCT constraint |
| 2026-05-28 | `add_review_and_chat_tables` | Review/feedback and chat session tables |
| 2026-05-30 | `initial_schema` | Schema reset/restructure |
| 2026-06-01 | `add_fk_chat_message_evidence_entity` | FK from chat messages to evidence entities |
| 2026-06-08 | `add_literature_profiles` | Literature profile CQRS read-model table |
| 2026-06-08 | `add_performance_indexes` | Performance indexes for search |
| 2026-06-08 | `add_reviewed_unmappable_status` | Unmappable entity review status |
| 2026-06-08 | `extract_pipeline_status_column` | Extract pipeline status column |
| 2026-06-08 | `remove_run_evidence_canonical_fk` | Remove FK constraint |
| 2026-06-10 | `add_created_at_to_search_index` | Created_at for search indexing |
| 2026-06-11 | `add_pipeline_run_leases` | Pipeline run lease management |
| 2026-06-11 | `allow_standalone_chat_sessions` | Standalone chat sessions support |
| 2026-06-13 | `add_chat_message_action` | Nullable JSONB action column on chat_messages |
| 2026-06-21 | `add_critical_indexes` | Hot-path indexes: P0 (pipeline_run_states.created_at, canonical_evidence_items doc/field, literature_profiles.updated_at), P1 (run_evidence_items source-linker composite, normalized_entities standardization composite, review_status), P2 (source_document_identifiers composite, processing_runs.run_status) |
| 2026-06-21 | `add_variant_internal_id_index` | Partial unique index for synthetic `internal:variant:*` external IDs |
| 2026-06-22 | `add_document_processing_cache` | L2 PostgreSQL cache table for pipeline results (JSONB keyed by content hash) |
| 2026-06-23 | `repair_phase3_schema` | Repair missing Phase 3 runtime tables (terminology_embeddings, frontend_search_index) with idempotent existence checks |
| 2026-06-23 | `add_document_full_text` | Add original_text and translated_text columns to source_documents |
| 2026-06-23 | `add_content_blocks` | Add original_blocks and translated_blocks JSONB columns to source_documents |
| 2026-06-23 | `add_document_annotations` | Per-paragraph character-offset annotations table for bilingual reader highlights and notes |
