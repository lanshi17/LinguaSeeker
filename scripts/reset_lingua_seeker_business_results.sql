-- ============================================================================
-- Reset Lingua Seeker Business Pipeline Results
-- ============================================================================
-- PURPOSE: Truncate all business pipeline result tables while preserving
--          terminology data, users, and migration state.
--
-- PRESERVED tables (NOT truncated):
--   - users
--   - terminology_entries
--   - terminology_aliases
--   - terminology_relationships
--   - terminology_embeddings
--   - alembic_version
--
-- USAGE:
--   psql -f scripts/reset_lingua_seeker_business_results.sql dev_lingua_seeker
-- ============================================================================

BEGIN;

TRUNCATE TABLE
  frontend_search_index,
  literature_profiles,
  review_audit_events,
  chat_messages,
  chat_sessions,
  document_annotations,
  evidence_entity_bindings,
  canonical_evidence_items,
  run_evidence_items,
  pipeline_jobs,
  pipeline_run_states,
  document_processing_cache,
  processing_runs,
  source_document_identifiers,
  source_documents,
  normalized_entities,
  entity_merge_events
RESTART IDENTITY CASCADE;

COMMIT;
