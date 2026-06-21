# visualize_evidence_with_expert_in_loop

> Evidence search, expert review, and chat-assisted feedback system with field-level data pivoting, delta audit trails, and bilingual source traceability.

## Overview

This module provides the Phase 4 expert-in-the-loop surface. It contains five services:

1. **SearchService** -- evidence search and group detail with field-level pivoting
2. **FeedbackService** -- expert evidence correction with delta audit
3. **DeltaAuditService** -- field-level diff computation and audit event persistence
4. **SourceLinker** -- bilingual source span traceability (original/translated)
5. **ChatService** -- conversational AI assistant for evidence review

The key structural concept is **field-level pivoting**: the database stores evidence as individual field extractions (e.g., `A.gene_symbol`, `B.disease_diagnosis`), but the search API pivots them into summary rows grouped by `group_id`.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      SearchService                           │
│  1. Query canonical_evidence_items (field-level rows)       │
│  2. Group by group_id (from active_payload JSONB)           │
│  3. Pivot fields into summary columns                       │
│  4. Batch-load identifiers and titles                       │
│  5. Apply pagination (page/page_size)                       │
├─────────────────────────────────────────────────────────────┤
│                     FeedbackService                          │
│  1. Load current active_payload                              │
│  2. Merge patch fields into payload                          │
│  3. Compute field-level deltas (DeltaAuditService)           │
│  4. Update review_status (auto -> corrected if deltas)       │
│  5. Persist audit event via DeltaAuditService                │
│  6. Refresh literature_profiles and search_index read models │
├─────────────────────────────────────────────────────────────┤
│                    SourceLinker                               │
│  1. Load canonical item + run evidence by identity tuple     │
│  2. Resolve track-specific source spans                      │
│  3. Build bilingual (original/translated) trace pairs        │
├─────────────────────────────────────────────────────────────┤
│                     ChatService                              │
│  1. Manage chat sessions and messages                        │
│  2. Build evidence context from canonical items + entities   │
│  3. Detect intent (question / correction / note)             │
│  4. Route to LLM with capability-aware system prompts        │
│  5. Stream SSE events with action dispatch                   │
└─────────────────────────────────────────────────────────────┘
```

## Module Layout

- `search_service.py`: `SearchService` with `search_evidence()` and `get_group_detail()`
- `feedback_service.py`: `FeedbackService` with `patch_evidence()`
- `delta_audit_service.py`: `DeltaAuditService` with `compute_deltas()`, `record_audit_event()`, `list_audit_events()`
- `source_linker.py`: `SourceLinker` with `get_track_span()` and `get_bilingual_span()`
- `chat_service.py`: `ChatService` with session/message CRUD, intent detection, and LLM-backed reply generation
- `providers.py`: `ReasoningLLMProvider` and `ChatLLMProvider` wrappers for LLM API calls
- `contracts.py`: Pydantic response models, enums, and typed contracts

## Database Schema

Evidence is stored at field-level granularity:

```sql
canonical_evidence_items (
  canonical_evidence_id UUID,
  source_document_id UUID,
  field_id VARCHAR,           -- e.g., 'A.gene_symbol', 'B.disease_diagnosis'
  active_payload JSONB,       -- contains 'group_id', 'value', 'confidence', 'track', 'source'
  review_status VARCHAR,
  current_best_confidence DECIMAL,
  current_best_run_evidence_id UUID,
  position_hash VARCHAR,
  text_hash VARCHAR,
  entity_scope_hash VARCHAR,
  conflict_flag BOOLEAN
)
```

Each row represents one field extraction. A complete evidence group (e.g., one case study) contains multiple rows sharing the same `group_id`.

Related tables:

| Table | Purpose |
|---|---|
| `source_document_identifiers` | PMID/DOI identifiers for source documents |
| `source_documents` | Metadata (title, authors, etc.) |
| `review_audit_events` | Field-level delta audit trail |
| `chat_sessions` | Chat session metadata |
| `chat_messages` | Chat message history with optional action dispatch |
| `run_evidence_items` | Phase 3 run-level evidence with source spans |
| `normalized_entities` | Phase 3 standardized entities |
| `evidence_entity_bindings` | Phase 3 evidence-to-entity bindings |
| `literature_profiles` | Read model for literature search |
| `frontend_search_index` | Read model for frontend search |

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
      "title": "Original paper title",
      "pmid": "12345678",
      "doi": "10.1234/example",
      "gene": "BRCA1, BRCA2",
      "variant": "c.68_69delAG (p.Glu23Valfs)",
      "disease": "Hereditary breast and ovarian cancer syndrome",
      "classification": "Pathogenic",
      "field_count": 45,
      "avg_confidence": 0.92,
      "review_status": "provisional",
      "canonical_evidence_id": "uuid",
      "created_at": "2026-01-01T00:00:00Z"
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

## Evidence Group Detail

`GET /api/v1/evidence/groups/{group_id}` returns a group-level detail payload. It joins field-level rows by `active_payload.group_id`, pivots summary values, computes distribution counts, and attaches original/translated source highlights from `run_evidence_items.source_span`.

The endpoint is used by the Evidence frontend detail page for:
- evidence item distribution by category, field, status, and track
- selectable field-level evidence items
- original/translated traceability panes
- highlighted source snippets
- full document text (loaded from pipeline output files)

### Highlight building

`_build_highlight()` constructs `EvidenceChainHighlight` payloads from stored `source_span` JSONB data. When source span offsets are malformed or fall outside the snippet text, it falls back to a value-anchor search using token-boundary regex matching.

### Full document text loading

`_load_full_document_text()` resolves full document text from three locations in priority order:
1. Known output directory from `pipeline_run_states.state_json`
2. `backend/data/pipeline/*/phase_2/{doc_id}/` (current pipeline)
3. `backend/output/cross_lingual/**/` (legacy output)

## Evidence Feedback (PATCH)

### Endpoint

```
PATCH /api/v1/evidence/{canonical_evidence_id}
```

### Request

```json
{
  "fields": {
    "disease": "Corrected disease name",
    "classification": "Pathogenic"
  },
  "change_reason": "Expert correction after re-evaluation",
  "new_status": "corrected"
}
```

`EvidencePatchRequest` validates that all field names are in `EvidenceCardPayload.DIFF_FIELDS` and requires at least one of `fields` or `new_status`.

### Workflow

1. Load current `active_payload` from `canonical_evidence_items`
2. Build old card view via `EvidenceCardPayload.from_field_payload()`
3. Merge patch fields into new card
4. Compute field-level deltas via `DeltaAuditService.compute_deltas()`
5. Auto-set status to `corrected` if deltas exist and no explicit status given
6. Update `active_payload` and `review_status` in the database
7. Record `review_audit_event` with delta details
8. Refresh `literature_profiles` and `frontend_search_index` read models

### Patchable fields

`EvidenceCardPayload.DIFF_FIELDS`: `gene`, `variant`, `phenotype`, `disease`, `classification`, `evidence_strength`, `evidence_type`, `functional_impact`, `inheritance_pattern`, `zygosity`, `references`, `summary`

## Source Linker

`SourceLinker` provides bilingual source traceability by resolving canonical evidence items back to their original and translated run evidence items.

### API

| Method | Signature | Description |
|---|---|---|
| `get_track_span` | `(*, canonical_evidence_id, track) -> TrackSpan \| None` | Resolve source span for one track |
| `get_bilingual_span` | `(*, canonical_evidence_id) -> BilingualSpan` | Resolve both original and translated spans |

### Resolution strategy

1. Load canonical item to get identity fields and `current_best_run_evidence_id`
2. If the best run matches the requested track, use it directly (fast path)
3. Otherwise, find a run item by identity tuple (`source_document_id`, `field_id`, `position_hash`, `entity_scope_hash`) + track

## Chat Service

`ChatService` manages conversational interactions for evidence review.

### Capabilities

The chat agent supports eight dispatchable capabilities via `ChatAction`:

| Intent | Slots | Description |
|---|---|---|
| `confirm-pipeline` | `source_type`, `query`, `identifiers`, `gene_symbol`, `disease_name`, `variant_hgvs_p`, `filename` | Submit the pipeline after conversational slot gathering + user confirmation |
| `start-pipeline` *(deprecated)* | `source_type`, `query`, `identifiers` | Legacy: opens the inline form. The LLM must no longer emit this; use `confirm-pipeline` instead |
| `upload-pdf` *(deprecated)* | `filename` | Legacy: opens the inline upload form. Use `confirm-pipeline` with `source_type=local` instead |
| `search-evidence` | `gene`, `variant`, `disease`, `pmid`, `doi` | Search existing evidence |
| `classify-variant` | `variant`, `gene`, `disease` | Propose ACMG classification |
| `interpret-evidence` | `evidence_id`, `gene`, `variant` | Summarize an evidence card |
| `review-changes` | `filter` | List pending review items |
| `check-pipeline-status` | `run_id` | Show status of a pipeline run |

### Intent detection

`_detect_intent()` classifies user messages as `question`, `correction`, or `note` using pattern matching. Ambiguous messages (e.g. "change X to Y?") default to `question` as the less destructive intent.

### Evidence context

When `evidence_id` is provided, the service builds a context block including the evidence card fields, associated normalized entities (via `evidence_entity_bindings`), and source text snippets. This context is injected into the LLM system prompt.

### Streaming

`stream_reply()` yields SSE events:
- `{"type": "text", "content": "..."}` -- incremental text chunks
- `{"type": "action", "intent": "...", "slots": {...}}` -- action dispatch
- `{"type": "done"}` -- completion
- `{"type": "error", "message": "..."}` -- error

For standalone (non-evidence) chat, the service uses `ChatLLMProvider.route_intent()` which asks the LLM to return a structured `{reply, action}` JSON envelope. The reply is streamed first, then the action is emitted if present.

## LLM Providers

### `ReasoningLLMProvider`

Used for high-accuracy evidence review tasks. Configured via `REASONING_LLM_*` env vars (falls back to `FAST_LLM_*`). Supports `reasoning_effort` parameter for extended thinking.

### `ChatLLMProvider`

Used for lightweight conversational chat. Configured via `CHAT_LLM_*` env vars (falls back to `FAST_LLM_*`). Supports:
- `generate()` -- single-shot reply
- `stream()` -- streaming reply chunks
- `route_intent()` -- structured `{reply, action}` envelope for capability dispatch

Both providers use OpenAI-compatible `/v1/chat/completions` endpoints.

## Contracts

### Core enums

- `ReviewStatus`: `provisional`, `approved`, `corrected`, `rejected`
- `TargetType`: `evidence_item`, `entity`, `missed_evidence`, `task`, `native_extraction`, `translated_extraction`, `translation`, `fusion`, `report`

### Search and group models

| Type | Purpose |
|---|---|
| `EvidenceSearchResult` | Pivoted summary row with gene/variant/disease/classification, title, created_at |
| `EvidenceSearchResponse` | Paginated search response |
| `EvidenceGroupDetailResponse` | Full group detail with items, traces, distribution, full document text |
| `EvidenceGroupItem` | One field-level item within a group |
| `EvidenceFieldDistribution` | Distribution counts by category/field/status/track |
| `EvidenceTrackTrace` | Original/translated trace pair with highlight info |
| `EvidenceChainHighlight` | Highlightable source text with offset clamping |

### Feedback models

| Type | Purpose |
|---|---|
| `EvidenceCardPayload` | Predefined card-level schema with `DIFF_FIELDS` whitelist |
| `EvidencePatchRequest` | PATCH request body with field validation |
| `PatchResultResponse` | PATCH response with delta details |
| `DeltaEntry` | Single field change (old_value vs new_value) |
| `ReviewAuditEventResponse` | Audit event with deltas and metadata |

### Traceability models

| Type | Purpose |
|---|---|
| `TrackSpan` | Single-track source span with highlight offsets |
| `BilingualSpan` | Cross-track bilingual traceability pair |

### Chat models

| Type | Purpose |
|---|---|
| `ChatSessionResponse` | Session metadata with message count |
| `ChatMessageResponse` | Message with role, content, optional action |
| `ChatAction` | Action envelope with intent and slots |
| `ChatActionIntent` | Literal type for the six capability intents |

### Literature models

| Type | Purpose |
|---|---|
| `LiteratureProfileSummary` | Summary row for literature search |
| `LiteratureSearchResponse` | Paginated literature search response |
| `LiteratureProfileDetailResponse` | Full literature profile with evidence groups |
| `EvidenceGroupSummary` | Evidence group summary within a literature profile |
| `EvidenceFieldItem` | Field item within an evidence group |

## Usage Example

```python
from src.api.deps import get_db_session
from src.core.visualize_evidence_with_expert_in_loop.search_service import SearchService
from src.core.visualize_evidence_with_expert_in_loop.feedback_service import FeedbackService
from src.core.visualize_evidence_with_expert_in_loop.source_linker import SourceLinker
from src.core.visualize_evidence_with_expert_in_loop.chat_service import ChatService

