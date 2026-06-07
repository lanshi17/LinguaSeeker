# Visualize Evidence with Expert in Loop

> Evidence search and expert review system with field-level data pivoting and pagination.

## Overview

This module provides evidence search, review, and feedback functionality. The key feature is **field-level pivoting** - the database stores evidence as individual field extractions (e.g., `A.gene_symbol`, `B.disease_diagnosis`), but the search API pivots them into summary rows grouped by `group_id`.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SearchService                             │
│                                                              │
│  1. Query canonical_evidence_items (field-level rows)       │
│  2. Group by group_id (from active_payload JSONB)           │
│  3. Pivot fields into summary columns:                      │
│     - A.gene_symbol → gene                                  │
│     - A.variant_hgvs_* → variant                            │
│     - B.disease_diagnosis → disease                         │
│     - J.authority_classification → classification           │
│  4. Batch-load identifiers (PMID/DOI) from separate table   │
│  5. Apply pagination (page/page_size)                       │
└─────────────────────────────────────────────────────────────┘
```

## Database Schema

Evidence is stored at field-level granularity:

```sql
canonical_evidence_items (
  canonical_evidence_id UUID,
  source_document_id UUID,
  field_id VARCHAR,           -- e.g., 'A.gene_symbol', 'B.disease_diagnosis'
  active_payload JSONB,       -- contains 'group_id', 'value', 'confidence'
  review_status VARCHAR,
  current_best_confidence DECIMAL
)
```

Each row represents one field extraction. A complete evidence group (e.g., one case study) contains multiple rows sharing the same `group_id`.

## Search API

### Endpoint

```
GET /api/v1/evidence/search
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `gene` | string | Partial match on `A.gene_symbol` field values |
| `variant` | string | Partial match on `A.variant_hgvs_*` field values |
| `disease` | string | Partial match on `B.disease_diagnosis` field values |
| `pmid` | string | Exact match on PMID from `source_document_identifiers` |
| `doi` | string | Partial match on DOI from `source_document_identifiers` |
| `page` | int | Page number (1-indexed, default: 1) |
| `page_size` | int | Items per page (default: 50, max: 200) |

### Response

```json
{
  "items": [
    {
      "group_id": "gene=['BRCA1']|variant=['c.68_69del']|...",
      "source_document_id": "uuid",
      "pmid": "12345678",
      "doi": "10.1234/example",
      "gene": "BRCA1, BRCA2",
      "variant": "c.68_69delAG (p.Glu23Valfs)",
      "disease": "Hereditary breast and ovarian cancer syndrome",
      "classification": "Pathogenic",
      "field_count": 45,
      "avg_confidence": 0.92,
      "review_status": "provisional",
      "canonical_evidence_id": "uuid"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 50
}
```

## Field Mapping

The pivot logic maps field IDs to summary columns:

| Summary Column | Field ID Prefixes |
|----------------|-------------------|
| `gene` | `A.gene_symbol`, `A.gene_aliases` |
| `variant` | `A.variant_hgvs_c`, `A.variant_hgvs_p`, `A.variant_hgvs_g`, `A.variant_legacy_name` |
| `disease` | `B.disease_diagnosis`, `B.clinical_diagnosis`, `B.hpo_terms` |
| `classification` | `J.authority_classification`, `J.clinvar_assertion` |

## Usage Example

```python
from src.api.deps import get_db_session
from src.core.visualize_evidence_with_expert_in_loop.search_service import SearchService

async with get_db_session() as session:
    service = SearchService(session)
    
    # Search for BRCA1-related evidence
    results = await service.search_evidence(
        gene="BRCA1",
        page=1,
        page_size=50,
    )
    
    for item in results.items:
        print(f"Gene: {item.gene}")
        print(f"Disease: {item.disease}")
        print(f"Confidence: {item.avg_confidence:.2%}")
        print(f"Fields extracted: {item.field_count}")
```

## Frontend Integration

The frontend evidence search module consumes this API:

```typescript
// useEvidenceSearch hook manages pagination state
const { results, total, page, pageSize, setPage } = useEvidenceSearch();

// Table displays pivoted summary rows
<EvidenceResultsTable
  results={results}
  total={total}
  page={page}
  pageSize={pageSize}
  onPageChange={setPage}
/>
```

## Testing

```bash
cd backend
uv run pytest tests/core/visualize_evidence_with_expert_in_loop/ -v -k search
```

## Related Modules

- **Phase 3 (Standardize Entities)**: Produces the field-level evidence stored in `canonical_evidence_items`
- **Phase 4 (Expert Review)**: Uses `review_status` and `current_best_confidence` for expert feedback workflow
- **DAO Layer**: `CanonicalEvidenceItem`, `SourceDocumentIdentifier` models

## Performance Notes

- Field-level pivoting happens in application layer (not SQL) to maintain flexibility
- Batch-loads identifiers in a single query to avoid N+1 problem
- Pagination is applied after grouping to ensure consistent page sizes
- Filters on gene/variant/disease trigger a two-query pattern:
  1. Find matching `group_id`s
  2. Fetch all fields for those groups

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `sqlalchemy[asyncio]` | Async database queries |
| `pydantic` | Response validation |
| `fastapi` | API routing |
