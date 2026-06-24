# Evidence DB -- Variant-Centric Evidence Database

> Three-level browse experience for clinical genetics evidence, organized by variant identifier. Users drill from a variant index to variant detail with evidence fields and literature references to bilingual document comparison with multi-color category highlighting.

## Quick Start

```tsx
import { VariantIndexView, VariantDetailView, BilingualEvidenceView } from "@/features/evidence-db";

// L1: variant index grid
<VariantIndexView />

// L2: single variant detail (requires variantSlug from URL param)
<VariantDetailView variantSlug="BRCA1:c.5266dupC:breast_cancer" />

// L3: bilingual comparison (requires both variantSlug and sourceDocumentId)
<BilingualEvidenceView variantSlug="BRCA1:c.5266dupC:breast_cancer" sourceDocumentId="abc-123" />
```

Routing is handled by `EvidenceDbPage` (`src/pages/EvidenceDbPage.tsx`), which reads `useParams()` and delegates to the correct view:

| Level | URL | Component |
|-------|-----|-----------|
| L1 | `/evidence-db` | `VariantIndexView` |
| L2 | `/evidence-db/:variantSlug` | `VariantDetailView` |
| L3 | `/evidence-db/:variantSlug/:sourceDocId` | `BilingualEvidenceView` |

## Structure

```
features/evidence-db/
|-- index.ts                             # Barrel exports
|-- types/
|   +-- variantDb.ts                     # VariantIndexEntry, VariantDetailData, LiteratureReference, etc.
|-- services/
|   +-- variantDb.ts                     # fetchAllEvidence, fetchEvidenceGroupDetail
|-- hooks/
|   |-- useVariantIndex.ts              # Fetch + aggregate + filter + paginate variant index
|   +-- useVariantDetail.ts             # Fetch variant entry + all group details
|-- components/
|   |-- VariantIndexView.tsx            # L1: searchable variant grid with stats and pagination
|   |-- VariantIndexSkeleton.tsx        # Loading skeleton for variant index
|   |-- VariantDetailView.tsx           # L2: variant hero with evidence by category and literature sidebar
|   |-- VariantDetailSkeleton.tsx       # Loading skeleton for variant detail
|   |-- BilingualEvidenceView.tsx       # L3: bilingual document reader with category highlighting
|   |-- BilingualEvidenceSkeleton.tsx   # Loading skeleton for bilingual view
|   |-- BilingualSidebar.tsx            # Sidebar for bilingual comparison navigation
|   |-- ActiveEvidenceCard.tsx          # Card showing currently selected evidence item
|   |-- DocumentReader.tsx              # Full document reader with highlight rendering
|   |-- HighlightedText.tsx             # Inline highlight span renderer
|   |-- LiteratureHeader.tsx            # Literature document header (title, PMID, DOI)
|   |-- SidebarControls.tsx             # Sidebar filter/toggle controls
|   |-- StructuredBlockRenderer.tsx     # Renders MinerU structured content blocks (tables, images, code, lists)
|   +-- bevStyles.ts                    # Shared inline style constants for the bilingual evidence view
+-- utils/
    |-- variantAggregation.ts           # aggregateVariants, filterAndPaginateVariants
    +-- pathogenicity.ts                # classifyLevel, classificationColor, classificationBadgeStyle, classificationLabel
```

## Architecture

```
                    EvidenceDbPage
                    (useParams router dispatch)
                           |
              +------------+-------------+
              |            |             |
         VariantIndex  VariantDetail  BilingualEvidence
           View (L1)     View (L2)       View (L3)
              |            |             |
              v            v             v
         useVariantIndex  useVariantDetail
         (React Query)    (React Query)
              |            |
              v            v
         fetchAllEvidence  fetchEvidenceGroupDetail
         (GET /evidence/search)  (GET /evidence/groups/detail)
              |
              v
         aggregateVariants -> groups flat results by
         gene:variant:disease into VariantIndexEntry[]
         filterAndPaginateVariants -> applies filters + pagination
```

### Data Flow

1. **L1**: `fetchAllEvidence()` fetches all evidence search results (page_size=1000) -> `aggregateVariants()` splits multi-variant values into one row per variant site, then groups by `gene:variant:disease` composite key -> `filterAndPaginateVariants()` applies client-side filters and pagination -> React Query caches with 60s stale time.

