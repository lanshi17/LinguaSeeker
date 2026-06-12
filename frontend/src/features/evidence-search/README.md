# Evidence Search Feature

> Literature-level search and review for evidence. Queries evidence groups, aggregates into literature rows, and provides bilingual full-document highlighting.

## Structure

```
features/evidence-search/
├── components/
│   ├── EvidenceSearchView.tsx       Page-level orchestrator
│   ├── EvidenceSearchForm.tsx       Gene, variant, disease, PMID filters
│   ├── EvidenceResultsTable.tsx     Literature-row result cards
│   ├── EvidenceDetailView.tsx       Literature overview + compare mode
│   └── EvidenceHighlightText.tsx    Reusable single-span highlighter
├── hooks/
│   ├── useEvidenceSearch.ts         Paginated search query state
│   └── useEvidenceGroupDetail.ts    Group detail query state
├── services/evidenceSearch.ts       API calls
├── types/evidenceSearch.ts          API boundary types
├── utils/
│   ├── evidenceDocument.ts          Full-document reader and highlight helpers
│   └── literatureRows.ts            Literature-row aggregation
└── index.ts
```

## Usage

```tsx
<EvidenceSearchView />
const { results, filters, updateFilter, setPage } = useEvidenceSearch();
```

## Key Utilities

| Helper | Description |
|--------|-------------|
| `buildLiteratureRows(results)` | Groups results by `source_document_id` |
| `buildEvidenceDocument(detail, track)` | Full-document reader with highlight ranges |
| `buildBilingualCompareHref(groupId, evidenceId?)` | Compare-mode detail URL |
| `evidenceToneForItem(item)` | Maps fields to highlight tones |
| `BilingualComparison` | Original/translated value-anchored snippet panel; used in compare mode |