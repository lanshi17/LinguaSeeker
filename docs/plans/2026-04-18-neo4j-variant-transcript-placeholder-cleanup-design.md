# Neo4j Variant Transcript Placeholder Cleanup Design

## Goal

Stop obvious placeholder transcript values such as `"0.0"`, `"null"`, and `"None"` from being persisted into PostgreSQL evidence rows and Neo4j `Variant` / `Transcript` nodes.

## Problem Summary

Investigation showed real Neo4j `Variant` nodes carrying values like:

- `transcript_id = "0.0"`

The root cause is that the current sync pipeline treats any non-empty string as valid. The extracted-field path feeds transcript-like values through generic normalization, and `"0.0"` survives all the way into PostgreSQL and then Neo4j.

## Chosen Approach

Use a **transcript-specific** placeholder filter rather than broad string cleaning.

That means:
- keep generic `_normalize_string()` unchanged
- add a targeted `_normalize_transcript_id()` helper
- use it only on transcript-related paths

This is preferred because the confirmed dirty-value problem is currently specific to transcript identifiers, and we want to keep the change tightly scoped.

## Scope

### In scope
- Filter obvious transcript placeholder values
- Forward sync only
- Unit tests proving placeholders do not reach graph/database writes
- Optional read-only inspection of existing dirty data after the forward fix

### Out of scope
- Broad string cleaning across all fields
- Disease / Gene / Document follow-ups
- Large-scale normalization of transcript formats
- Automatic backfill of existing dirty rows unless explicitly requested later

## Candidate Placeholder Values

The initial denylist should include only clearly invalid placeholder values:

- `"0.0"`
- `"null"`
- `"none"`
- `"nan"`
- `"n/a"`

Comparison should be case-insensitive after trimming whitespace.

## Implementation Shape

### 1. Add targeted transcript normalization
Add a helper in `GraphSyncService` that:
- reuses the existing string normalization baseline
- converts the placeholder values above to `None`
- otherwise returns the cleaned transcript string unchanged

### 2. Apply it only to transcript paths
Use that helper where transcript data is pushed into:
- PostgreSQL evidence records
- Neo4j `Variant` / `Transcript` nodes

Do not apply it to unrelated free-text fields.

### 3. Keep existing behavior for valid transcript IDs
Real transcript IDs like `NM_006017.3` must remain unchanged.

## Verification Plan

### Unit verification
- a regression test showing `transcript_id="0.0"` is dropped before persistence
- a regression test showing a valid transcript ID still persists normally

### Real verification
- inspect a sample of Neo4j `Variant` nodes after the forward fix
- confirm new syncs no longer create fresh `transcript_id="0.0"` values

## Risks and Mitigations

### Risk: over-filtering a legitimate value
Mitigation: keep the denylist extremely small and only include obvious placeholders.

### Risk: dirty historical rows remain
Mitigation: explicitly accept that in this pass; the goal is to stop new bad writes first.

### Risk: placeholder values appear in other fields too
Mitigation: defer that to a later generalized cleanup pass instead of broadening this change now.

## Success Criteria

1. New syncs do not write transcript placeholder values like `"0.0"`
2. Valid transcript IDs still sync correctly
3. Unit tests prove both behaviors
