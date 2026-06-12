# Database Architecture Design

**Status:** completed
**Created:** 2026-05-18
**Completed:** 2026-05-18
**PR:** branch `database-mvp`

## Goal

Build a PostgreSQL-first persistence layer for CrossEvidence that keeps the write side normalized and versioned, while exposing a flattened read model for fast gene, variant, DOI, PMID, and keyword search. Redis remains a cache only. Vector search and graph storage stay out of the MVP.

## Confirmed Decisions

| Area | Decision |
|---|---|
| Primary store | PostgreSQL |
| Cache | Redis for DAO read caching only; future token/session TTL namespace reserved |
| ORM / migration | SQLAlchemy 2.0 async ORM + Alembic under `database/migrations/` |
| Write model | Normalized tables with versioned run records and JSONB for fast-changing attributes |
| Read model | A dedicated `frontend_search_index` flattened search index, implemented as a materialized view or refreshable table |
| Vector search | Not in MVP |
| GraphRAG / Neo4j | Not in MVP |
| Review | Minimal `review_status` field only; no feedback detail table in MVP |

## Identity Rules

| Concept | Meaning |
|---|---|
| `source_document_id` | Stable document identity across retries, re-parses, and re-extractions |
| `processing_run_id` | One execution of parse/translate/extract/standardize/fuse |
| Canonical evidence key | `source_document_id + field_id + position_hash + entity_scope_hash` |
| `position_hash` | Hash of normalized location data: `track + page + start_offset + end_offset + context_ref` |
| `text_hash` | Hash of the span text for drift detection |
| `entity_scope_hash` | Hash of scope-bearing bindings only: `subject`, `target`, `context`, `comparator` |

`variant_id` is no longer a hard uniqueness input. Variant, gene, disease, and phenotype are all represented through entity bindings.

`field_id` is the fine-grained evidence catalog field. ACMG codes and ClinGen modules are separate labels, not part of the uniqueness key.

## Logical Schema

### `source_documents`

Stable document root.

Core columns:

- `source_document_id` UUID primary key.
- `raw_metadata` JSONB for durable document metadata that can evolve.
- `latest_processing_run_id` nullable foreign key.
- `created_at`, `updated_at`.

Notes:

- DOI, PMID, PMCID, file hash, and any other external identifier do not live here.
- This table exists so one document can survive multiple runs and identifier changes.

### `source_document_identifiers`

External identifier registry and first dedupe gate.

Core columns:

- `source_document_identifier_id` UUID primary key.
- `source_document_id` foreign key.
- `identifier_type` text, for example `doi`, `pmid`, `pmcid`, `file_hash`.
- `identifier_value` text.
- `created_at`, `updated_at`.

Constraints:

- Unique `(identifier_type, identifier_value)`.

Notes:

- If a new identifier already exists on another document, the merge happens here before evidence is duplicated.
- This table is the physical gate for DOI/PMID/file-based deduplication.

### `processing_runs`

Reproducibility boundary for each pipeline execution.

Core columns:

- `processing_run_id` UUID primary key.
- `source_document_id` foreign key.
- Version snapshot fields for parser, translation, extraction, standardization, fusion, prompt, model, and config hashes.
- `input_artifacts` JSONB or path bundle.
- `output_artifacts` JSONB or path bundle.
- `run_status`.
- `created_at`, `completed_at`.

Notes:

- A run is the audit boundary, not the canonical identity boundary.
- Re-running the same document creates a new run, not a new source document.

### `normalized_entities`

Shared entity dictionary for gene, variant, disease, phenotype, method, and future entity types.

Core columns:

- `entity_id` UUID primary key.
- `entity_type` text.
- `external_id` nullable text.
- `normalized_raw_text` text.
- `display_name` text.
- `aliases` JSONB.
- `standardization_status` text.
- `merged_into_entity_id` nullable foreign key to the same table.
- `raw_payload` JSONB.
- `created_at`, `updated_at`.

Status machine:

- `standardized`
- `unmapped`
- `merged`
- `rejected`

Constraints:

- Unique `(entity_type, external_id)` for standardized rows.
- Unique `(entity_type, normalized_raw_text)` for unmapped rows.

Notes:

- Unmapped entities are still inserted immediately with a UUID.
- Later expert mapping can trigger hash recomputation and canonical merge.
- `merged_into_entity_id` keeps direct traceability on the entity row.

### `entity_merge_events`

Audit trail for entity merges.

Core columns:

- `entity_merge_event_id` UUID primary key.
- `from_entity_id`.
- `to_entity_id`.
- `merge_reason`.
- `merged_by_user_id` nullable foreign key.
- `merged_at`.
- `raw_payload` JSONB.

Notes:

- This table is the human-readable merge history.
- It complements `normalized_entities.merged_into_entity_id`.

