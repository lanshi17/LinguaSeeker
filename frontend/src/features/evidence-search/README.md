# Evidence Search Feature

> Literature-level search and review for extracted evidence. Queries evidence groups by gene/variant/disease, aggregates results into literature rows, and provides bilingual full-document highlighting with annotation support.

## Structure

```
features/evidence-search/
|-- index.ts                              # Barrel exports
|-- components/
|   |-- EvidenceSearchView.tsx            # Page-level orchestrator: form + results table
|   |-- EvidenceSearchForm.tsx            # Gene, variant, disease, PMID/DOI filter inputs
|   |-- EvidenceResultsTable.tsx          # Literature-row result cards with pagination
|   |-- EvidenceDetailView.tsx            # Literature overview + compare mode
|   |-- EvidenceAuditHistory.tsx          # Audit history for a specific evidence item
|   |-- EvidenceCorrectionForm.tsx        # Form for correcting evidence field values
|   |-- EvidenceHighlightText.tsx         # Reusable single-span text highlighter
|   |-- EvidenceDetailSkeleton.tsx        # Loading skeleton for detail view
|   |-- EvidenceTableSkeleton.tsx         # Loading skeleton for results table
|   |-- evidenceTableColumns.tsx          # Column definitions for the results table
|   |-- LiteratureOverview.tsx            # Literature document overview card
|   |-- BilingualComparison.tsx           # Original/translated value-anchored snippet panel
|   |-- BilingualCompareView.tsx          # Full bilingual compare view (document reader)
|   |-- MarkdownDocumentViewer.tsx        # Markdown-based document viewer with highlights
|   +-- annotationLayer.tsx              # User annotation overlay for document paragraphs
|-- hooks/
|   |-- useEvidenceSearch.ts              # Paginated search query state
|   +-- useEvidenceGroupDetail.ts         # Group detail query state
|-- services/
|   |-- evidenceSearch.ts                 # Re-exports from @/api/evidence
|   +-- evidenceCorrection.ts             # patchEvidence(), listAuditEvents()
|-- types/
|   |-- evidenceSearch.ts                 # All API boundary types (see below)
|   +-- annotations.ts                    # UserAnnotation, AnnotationCreateRequest, etc.
+-- utils/
    |-- evidenceDocument.ts               # Full-document builder, highlight helpers, category colors
    |-- literatureRows.ts                 # Literature-row aggregation, compare href builder
    +-- categoryStyles.ts                 # Category chip/mark/label style utilities
```

## Usage

```tsx
import { EvidenceSearchView, EvidenceDetailView, BilingualComparison } from "@/features/evidence-search";

// Search page
<EvidenceSearchView />

// Detail page (via route: /evidence/detail?groupId=...)
<EvidenceDetailView />

// Hook usage
const { results, filters, updateFilter, setPage } = useEvidenceSearch();
```

## Key Components

| Component | Description |
|-----------|-------------|
| `EvidenceSearchView` | Top-level orchestrator: search form + results table. Navigates to `/evidence/detail?groupId=...` on row click. |
| `EvidenceSearchForm` | Gene, variant, disease, PMID/DOI inputs with search and clear buttons. |
| `EvidenceResultsTable` | Literature-row cards with pagination. Groups evidence by source document. |
| `EvidenceDetailView` | Literature overview + evidence detail with bilingual compare mode. |
| `BilingualComparison` | Side-by-side original/translated value-anchored snippet panel. |
| `BilingualCompareView` | Full bilingual document reader with highlight rendering. |
| `EvidenceHighlightText` | Reusable component that renders a single text span with a highlight mark. |
| `MarkdownDocumentViewer` | Renders full document text as Markdown with evidence highlight overlays. |
| `annotationLayer.tsx` | User annotation overlay for document paragraphs (create, edit, delete annotations). |
| `LiteratureOverview` | Card showing literature metadata (title, PMID, DOI, gene, variant). |
| `EvidenceCorrectionForm` | Form for submitting evidence field corrections. |

## Hooks

| Hook | Signature | Description |
|------|-----------|-------------|
| `useEvidenceSearch` | `() => { results, total, page, pageSize, isLoading, isFetching, error, filters, updateFilter, applyFilters, clearFilters, setPage }` | Paginated search query state. Default page size 50. Uses `keepPreviousData`. |
| `useEvidenceGroupDetail` | `(groupId?, sourceDocumentId?) => { detail, isLoading, isFetching, error, refetch }` | Single evidence group detail query. |

## Key Utilities

### `evidenceDocument.ts`

| Export | Description |
|--------|-------------|
| `buildEvidenceDocument(detail, track, enabledTones?, selectedId?, enabledCategories?)` | Constructs `EvidenceDocument` with paragraphs and highlight ranges from traces. Supports original/translated tracks, tone filtering, category filtering, and selected-evidence focus. |
| `CATEGORY_COLORS` | Per-category color palette (A-J) with `chip`, `mark`, `label`, and `hex` values. |
| `EVIDENCE_CATEGORIES` | Ordered list of category keys: `["A", "B", ..., "J"]` |
| `countEvidenceCategories(items)` | Counts evidence items per category letter. |
| `evidenceToneForItem(item)` | Maps field to highlight tone: `gene`, `variant`, `disease`, `classification`, `functional`, `neutral`. |
| `hasTranslatedDocumentText(detail)` | Returns true if translated document text or translated traces exist. |

