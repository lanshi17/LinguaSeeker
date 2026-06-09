# Evidence Search Feature Module

> Literature-level search and review UI for structured ACMG evidence. The module queries evidence groups, aggregates them into literature rows, and provides a title/UUID-first detail flow with bilingual full-document evidence highlighting.

## Quick Start

```typescript
import { EvidenceSearchView } from "@/features/evidence-search";

export default function EvidencePage() {
  return <EvidenceSearchView />;
}
```

For custom data access:

```typescript
import { useEvidenceSearch } from "@/features/evidence-search";

const {
  results,
  total,
  filters,
  updateFilter,
  applyFilters,
  clearFilters,
  setPage,
} = useEvidenceSearch();
```

## Architecture

```text
features/evidence-search/
├── components/
│   ├── EvidenceSearchView.tsx       # Page-level feature orchestrator
│   ├── EvidenceSearchForm.tsx       # Gene, variant, disease, PMID filters
│   ├── EvidenceResultsTable.tsx     # Literature-row result table/cards
│   ├── EvidenceDetailView.tsx       # Literature overview + compare mode
│   └── EvidenceHighlightText.tsx    # Reusable single-span highlighter
├── hooks/
│   ├── useEvidenceSearch.ts         # Paginated search query state
│   └── useEvidenceGroupDetail.ts    # Group detail query state
├── services/evidenceSearch.ts       # API client calls
├── types/evidenceSearch.ts          # API boundary types
├── utils/
│   ├── evidenceDocument.ts          # Full-document reader and highlight helpers
│   └── literatureRows.ts            # Literature-row aggregation helpers
└── index.ts                         # Public exports
```

Data flow:

```text
/evidence page
  -> useEvidenceSearch()
  -> GET /api/v1/evidence/search
  -> EvidenceResultsTable.buildLiteratureRows(results)
  -> user opens representative group

/evidence/detail?groupId=...
  -> useEvidenceGroupDetail(groupId)
  -> GET /api/v1/evidence/groups/detail?group_id=...
  -> overview shows title, UUID, PMID/DOI, coverage, categories, evidence items
  -> "Full-text comparison" links to view=compare&evidenceId=...

/evidence/detail?groupId=...&view=compare&evidenceId=...
  -> same detail payload
  -> buildEvidenceDocument() creates original/English reader paragraphs
  -> sidebar toggles evidence highlight categories
  -> selected evidence item is emphasized in both document columns
```

## Public API

### `useEvidenceSearch()`

Stateful search hook with pagination.

| Property | Type | Description |
|----------|------|-------------|
| `results` | `EvidenceSearchResult[]` | Current page of evidence group summaries |
| `total` | `number` | Total matching evidence groups |
| `page` | `number` | Current backend page |
| `pageSize` | `number` | Current backend page size |
| `isLoading` | `boolean` | Initial load state |
| `isFetching` | `boolean` | Background refetch state |
| `error` | `Error \| null` | Query error |
| `filters` | `EvidenceSearchQuery` | Current filter and pagination state |
| `updateFilter` | `(key, value) => void` | Updates one filter and resets to page 1 |
| `applyFilters` | `() => void` | Refetches with current filters |
| `clearFilters` | `() => void` | Clears filters and resets pagination |
| `setPage` | `(page: number) => void` | Updates backend page |

### `useEvidenceGroupDetail(groupId)`

Loads the detail payload used by both overview and bilingual comparison views.

| Property | Type | Description |
|----------|------|-------------|
| `detail` | `EvidenceGroupDetailResponse \| undefined` | Group metadata, items, distribution, and traces |
| `isLoading` | `boolean` | Initial load state |
| `isFetching` | `boolean` | Background refetch state |
| `error` | `Error \| null` | Query error |
| `refetch` | `() => void` | Manual refetch |

### Utility Helpers

| Helper | Signature | Description |
|--------|-----------|-------------|
| `buildLiteratureRows` | `(results: EvidenceSearchResult[]) => LiteratureEvidenceRow[]` | Groups paged evidence results by `source_document_id` |
| `findInitialEvidenceId` | `(detail, requestedEvidenceId?) => string \| null` | Selects a valid requested evidence id or first traceable item |
| `buildBilingualCompareHref` | `(groupId, evidenceId?) => string` | Creates a stable compare-mode detail URL |
| `buildEvidenceDocument` | `(detail, track, enabledTones?, selectedEvidenceId?) => EvidenceDocument` | Builds full-document reader paragraphs and highlight ranges |
| `countEvidenceHighlightTones` | `(items) => EvidenceToneCounts` | Counts sidebar highlight categories |
| `evidenceToneForItem` | `(item?) => EvidenceHighlightTone` | Maps field/category metadata to a semantic highlight tone |

## Internal Design

### Literature Rows

The backend search API returns evidence group summaries, not a dedicated literature read model. `EvidenceResultsTable` keeps the API contract unchanged and uses `buildLiteratureRows()` to aggregate each page by `source_document_id`.