2. **L2**: Reuses the L1 index query to find the variant entry -> fetches `EvidenceGroupDetailResponse` for each (group_id, source_document_id) pair via `Promise.allSettled` -> flattens all evidence items -> builds `LiteratureReference[]` with bilingual item maps for the sidebar.

3. **L3**: Uses `useEvidenceGroupDetail` from `@/features/evidence-search` to fetch the full group detail -> `buildEvidenceDocument()` constructs paragraphs with highlight ranges from traces -> category toggles filter which highlights are visible -> evidence navigator selects a specific field to emphasize.

## Public API

### Components

| Component | Props | Description |
|-----------|-------|-------------|
| `VariantIndexView` | -- | L1: searchable variant grid with stats, classification filters, pagination |
| `VariantDetailView` | `variantSlug: string` | L2: variant hero with confidence ring, evidence by category, literature sidebar |
| `BilingualEvidenceView` | `variantSlug: string`, `sourceDocumentId: string` | L3: bilingual document reader with category highlighting |

### Hooks

| Hook | Returns | Description |
|------|---------|-------------|
| `useVariantIndex` | `{ items, total, page, pageSize, stats, isLoading, isFetching, error, filters, updateFilter, setPage, clearFilters, refetch }` | Fetches + aggregates + filters variant index data client-side |
| `useVariantDetail` | `{ detail, isLoading, isFetching, error }` | Fetches variant entry + all group details for a single variant, builds bilingual maps |

### Types

| Type | Description |
|------|-------------|
| `VariantIndexEntry` | Aggregated variant: slug, gene, variant, disease, classification, counts, category distribution, groupIds, sourceDocumentIds, representative |
| `VariantIndexData` | Paginated response: items, total, page, pageSize, stats (classificationDistribution) |
| `VariantDetailData` | L2 response: entry, evidenceGroups, literature, allItems, reconciledItems, bilingualItems |
| `LiteratureReference` | Sidebar reference: sourceDocumentId, title, pmid, doi, groupId, fieldCount, categories, bilingualItems |
| `VariantIndexFilters` | Filter state: gene, variant, disease, classification, page, pageSize, sortBy, sortOrder |
| `ClassificationLevel` | `"pathogenic" \| "likely_pathogenic" \| "uncertain" \| "likely_benign" \| "benign"` |

### Utils

| Function | Description |
|----------|-------------|
| `classifyLevel(classification)` | Maps classification string -> `ClassificationLevel` |
| `classificationColor(level)` | Hex color for dark-theme rendering |
| `classificationBadgeStyle(level)` | Inline CSS style object for badge (bg, text, border) |
| `classificationLabel(level)` / `classificationShortLabel(level)` | Human-readable / abbreviated labels |
| `aggregateVariants(results)` | Splits multi-variant values into one row per variant site, groups flat `EvidenceSearchResult[]` -> `VariantIndexEntry[]` |
| `filterAndPaginateVariants(entries, filters)` | Applies filters + pagination -> `VariantIndexData` |

## Design

The evidence DB uses a light theme matching the dashboard's design system. CSS utility classes defined in `globals.css`:

- `.edb-hero` -- teal-tinted gradient header
- `.edb-card` -- white card container
- `.edb-card-clickable` -- white card with teal hover
- `.edb-ring` -- confidence ring indicator
- `.edb-cat-strip` -- category color strip
- `.edb-scroll` -- scrollable container
- `.edb-stagger` -- staggered entrance animation

**Pathogenicity scale**: `#B91C1C` (P) -> `#DC2626` (LP) -> `#6B7280` (VUS) -> `#0D9488` (LB) -> `#0F766E` (B)

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/evidence/search` | GET | Fetch all evidence search results (page_size=1000 for aggregation) |
| `/api/v1/evidence/groups/detail` | GET | Fetch full detail for a single evidence group (items + traces + document text) |

## Testing

```bash
cd frontend
bun run test tests/evidence-db/variantAggregation.test.tsx
```

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `@tanstack/react-query` | Data fetching, caching (60s stale time shared across L1-L3) |
| `react-router-dom` | URL param routing, `Link` navigation |
| `lucide-react` | Icons |
| `@/features/evidence-search` | Shared types (`EvidenceSearchResult`, `EvidenceGroupDetailResponse`), utils (`CATEGORY_COLORS`, `buildEvidenceDocument`, `categoryLabel`), hooks (`useEvidenceGroupDetail`) |
| `@/lib/api/client` | Axios instance for API calls |