### `run_evidence_items`

Versioned extraction output for one run.

Core columns:

- `run_evidence_item_id` UUID primary key.
- `processing_run_id` foreign key.
- `source_document_id` foreign key.
- `track` text, usually `original` or `translated`.
- `field_id` text.
- `status` text.
- `value` JSONB.
- `confidence` numeric.
- `position_hash` text.
- `text_hash` text.
- `source_span` JSONB for multi-span or multimodal source detail.
- `entity_scope_hash` text.
- `raw_payload` JSONB.
- `canonical_evidence_id` nullable foreign key.
- `created_at`, `updated_at`.

Notes:

- This is the durable run-level record.
- It preserves the raw value and the source details that were produced in that run.
- `canonical_evidence_id` is filled after canonical grouping.

### `evidence_entity_bindings`

Hyperedge-style binding table between evidence and normalized entities.

Core columns:

- `evidence_entity_binding_id` UUID primary key.
- `run_evidence_item_id` foreign key.
- `entity_id` foreign key.
- `entity_type` text.
- `role` text.
- `binding_rank` integer nullable.
- `raw_entity_text` text nullable.
- `created_at`, `updated_at`.

Allowed roles:

- `subject`
- `target`
- `context`
- `comparator`
- `mention`

Constraints and indexes:

- Composite index on `(entity_type, entity_id)`.
- Composite index on `(run_evidence_item_id, role)`.

Notes:

- Only `subject`, `target`, `context`, and `comparator` participate in `entity_scope_hash`.
- `mention` is preserved for traceability but excluded from canonical identity.

### `canonical_evidence_items`

Current-best aggregated evidence record.

Core columns:

- `canonical_evidence_id` UUID primary key.
- `source_document_id` foreign key.
- `field_id` text.
- `position_hash` text.
- `text_hash` text.
- `entity_scope_hash` text.
- `current_best_run_evidence_id` foreign key.
- `current_best_status` text.
- `current_best_confidence` numeric.
- `conflict_flag` boolean.
- `review_status` text.
- `active_payload` JSONB.
- `created_at`, `updated_at`.

Constraints:

- Unique `(source_document_id, field_id, position_hash, entity_scope_hash)`.

Notes:

- One canonical row can aggregate many run-level versions.
- `current_best_run_evidence_id` points to the selected version.
- `active_payload` is the flattened direct-read surface: current best value plus key entity and source snapshots.
- `text_hash` is retained for collision and drift checks, not for the canonical uniqueness rule.
- `conflict_flag` is the only canonical-level conflict signal in MVP; conflict details remain in run-level records.
- `review_status` is intentionally minimal and tracks provisional vs approved workflow state.

### `users`

Minimal auth table for login and review ownership.

Core columns:

- `user_id` UUID primary key.
- `email` unique.
- `password_hash`.
- `display_name` nullable.
- `status` text.
- `created_at`, `updated_at`.

Notes:

- This is the only auth persistence needed in MVP.
- Redis token/session TTL storage is deferred.

## Read Model

`frontend_search_index` is the front-end search surface. Its job is to answer the user-facing search paths without forcing joins through the normalized write model.

Recommended columns:

- `canonical_evidence_id`
- `source_document_id`
- `pmid`
- `doi`
- `gene_ids` array
- `variant_ids` array
- `entity_ids` array
- `field_id`
- `review_status`
- `current_best_confidence`
- `search_text`
- `active_payload`
- `updated_at`

Recommended indexes:

- B-tree on `pmid`.
- B-tree on `doi`.
- GIN on `gene_ids`.
- GIN on `variant_ids`.
- GIN or full-text index on `search_text`.

Refresh rule:

- Rebuild or refresh only after a run finishes or a review state changes.
- Do not depend on the read model during in-flight extraction.

## Redis Cache

Redis is not the source of truth. It is a DAO cache layer only.

Cache policy:

- Cache read paths for source documents, canonical evidence, entities, and search results.
- Invalidate by affected `source_document_id`, `canonical_evidence_id`, and `entity_id` when a run completes or a review state changes.
- Keep a reserved namespace for future token/session TTL usage, but do not activate it in MVP.

## Deferred Extensions

Not part of MVP:

- pgvector-backed similarity search.
- Qdrant migration.
- Neo4j / GraphRAG persistence.
- Dedicated feedback detail tables.

The schema should still tolerate these later additions by keeping entity bindings, canonical evidence, and read-model projection cleanly separated.

## Open Implementation Choices

These are implementation choices, not business rules:

- `frontend_search_index` may start as a materialized view and later become a refreshable table if refresh cost grows.
- Exact `users` fields can be aligned with the auth module when login/register behavior is finalized.
- Exact `processing_runs` artifact storage format can be paths or JSONB references as long as the snapshot is immutable.