Each `LiteratureEvidenceRow` contains:

| Field | Source |
|-------|--------|
| `documentId` | `source_document_id`, falling back to `group_id` |
| `representativeGroupId` | First group on the current page for navigation |
| `title` | First available search result `title` |
| `genes`, `variants`, `diseases`, `classifications` | Unique values in first-seen order |
| `fieldCount` | Sum of evidence group `field_count` values |
| `groupCount` | Number of groups represented by the row |
| `avgConfidence` | Field-count-weighted average of non-null confidences |
| `reviewStatus` | Single status, or `mixed` when multiple statuses appear |

### Detail Flow

`EvidenceDetailView` supports two URL-controlled modes:

| Mode | URL | Purpose |
|------|-----|---------|
| Overview | `/evidence/detail?groupId=...` | Literature metadata, evidence coverage, category distribution, evidence item list |
| Compare | `/evidence/detail?groupId=...&view=compare&evidenceId=...` | Original/English full-document reader with category highlight controls |

The overview header treats `title` and `source_document_id` as primary identifiers because PMID and DOI may be missing. PMID/DOI remain visible as secondary metadata tokens.

The compare view does not fetch a second payload. It selects the requested evidence item from the group detail response and builds two document readers:

- If future backend payloads provide `original_document_text` or `translated_document_text`, `buildEvidenceDocument()` tries to locate each evidence span inside the full text.
- With the current trace-only payload, it synthesizes a full-document style reader from every available original/translated trace snippet.
- Highlight category toggles filter the rendered `<mark>` ranges without changing the underlying text.

### Highlight Tones

`EvidenceHighlightTone` is shared by `EvidenceHighlightText`, `EvidenceDetailView`, and `evidenceDocument.ts`:

| Tone | Typical fields |
|------|----------------|
| `gene` | Field ids containing `gene` |
| `variant` | Field ids containing `variant` or `hgvs` |
| `disease` | Field ids containing `disease` or `phenotype` |
| `classification` | Field ids containing `classification`, `pathogenic`, or `acmg` |
| `functional` | Catalog categories `F`, `G`, or `I` |
| `neutral` | Fallback |

The same tone is used for evidence category chips, sidebar switches, and `<mark>` source-span highlights so users can scan evidence classes consistently.

## Usage Patterns

### Render literature rows in a custom component

```typescript
import { buildLiteratureRows, useEvidenceSearch } from "@/features/evidence-search";

function LiteratureList() {
  const { results } = useEvidenceSearch();
  const rows = buildLiteratureRows(results);

  return (
    <ul>
      {rows.map((row) => (
        <li key={row.documentId}>
          {row.title ?? "Untitled literature record"}: {row.genes.join(", ")}
        </li>
      ))}
    </ul>
  );
}
```

### Link directly to bilingual comparison

```typescript
import { buildBilingualCompareHref } from "@/features/evidence-search";

const href = buildBilingualCompareHref(groupId, canonicalEvidenceId);
```

## Extension Guide

### Adding a search filter

1. Add the field to `EvidenceSearchQuery` in `types/evidenceSearch.ts`.
2. Add an input in `EvidenceSearchForm.tsx`.
3. Pass the query parameter in `services/evidenceSearch.ts`.
4. Add backend filter support in `GET /api/v1/evidence/search`.

### Switching to a literature-profile API

The UI is ready for a dedicated literature endpoint. Replace the page-level source in `useEvidenceSearch()` or add a new hook, then remove page-local aggregation from `EvidenceResultsTable`. Keep `representativeGroupId` or an equivalent detail target so users can still open evidence comparison.

### Adding a new evidence class color

1. Add a tone to `EvidenceHighlightTone`.
2. Add the `<mark>` class in `EvidenceDetailView.tsx`.
3. Add matching chip classes in `EvidenceDetailView.tsx`.
4. Update `evidenceToneForItem()` in `utils/evidenceDocument.ts` to map the field or category.
5. Add/adjust tests in `frontend/tests/evidence-search/literatureRows.test.ts`.

## Performance Notes

- Search uses backend pagination with a default page size of 50.
- Literature aggregation is page-local and linear in `results.length`.
- No virtualization is used; the UI is sized for the current page size.
- Detail and compare modes share one TanStack Query cache entry per `groupId`.
- The full-document reader uses bounded scroll containers (`max-h-[720px]`) instead of virtualizing trace snippets.

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `@tanstack/react-query` | `^5.50.0` | Query caching and refetch state |
| `axios` | `^1.7.0` | API client via `apiClient` |
| `lucide-react` | `^1.17.0` | Consistent UI icons |
| Node.js test runner | Node 20 | Frontend unit tests after TypeScript compilation |

## Testing

Focused tests live in `frontend/tests/evidence-search/`.

```bash
cd frontend
nvm use
npm test -- tests/evidence-search/literatureRows.test.ts
npm test
npm run type-check
npm run lint
npm run build
```