### `literatureRows.ts`

| Export | Description |
|--------|-------------|
| `buildLiteratureRows(results)` | Groups `EvidenceSearchResult[]` by `source_document_id`. Aggregates genes, variants, diseases, classifications, confidence, and review status. |
| `findInitialEvidenceId(detail, requestedId?)` | Finds the best initial evidence ID for navigation (requested > traceable > first). |
| `buildBilingualCompareHref(groupId, evidenceId?)` | Builds compare-mode detail URL: `/evidence/detail?groupId=...&view=compare`. |

### `categoryStyles.ts`

| Export | Description |
|--------|-------------|
| `categoryChipStyle(category?)` | Returns Tailwind chip class string for a category letter. |
| `categoryMarkStyle(category?)` | Returns Tailwind mark/highlight class string. |
| `categoryLabel(category?)` | Returns human-readable label for a category letter. |

## Types

### Search and Results

| Type | Description |
|------|-------------|
| `EvidenceSearchQuery` | Query params: gene, variant, disease, pmid, doi, page, page_size |
| `EvidenceSearchResult` | Single result: group_id, source_document_id, title, pmid, doi, gene, variant, disease, classification, field_count, avg_confidence, review_status, canonical_evidence_id |
| `EvidenceSearchResponse` | Paginated response: items, total, page, page_size |

### Group Detail

| Type | Description |
|------|-------------|
| `EvidenceGroupDetailResponse` | Full group: group_id, source_document_id, title, pmid, doi, original/translated_document_text, original/translated_blocks, gene, variant, disease, classification, item_count, avg_confidence, distribution, items, traces |
| `EvidenceGroupItem` | Single field: canonical_evidence_id, field_id, field_name, category, value, review_status, confidence, track, page |
| `EvidenceFieldDistribution` | Aggregated counts: by_category, by_field, by_status, by_track |
| `ContentBlock` | MinerU structured block: type, page_idx, bbox, text, table_body, img_path, list_items, code_body, etc. |

### Traces and Highlights

| Type | Description |
|------|-------------|
| `EvidenceTrackTrace` | Trace: canonical_evidence_id, field_id, original/translated highlight spans, alignment_confidence |
| `EvidenceChainHighlight` | Highlight span: text, highlight_start, highlight_end, page, source_span |
| `EvidenceHighlightTone` | `"classification" \| "disease" \| "functional" \| "gene" \| "neutral" \| "variant"` |
| `EvidenceDocument` | Built document: track + paragraphs with highlights |
| `EvidenceDocumentParagraph` | Paragraph: id, page, text, highlights[] |
| `EvidenceDocumentHighlight` | Located highlight: evidenceId, fieldId, label, tone, category, start, end, selected |

### Corrections and Audit

| Type | Description |
|------|-------------|
| `EvidencePatchRequest` | PATCH body: fields, change_reason?, new_status? |
| `PatchResultResponse` | PATCH result: canonical_evidence_id, old/new_status, deltas, field_deltas |
| `ReviewStatusValue` | `"provisional" \| "approved" \| "corrected" \| "rejected"` |
| `ReviewAuditEventResponse` | Audit event: review_event_id, canonical_evidence_id, reviewer_id, target_type, old/new_status, field_deltas, change_reason, created_at |

### Annotations

| Type | Description |
|------|-------------|
| `UserAnnotation` | Annotation: id, source_document_id, track, paragraph_id, start/end_offset, color, note, author, created_at, updated_at |
| `AnnotationCreateRequest` | Create body: track, paragraph_id, start/end_offset, color?, note?, author? |
| `AnnotationUpdateRequest` | Update body: color?, note? |
| `AnnotationListResponse` | Response: items[] |
| `ANNOTATION_COLORS` | Default palette: 6 colors (amber, blue, green, pink, violet, orange) |

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/evidence/search` | GET | Search evidence groups with filters and pagination |
| `/api/v1/evidence/groups/detail` | GET | Fetch full detail for a single evidence group |
| `/api/v1/evidence/{canonical_evidence_id}` | PATCH | Correct evidence fields and/or change review status |
| `/api/v1/delta-audit/` | GET | List review audit events |

## Testing

```bash
cd frontend
bun run test tests/evidence-search/
```

Test files: `BilingualComparison.test.tsx`, `EvidenceHighlightText.test.tsx`, `literatureRows.test.ts`

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `@tanstack/react-query` | Data fetching, caching, polling |
| `react-router-dom` | URL params, navigation, Link |
| `react-markdown` + `remark-gfm` | Markdown rendering for document viewer |
| `lucide-react` | Icons |
| `antd` | Table, Card, Input, Button, Tag, Typography |
| `@/lib/api/client` | Axios instance for API calls |
| `@/components/ui` | Badge, Skeleton, ErrorBoundary |
