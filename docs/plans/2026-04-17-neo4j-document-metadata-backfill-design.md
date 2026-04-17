# Neo4j Document Metadata Backfill Design

## Goal

Backfill existing Neo4j `Document` nodes with PostgreSQL-backed metadata so each document node carries:

- `title`
- `file_hash`
- `status`
- `pmid`

The design keeps the change minimal and focused on `Document` nodes only.

## Problem Summary

Current PostgreSQL `documents` rows contain `title`, `file_hash`, `status`, and sometimes `pmid`, but Neo4j `Document` nodes were created with only `document_id`.

The root cause is in the graph sync path: `GraphSyncService._sync_to_neo4j()` called `neo.upsert_document(document_id)` without passing document properties.

That omission has already been corrected in the sync path for future writes. The remaining need is a backfill for already-synced Neo4j documents.

## Chosen Approach

Use a lightweight, document-only backfill path.

For each PostgreSQL document row, call:

```python
neo.upsert_document(
    document_id,
    title=title,
    file_hash=file_hash,
    status=status,
    pmid=pmid,
)
```

This is preferred over re-running full evidence resync because it is:

- cheaper
- lower risk
- idempotent
- tightly scoped to the confirmed problem

## Scope

### In scope

- Add a backfill service/CLI for Neo4j `Document` node metadata
- Reuse existing PostgreSQL and Neo4j clients
- Backfill only `Document` node properties
- Add focused unit coverage
- Run a real backfill against the current database and verify a sample node
- Report other likely unsynced Neo4j fields without fixing them

### Out of scope

- Rebuilding variant/evidence/gene edges
- Replaying historical evidence extraction
- Changing graph schema
- Broad graph consistency remediation beyond `Document` node properties

## Data Flow

1. Read document rows from PostgreSQL `documents`
2. For each row, normalize optional fields
3. Upsert the Neo4j `Document` node by `document_id`
4. Apply the metadata properties with `SET doc += $props`
5. Count processed rows for reporting

## Implementation Shape

### 1. Preserve the forward fix

Keep the existing `_sync_to_neo4j()` improvement that now fetches PostgreSQL document metadata and passes it into `neo.upsert_document(...)` for future sync operations.

### 2. Add document metadata backfill service

Add a small service function that:

- obtains a PostgreSQL client
- lists documents in batches
- obtains a Neo4j client
- upserts each document with the selected properties
- returns a summary such as processed count and optional sample IDs

### 3. Add a CLI entrypoint

Add a CLI wrapper so the backfill can be run deliberately from the repo, e.g. with a limit/batch-size option for safety.

## Verification Plan

### Unit verification

Add a unit test that proves the backfill passes PostgreSQL document metadata into `neo.upsert_document(...)`.

### Real verification

Run the backfill against the configured environment, then query Neo4j for a known document and confirm that:

- `document_id` remains intact
- `title` is present
- `file_hash` is present
- `status` is present
- `pmid` is present when available

## Risks and Mitigations

### Risk: accidental over-scope

Mitigation: limit the backfill to `Document` properties only and avoid any evidence/variant rewrites.

### Risk: null/empty values overwriting useful data

Mitigation: only include non-empty PostgreSQL fields in the property payload.

### Risk: large one-shot backfill

Mitigation: support batch sizing / limits in the CLI and keep the operation idempotent.

## Other Neo4j Field Gaps To Inspect and Report

After the backfill, inspect whether these node types also miss useful properties:

- `Gene`
- `Variant`
- `Evidence`
- `Disease`
- `Phenotype`
- `Transcript`

This inspection is reporting-only for this pass.

## Success Criteria

The design is complete when:

1. future syncs write `Document` metadata correctly
2. existing Neo4j `Document` nodes can be backfilled without replaying full evidence sync
3. unit coverage proves property propagation
4. a real Neo4j node shows the expected metadata after backfill
