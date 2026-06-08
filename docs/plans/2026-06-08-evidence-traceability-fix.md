# Evidence Traceability Fix - Implementation Plan

**Date:** 2026-06-08  
**Status:** ✅ COMPLETED

## Problem

The evidence detail page at `/evidence/detail?groupId=...` was not displaying source spans for original and translated text. Both sections showed "No source span available" even though the data existed in the database.

## Root Cause

1. **Backend Issue**: `SearchService.get_group_detail()` was querying `run_evidence_items` table and joining on `canonical_evidence_id`
2. **Data Issue**: The `run_evidence_items.canonical_evidence_id` column was never populated (NULL on all 1423 rows)
3. **Data Location**: Source span data actually exists in `canonical_evidence_items.active_payload->'source'` but wasn't being extracted
4. **Offset Mismatch**: Source spans stored document-global offsets (e.g., 6344-6381) but `text_snippet` contained only short excerpts (37 chars), causing offset bounds errors
5. **Frontend Issue**: Trace selection used `canonical_evidence_id` but traces are now grouped by `field_id`

## Solution

### Backend Changes

**File:** `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py`

1. Removed `RunEvidenceItem` import (no longer needed)
2. Removed query for `run_evidence_items` table
3. Modified `get_group_detail()` to:
   - Group rows by `field_id` after fetching canonical items
   - Match original/translated track pairs for each field
   - Extract source spans directly from `active_payload->'source'`
   - Pass evidence value to `_build_highlight()` for offset fallback
4. Updated `_build_highlight()` to:
   - Accept optional `value` parameter
   - Clamp offsets to text bounds when out of range
   - Fall back to searching for value within text_snippet when offsets are invalid

### Frontend Changes

**File:** `frontend/src/features/evidence-search/components/EvidenceDetailView.tsx`

1. Updated `selectedTrace` memo to match traces by `field_id` instead of `canonical_evidence_id`
2. Updated active item highlighting to match by both `field_id` and `canonical_evidence_id`

### Test Updates

**File:** `backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py`

1. Updated `test_get_group_detail_pivots_distribution_and_traces()` to include source data in `active_payload`
2. Removed mock `run_items` query (no longer executed)

## Results

### Backend API Response (Before)
```json
{
  "traces": [
    {
      "field_id": "A.gene_symbol",
      "original": null,
      "translated": null
    }
  ]
}
```

### Backend API Response (After)
```json
{
  "traces": [
    {
      "field_id": "A.gene_symbol",
      "original": {
        "text": "BRCA1 was detected in the proband.",
        "highlight_start": 0,
        "highlight_end": 5,
        "page": 1
      },
      "translated": {
        "text": "检测到BRCA1。",
        "highlight_start": 3,
        "highlight_end": 8,
        "page": 1
      }
    }
  ]
}
```

### Test Results
- All 51 tests in `test_search_service.py` pass
- TypeScript type checking passes
- Live API returns 33 traces with source spans (23 with original, 27 with translated)

## Files Modified

1. `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py`
2. `frontend/src/features/evidence-search/components/EvidenceDetailView.tsx`
3. `backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py`

## Verification Steps

1. ✅ Backend tests pass (51/51)
2. ✅ TypeScript type checking passes
3. ✅ Live API returns traces with source spans
4. ✅ Highlighting works correctly (value-based fallback for offset mismatches)
5. ⏳ Manual browser testing (pending user verification)

## Notes

- The fix maintains backward compatibility with existing `run_evidence_items` data
- Source span extraction now uses the authoritative `active_payload` data
- Offset handling is robust to both document-global and snippet-relative offsets
- One trace per `field_id` (not per `canonical_evidence_id`) simplifies the data model
