# Evidence DB — Variant-Centric Evidence Database

> Three-level browse experience for clinical genetics evidence, organized by variant identifier. Users drill from a variant index → variant detail with evidence fields and literature references → bilingual document comparison with multi-color category highlighting.

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

## Architecture

```
                    ┌─────────────────────────────────────────────────┐
                    │              EvidenceDbPage                      │
                    │         (useParams router dispatch)              │
                    └──────┬──────────────┬───────────────────────────┘
                           │              │
              ┌────────────▼──┐  ┌───────▼──────────┐  ┌──────────────────┐
              │ VariantIndex  │  │ VariantDetail    │  │ BilingualEvidence │
              │    View       │  │     View         │  │      View         │
              │ (L1 grid)     │  │ (L2 detail)      │  │ (L3 comparison)   │
              └───────┬───────┘  └────────┬─────────┘  └────────┬──────────┘
                      │                   │                     │
                      ▼                   ▼                     ▼
              ┌──────────────────────────────────────────────────────────┐
              │                    Hooks Layer                           │
              │  useVariantIndex    useVariantDetail    useEvidenceGroup  │
              │  (React Query)      (React Query)        Detail (RQ)      │
              └──────────────────────────────────────────────────────────┘
                      │                   │                     │
                      ▼                   ▼                     ▼
              ┌──────────────────────────────────────────────────────────┐
              │                  Services Layer                          │
              │  fetchAllEvidence     fetchEvidenceGroupDetail           │
              │  (GET /evidence/search)  (GET /evidence/groups/detail)   │
              └──────────────────────────────────────────────────────────┘
                      │
                      ▼
              ┌──────────────────────────────────────────────────────────┐
              │              Aggregation Layer (client-side)             │
              │  aggregateVariants → groups flat results by              │
              │  gene:variant:disease into VariantIndexEntry[]           │
              │  filterAndPaginateVariants → applies filters + pagination│
              └──────────────────────────────────────────────────────────┘
```

### Data Flow

1. **L1**: `fetchAllEvidence()` fetches all evidence search results (page_size=200) → `aggregateVariants()` splits multi-variant values (e.g. `c.316C>T; c.502C>T`) into one row per variant site, then groups by `gene:variant:disease` composite key → `filterAndPaginateVariants()` applies client-side filters and pagination → React Query caches with 60s stale time.

2. **L2**: Reuses the L1 index query to find the variant entry → fetches `EvidenceGroupDetailResponse` for each `group_id` via `Promise.allSettled` → flattens all evidence items across groups → builds `LiteratureReference[]` for the sidebar.

3. **L3**: Finds the `group_id` matching the `sourceDocumentId` from L2's data → fetches full group detail → `buildEvidenceDocument()` constructs paragraphs with highlight ranges from traces → category toggles filter which highlights are visible → evidence navigator selects a specific field to emphasize.

## Public API

### Components

| Component | Props | Description |
|-----------|-------|-------------|
| `VariantIndexView` | — | L1: searchable variant grid with stats, classification filters, pagination |
| `VariantDetailView` | `variantSlug: string` | L2: variant hero with confidence ring, evidence by category, literature sidebar |
| `BilingualEvidenceView` | `variantSlug: string`, `sourceDocumentId: string` | L3: bilingual document reader with category highlighting |

### Hooks

| Hook | Returns | Description |
|------|---------|-------------|
| `useVariantIndex` | `{ items, total, page, pageSize, stats, isLoading, isFetching, error, filters, updateFilter, setPage, clearFilters }` | Fetches + aggregates + filters variant index data |
| `useVariantDetail` | `{ detail, isLoading, isFetching, error }` | Fetches variant entry + all group details for a single variant |

### Types

| Type | Description |
|------|-------------|
| `VariantIndexEntry` | Aggregated variant: slug, gene, variant, disease, classification, counts, category distribution, groupIds |
| `VariantIndexData` | Paginated response: items, total, page, pageSize, stats |
| `VariantDetailData` | L2 response: entry, evidenceGroups, literature, allItems |
| `LiteratureReference` | Sidebar reference: sourceDocumentId, title, pmid, doi, groupId, fieldCount, categories |
| `VariantIndexFilters` | Filter state: gene, variant, disease, classification, page, pageSize |
| `ClassificationLevel` | `"pathogenic" \| "likely_pathogenic" \| "uncertain" \| "likely_benign" \| "benign"` |

