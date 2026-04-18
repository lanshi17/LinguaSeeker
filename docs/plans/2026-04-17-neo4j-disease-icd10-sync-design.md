# Neo4j Disease ICD10 Sync Design

## Goal

Ensure Neo4j `Disease` nodes carry `icd10_code` when PostgreSQL source data contains it, and provide a small backfill path to populate existing graph nodes without broad graph rewrites.

## Problem Summary

Current Neo4j `Disease` nodes mostly contain only `name`. Investigation showed two important facts:

1. PostgreSQL `evidence_records` contains `disease_name` values, but `icd10_code` is often `NULL`.
2. Neo4j `Disease` nodes currently do not expose `icd10_code` at all, even when future or existing PostgreSQL rows may contain it.

So this is not a broad “all disease metadata is missing” problem. The smallest useful fix is to guarantee `icd10_code` flows through whenever the source has it, and to backfill only those non-null mappings.

## Chosen Approach

Use a disease-only, `icd10_code`-only follow-up.

- Preserve and verify the forward sync path so `neo.upsert_disease(disease_name, icd10_code=...)` is used when `icd10` is non-empty.
- Add a lightweight backfill that reads distinct `(disease_name, icd10_code)` pairs from PostgreSQL `evidence_records` where `icd10_code IS NOT NULL`.
- Upsert only those Disease nodes in Neo4j.

This keeps scope tightly bounded and avoids pulling in larger data-cleaning work on variants or transcripts.

## Scope

### In scope
- Forward sync verification for Disease `icd10_code`
- Disease-only backfill service/CLI
- PostgreSQL source = `evidence_records`
- Neo4j target = `Disease` nodes
- Unit tests and one real verification query

### Out of scope
- Variant transcript cleanup
- Gene aliases/full names
- General disease normalization
- Any node classes other than `Disease`
- Repairing rows where PostgreSQL itself lacks `icd10_code`

## Data Flow

1. Read distinct disease rows from PostgreSQL `evidence_records`
2. Filter to rows with non-empty `disease_name` and non-empty `icd10_code`
3. Upsert Neo4j `Disease` nodes by `name`
4. Apply `icd10_code` through `SET d += $props`
5. Return processed counts and sample names for reporting

## Implementation Shape

### 1. Preserve/verify forward sync
Keep the current graph sync path responsible for passing `icd10_code` into `upsert_disease(...)` when available.

### 2. Add disease ICD10 backfill service
Add a small service function that:
- queries PostgreSQL for distinct disease mappings
- takes optional `limit` and `offset`
- calls `neo.upsert_disease(name, icd10_code=...)`
- returns a simple report

### 3. Add a CLI wrapper
Mirror the lightweight CLI style already used for other backfill commands.

## Verification Plan

### Unit verification
- A GraphSyncService regression proving Disease sync passes `icd10_code` when present
- A disease backfill unit test proving only non-empty `(name, icd10_code)` pairs are sent to Neo4j
- A CLI test proving the wrapper calls the service with parsed arguments

### Real verification
- Run the disease backfill CLI
- Query a sample Disease node and confirm `icd10_code` is present when source data exists

## Risks and Mitigations

### Risk: no useful source rows
Mitigation: treat this as a valid result and report zero processed rows honestly.

### Risk: duplicate disease names with inconsistent ICD10 values
Mitigation: only backfill exact distinct pairs and report if conflicting mappings are encountered later; do not solve normalization in this pass.

### Risk: scope creep into disease normalization
Mitigation: keep the backfill limited to a single optional property, `icd10_code`.

## Success Criteria

1. New graph syncs preserve `Disease.icd10_code` when source data has it
2. Existing Neo4j Disease nodes can be backfilled from PostgreSQL without replaying full graph sync
3. Unit tests prove the propagation path
4. A real Neo4j Disease node shows `icd10_code` after backfill when source data exists
