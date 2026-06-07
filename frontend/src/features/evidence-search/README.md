# Evidence Search Feature Module

> Search and filter structured evidence cards extracted by the ACMG Lingua pipeline. Queries the `frontend_search_index` table via `GET /api/v1/evidence/search` with gene, variant, disease, and PMID filters.

## Quick Start

```typescript
import { EvidenceSearchView } from "@/features/evidence-search";

// Drop the full search UI into any page:
<EvidenceSearchView />

// Or use the hook for custom UI:
import { useEvidenceSearch } from "@/features/evidence-search";

const { results, total, filters, updateFilter, applyFilters, clearFilters } = useEvidenceSearch();
```

## Architecture

```
features/evidence-search/
├── types/evidenceSearch.ts           # EvidenceSearchQuery, EvidenceSearchResult, EvidencePayload, EvidenceSearchResponse
├── services/evidenceSearch.ts        # searchEvidence() — GET /evidence/search with query params
├── hooks/useEvidenceSearch.ts        # Stateful filter management + TanStack Query for auto-fetch
├── components/
│   ├── EvidenceSearchForm.tsx        # 4-column filter grid (gene, variant, disease, PMID)
│   ├── EvidenceResultsTable.tsx     # Tabular results with status badges and confidence %
│   └── EvidenceSearchView.tsx      # Page-level orchestrator with ErrorBoundary isolation
└── index.ts                          # Barrel exports
```

### Data Flow

```
Component mounts
  → useEvidenceSearch() initializes with empty filters {}
    → useQuery fires GET /evidence/search (no params → all evidence)
      → Returns { items: EvidenceSearchResult[], total: number }

User types in filter fields
  → updateFilter("gene", "BRCA1") updates local filter state
    → User clicks "Search" → applyFilters() → query.refetch()
      → New request with ?gene=BRCA1
        → Table re-renders with filtered results

User clicks "Clear"
  → clearFilters() resets to {}
    → TanStack Query refetches with no params → all evidence
```

### Auto-Load on Mount

Unlike typical search UIs that start empty, `useEvidenceSearch` loads **all evidence** on mount (empty query = no filters). This gives users immediate visibility into the dataset, then they narrow via filters.

## Public API

### `useEvidenceSearch()` Hook

Stateful search hook with filter management.

| Property | Type | Description |
|----------|------|-------------|
| `results` | `EvidenceSearchResult[]` | Current page of evidence results |
| `total` | `number` | Total matching results |
| `isLoading` | `boolean` | Initial load in progress |
| `isFetching` | `boolean` | Any fetch (initial or refetch) in progress |
| `error` | `Error \| null` | Query error |
| `filters` | `EvidenceSearchQuery` | Current filter values |
| `updateFilter(key, value)` | `(key: keyof EvidenceSearchQuery, value: string) => void` | Update a single filter field |
| `applyFilters()` | `() => void` | Trigger refetch with current filters |
| `clearFilters()` | `() => void` | Reset all filters to `{}` |

### Types

| Type | Description |
|------|-------------|
| `EvidenceSearchQuery` | `{ gene?, variant?, disease?, pmid?, limit? }` — query parameters |
| `EvidenceSearchResult` | Single result row: `canonical_evidence_id`, `pmid`, `gene_ids`, `variant_ids`, `review_status`, `current_best_confidence`, `active_payload` |
| `EvidencePayload` | Denormalized JSONB: `gene`, `variant`, `phenotype`, `disease`, `classification`, `evidence_strength`, `references`, etc. |
| `EvidenceSearchResponse` | `{ items: EvidenceSearchResult[], total: number }` |

### Components

| Component | Props | Description |
|-----------|-------|-------------|
| `<EvidenceSearchView />` | — | Full page: form + table, each wrapped in ErrorBoundary |
| `<EvidenceSearchForm />` | `filters, onUpdateFilter, onSearch, onClear, isSearching?` | 4-column filter form |
| `<EvidenceResultsTable />` | `results, total, isLoading?` | Results table with status badges |

## Internal Design

### Filter Semantics

All text filters are **case-insensitive partial matches** against the denormalized `active_payload` fields, except `pmid` which is an **exact match**. The backend handles the SQL `ILIKE` translation.

### Review Status Badges

`EvidenceResultsTable` maps `review_status` to badge variants:

| Status | Badge |
|--------|-------|
| `provisional` | default (gray) |
| `approved` | success (green) |
| `corrected` | warning (yellow) |
| `rejected` | error (red) |

### Confidence Display

`current_best_confidence` is a float `[0, 1]` and displayed as a percentage: `0.87` -> `87%`. Null values render as `—`.

### ErrorBoundary Isolation

`EvidenceSearchView` wraps the form and results in separate `<ErrorBoundary>` components. A rendering crash in the results table won't take down the search form, and vice versa.

## Usage Patterns

### Custom results rendering

```typescript
const { results } = useEvidenceSearch();

return (
  <ul>
    {results.map((r) => (
      <li key={r.canonical_evidence_id}>
        {r.active_payload.gene} — {r.active_payload.variant}
      </li>
    ))}
  </ul>
);
```

### Programmatic filtering

```typescript
const { updateFilter, applyFilters } = useEvidenceSearch();

function handleGeneClick(gene: string) {
  updateFilter("gene", gene);
  applyFilters();
}
```

### Export results

```typescript
const { results } = useEvidenceSearch();

function handleExport() {
  const csv = results.map((r) => [
    r.pmid,
    r.active_payload.gene,
    r.active_payload.variant,
    r.active_payload.classification,
  ].join(","));
  // download CSV
}
```

## Extension Guide

### Adding new filter fields

1. Add the field to `EvidenceSearchQuery` interface in `types/evidenceSearch.ts`
2. Add a corresponding `<Input>` in `EvidenceSearchForm.tsx` (adjust the grid to `md:grid-cols-5` etc.)
3. Update `searchEvidence()` in `services/evidenceSearch.ts` to pass the new param
4. Backend: add the column/filter to `frontend_search_index` query

### Adding sortable columns

The table is currently static. To add sorting:
1. Add `sortBy` and `sortOrder` to `EvidenceSearchQuery`
2. Pass to the backend as query params
3. Add click handlers on `<th>` elements in `EvidenceResultsTable`

## Performance Notes

- **Default limit**: 50 results per request. Increase via `updateFilter("limit", "200")` if the backend supports pagination.
- **No client-side caching beyond TanStack Query**: Results are refetched on filter change. The query key includes the full `filters` object, so each unique filter combination is cached separately.
- **No virtualization**: The table renders all results at once. For datasets >500 rows, consider adding `react-window` or backend pagination.

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `@tanstack/react-query` | ^5.50.0 | `useQuery` for data fetching and caching |
| `axios` | ^1.7.0 | HTTP client via `apiClient` |

## Testing

Tests live in `frontend/tests/features/evidence-search/`.

```bash
cd frontend
npm run test -- --testPathPattern=evidence
```