### Utils

| Function | Description |
|----------|-------------|
| `classifyLevel(classification)` | Maps classification string → `ClassificationLevel` |
| `classificationColor(level)` | Hex color for dark-theme rendering |
| `classificationBadgeStyle(level)` | Inline CSS style object for badge (bg, text, border) — used in VariantIndexView/VariantDetailView |
| `classificationLabel(level)` / `classificationShortLabel(level)` | Human-readable / abbreviated labels |
| `aggregateVariants(results)` | Splits multi-variant values into one row per variant site, then groups flat `EvidenceSearchResult[]` → `VariantIndexEntry[]` (split rows share the original `group_id` for L2 detail navigation) |
| `filterAndPaginateVariants(entries, filters)` | Applies filters + pagination → `VariantIndexData`; aggregate stats count distinct evidence groups / literature to avoid double-counting split rows |

## Design: Unified Medical-Teal Light Theme

The evidence DB uses a light theme matching the dashboard's "Accessible & Ethical" design system (WCAG AAA, medical teal primary). Consistent with the rest of the application: white cards on gray-50 background, teal-600 primary, Figtree/Fraunces/JetBrains Mono typography.

**Color system:**
- Primary: `#0891B2` (teal-600) — shared with dashboard
- Pathogenicity scale: `#B91C1C` (P) → `#DC2626` (LP) → `#6B7280` (VUS) → `#0D9488` (LB) → `#0F766E` (B) — all WCAG AA on white
- Evidence categories A–J: each has a hex color (defined in `@/features/evidence-search/utils/evidenceDocument.ts` `CATEGORY_COLORS`)
- CSS utilities: `.edb-hero` (teal-tinted gradient), `.edb-card` (white card), `.edb-card-clickable` (teal hover), `.edb-ring` (confidence ring), `.edb-cat-strip`, `.edb-scroll`, `.edb-stagger` (defined in `src/globals.css`)

**Highlight rendering (L3):** Category marks use inline style objects from `categoryMarkStyle()` (e.g., amber bg/text/border) designed for light backgrounds. Selected evidence gets a teal `borderColor` focus ring.

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `@tanstack/react-query` | Data fetching, caching (60s stale time shared across L1–L3) |
| `react-router-dom` | URL param routing, `Link` navigation |
| `lucide-react` | Icons |
| `@/features/evidence-search` | Shared types (`EvidenceSearchResult`, `EvidenceGroupDetailResponse`), utils (`CATEGORY_COLORS`, `buildEvidenceDocument`, `categoryLabel`), hooks (`useEvidenceGroupDetail`) |
| `@/lib/api/client` | Axios instance for API calls |

## API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/evidence/search` | GET | Fetch all evidence search results (page_size=200 for aggregation) |
| `/api/v1/evidence/groups/detail` | GET | Fetch full detail for a single evidence group (items + traces + document text) |

## Extension Guide

### Adding a new filter dimension

1. Add the field to `VariantIndexFilters` in `types/variantDb.ts`
2. Add filter logic in `filterAndPaginateVariants()` in `utils/variantAggregation.ts`
3. Add UI control in `VariantIndexView.tsx` and wire via `updateFilter()`

### Changing the color palette

- **Pathogenicity colors**: Edit `classificationColor()` and `classificationBadgeStyle()` in `utils/pathogenicity.ts`
- **Category colors**: Edit `CATEGORY_COLORS` in `@/features/evidence-search/utils/evidenceDocument.ts` (shared with evidence-search feature)
- **Dark theme utilities**: Edit the `.edb-*` classes in `src/globals.css`

### Adding a new level

1. Create the component in `components/`
2. Add the route in `App.tsx` and the param dispatch in `EvidenceDbPage.tsx`
3. Export from `index.ts`