async with get_db_session() as session:
    # Search
    search = SearchService(session)
    results = await search.search_evidence(gene="BRCA1", page=1, page_size=50)
    for item in results.items:
        print(f"Gene: {item.gene}, Disease: {item.disease}")

    # Feedback
    feedback = FeedbackService(session)
    result = await feedback.patch_evidence(
        canonical_evidence_id=evidence_id,
        patch=EvidencePatchRequest(fields={"disease": "Corrected name"}),
    )

    # Traceability
    linker = SourceLinker(session)
    span = await linker.get_bilingual_span(canonical_evidence_id=evidence_id)

    # Chat
    chat = ChatService(session, chat_provider=ChatLLMProvider())
    async for event in chat.stream_reply(
        session_id=session_id,
        user_message="What evidence supports this classification?",
        evidence_id=evidence_id,
    ):
        print(event)
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
uv run pytest tests/core/visualize_evidence_with_expert_in_loop/ -v
```

## Related Modules

- **Phase 3 (Standardize Entities)**: Produces the field-level evidence stored in `canonical_evidence_items` and the read models (`literature_profiles`, `frontend_search_index`)
- **Phase 3 Repository**: `StandardizationRepository.refresh_literature_profile()` and `refresh_search_index()` maintain the same read models that FeedbackService refreshes after patches
- **DAO Layer**: `CanonicalEvidenceItem`, `SourceDocumentIdentifier`, `RunEvidenceItem`, `NormalizedEntity`, `EvidenceEntityBinding`, `ChatSession`, `ChatMessage`, `ReviewAuditEvent`

## Performance Notes

- Field-level pivoting happens in application layer (not SQL) to maintain flexibility
- Batch-loads identifiers and metadata in single queries to avoid N+1 problem
- Pagination is applied after grouping to ensure consistent page sizes
- Filters on gene/variant/disease trigger a two-query pattern:
  1. Find matching `group_id`s
  2. Fetch all fields for those groups
- Group detail deduplicates by `(field_id, track)` keeping the most recently updated row
- Full document text is loaded from disk on demand (not stored in DB)
- Chat provider uses connection pooling via httpx `AsyncClient`

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `sqlalchemy[asyncio]` | Async database queries |
| `pydantic` | Response validation and typed contracts |
| `fastapi` | API routing |
| `httpx` | Async HTTP for LLM provider calls |
| `loguru` | Structured logging |
