# visualize_evidence_with_expert_in_loop

> Evidence search, expert review, and chat-assisted feedback system with field-level data pivoting, delta audit trails, bilingual source traceability, and literature search.

## Overview

This module provides the Phase 4 expert-in-the-loop surface. It contains five services:

1. **SearchService** -- evidence search and group detail with field-level pivoting
2. **FeedbackService** -- expert evidence correction with delta audit
3. **DeltaAuditService** -- field-level diff computation and audit event persistence
4. **SourceLinker** -- bilingual source span traceability (original/translated)
5. **ChatService** -- conversational AI assistant for evidence review with streaming and action dispatch

The key structural concept is **field-level pivoting**: the database stores evidence as individual field extractions (e.g., `A.gene_symbol`, `B.disease_diagnosis`), but the search API pivots them into summary rows grouped by `group_id`.

## Architecture

```text
+-----------------------------------------------------------+
|                      SearchService                         |
|  1. Query canonical_evidence_items (field-level rows)      |
|  2. DB-level GROUP BY + pagination (pass 1)                |
|  3. Pivot fields into summary columns (pass 2)             |
|  4. Batch-load identifiers, titles, and availability flags  |
|  5. Build track traces with highlight building             |
|  6. Load full document text from DB or pipeline output     |
+-----------------------------------------------------------+
|                     FeedbackService                         |
|  1. Load current active_payload                             |
|  2. Merge patch fields into payload                         |
|  3. Compute field-level deltas (DeltaAuditService)          |
|  4. Update review_status (auto -> corrected if deltas)      |
|  5. Persist audit event via DeltaAuditService               |
|  6. Refresh literature_profiles and search_index read models |
+-----------------------------------------------------------+
|                    SourceLinker                              |
|  1. Load canonical item + run evidence by identity tuple    |
|  2. Resolve track-specific source spans                     |
|  3. Build bilingual (original/translated) trace pairs       |
+-----------------------------------------------------------+
|                     ChatService                             |
|  1. Manage chat sessions and messages                       |
|  2. Build evidence context from canonical items + entities  |
|  3. Detect intent (question / correction / note)            |
|  4. Route to LLM with capability-aware system prompts       |
|  5. Stream SSE events with action dispatch                  |
|  6. Apply field corrections via inline chat commands        |
+-----------------------------------------------------------+
```

## Module Layout

- `search_service.py`: `SearchService` with `search_evidence()` and `get_group_detail()`
- `feedback_service.py`: `FeedbackService` with `patch_evidence()`
- `delta_audit_service.py`: `DeltaAuditService` with `compute_deltas()`, `record_audit_event()`, `list_audit_events()`
- `source_linker.py`: `SourceLinker` with `get_track_span()` and `get_bilingual_span()`
- `chat_service.py`: `ChatService` with session/message CRUD, intent detection, correction parsing, and LLM-backed streaming reply generation
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
| `source_documents` | Metadata (title, authors) and stored document text (`original_text`, `translated_text`, `original_blocks`, `translated_blocks`) |
| `review_audit_events` | Field-level delta audit trail |
| `chat_sessions` | Chat session metadata |
| `chat_messages` | Chat message history with optional action dispatch |
| `run_evidence_items` | Phase 3 run-level evidence with source spans |
| `normalized_entities` | Phase 3 standardized entities |
| `evidence_entity_bindings` | Phase 3 evidence-to-entity bindings |
| `pipeline_run_states` | Persisted pipeline state including `output_dir` for document text lookup |
| `literature_profiles` | Read model for literature search |
| `frontend_search_index` | Read model for frontend search |

## Search API

### Evidence Search

```
GET /api/v1/evidence/search
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `gene` | string | Partial match on `A.gene_symbol` field values |
| `variant` | string | Partial match on `A.variant_hgvs_*` field values |
| `disease` | string | Partial match on `B.disease_diagnosis` field values |
| `pmid` | string | Exact match on PMID from `source_document_identifiers` |
| `doi` | string | Partial match on DOI from `source_document_identifiers` |
| `page` | int | Page number (1-indexed, default: 1) |
| `page_size` | int | Items per page (default: 50, max: 200) |

The search uses a two-pass approach:
1. DB-level `GROUP BY` + `OFFSET/LIMIT` to get current page `group_id`s
2. Fetch field details only for those groups (bounded set)
3. Batch-load document identifiers, title metadata, and stored text/block availability from `source_documents`

Gene/variant/disease filters narrow to matching `group_id`s first, then the two-pass pagination runs on the filtered set.

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
      "created_at": "2026-01-01T00:00:00Z",
      "has_full_text": true,
      "has_translation": true
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 50
}
```

`has_full_text` is derived from `source_documents.original_text` or `source_documents.original_blocks`.
`has_translation` is derived from `source_documents.translated_text` or `source_documents.translated_blocks`.
The search response exposes only booleans so index pages can show availability without loading full document text.

### Literature Search

```
GET /api/v1/literature/search
```

Returns `LiteratureSearchResponse` with `LiteratureProfileSummary` items. The response model includes fields for journal, publication year, overall confidence, evidence group count, and found/evidence field counts. The endpoint queries the `literature_profiles` read model maintained by Phase 3 and refreshed by `FeedbackService`.

### Literature Detail

```
GET /api/v1/literature/{id}/detail
```

Returns `LiteratureProfileDetailResponse` with full profile metadata and nested `EvidenceGroupSummary` items, each containing `EvidenceFieldItem` entries.

## Field Mapping

The pivot logic maps field IDs to summary columns:

| Summary Column | Field ID Prefixes |
|----------------|-------------------|
| `gene` | `A.gene_symbol`, `A.gene_aliases` |
| `variant` | `A.variant_hgvs_c`, `A.variant_hgvs_p`, `A.variant_hgvs_g`, `A.variant_legacy_name` |
| `disease` | `B.disease_diagnosis`, `B.clinical_diagnosis`, `B.hpo_terms` |
| `classification` | `J.authority_classification`, `J.clinvar_assertion` |

When field-level values are missing, gene and variant are parsed from the `group_id` string as a fallback.

## Evidence Group Detail

`GET /api/v1/evidence/groups/{group_id}` returns a group-level detail payload. It joins field-level rows by `active_payload.group_id`, pivots summary values, computes distribution counts, and attaches original/translated source highlights from `run_evidence_items.source_span`.

The endpoint is used by the Evidence frontend detail page for:
- evidence item distribution by category, field, status, and track
- selectable field-level evidence items
- original/translated traceability panes
- highlighted source snippets
- full document text (loaded from DB or pipeline output files)

### Highlight building

`_build_highlight()` constructs `EvidenceChainHighlight` payloads from stored `source_span` JSONB data. When source span offsets are malformed or fall outside the snippet text, it falls back to a value-anchor search using token-boundary regex matching. Single-letter values are skipped (too ambiguous); two-letter values require uppercase (typical gene symbols).

### Full document text loading

`_load_full_document_text()` resolves full document text from three locations in priority order:
1. Known output directory from `pipeline_run_states.state_json` (`phase_2_output.output_dir`)
2. `backend/data/pipeline/*/phase_2/{doc_id}/` (current pipeline)
3. `backend/output/cross_lingual/**/` (legacy output, matched by UUID or identifiers)

Text is concatenated from track-specific JSON files (`original.json`, `translated.json`).

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

The chat agent supports dispatchable capabilities via `ChatAction`:

| Intent | Slots | Description |
|---|---|---|
| `confirm-pipeline` | `source_type`, `query`, `identifiers`, `gene_symbol`, `disease_name`, `variant_hgvs_p`, `filename` | Submit the pipeline after conversational slot gathering + user confirmation |
| `start-pipeline` *(deprecated)* | `source_type`, `query`, `identifiers` | Legacy: opens the inline form |
| `upload-pdf` *(deprecated)* | `filename` | Legacy: opens the inline upload form |
| `search-evidence` | `gene`, `variant`, `disease`, `pmid`, `doi` | Search existing evidence |
| `classify-variant` | `variant`, `gene`, `disease` | Propose ACMG classification |
| `interpret-evidence` | `evidence_id`, `gene`, `variant` | Summarize an evidence card |
| `review-changes` | `filter` | List pending review items |
| `check-pipeline-status` | `run_id` | Show status of a pipeline run |

### Intent detection

`_detect_intent()` classifies user messages as `question`, `correction`, or `note` using pattern matching (English and Chinese patterns). Ambiguous messages (e.g. "change X to Y?") default to `question` as the less destructive intent.

### Inline corrections

When the intent is `correction` and an `evidence_id` is in context, `_parse_correction_message()` extracts field/value pairs from natural language commands (English: "change gene to BRCA2", Chinese: "gene 改为 BRCA2"). The correction is applied via `FeedbackService.patch_evidence()`, and the result is returned with delta details.

### Evidence context

When `evidence_id` is provided, the service builds a context block including the evidence card fields, associated normalized entities (via `evidence_entity_bindings`), and source text snippets. This context is injected into the LLM system prompt.

### Streaming

`stream_reply()` yields SSE events:
- `{"type": "text", "content": "..."}` -- incremental text chunks
- `{"type": "keepalive"}` -- heartbeat to prevent client disconnect during stalls
- `{"type": "action", "intent": "...", "slots": {...}}` -- action dispatch
- `{"type": "done"}` -- completion
- `{"type": "error", "message": "..."}` -- error

For standalone (non-evidence) chat, the service uses `ChatLLMProvider.route_intent_stream()` which yields reply text chunks token-by-token. The LLM returns a structured `<<<ACTION>>>` delimiter separating reply text from action JSON. The reply is streamed immediately; the action is emitted after the delimiter is detected.

Keepalive events are emitted when no LLM chunk arrives within 10 seconds to prevent SSE client timeouts.

## LLM Providers

### `ReasoningLLMProvider`

Used for high-accuracy evidence review tasks. Configured via `REASONING_LLM_*` env vars (falls back to `FAST_LLM_*`). Supports `reasoning_effort` parameter for extended thinking.

Methods:
- `generate()` -- single-shot reply
- `stream()` -- streaming reply chunks

### `ChatLLMProvider`

Used for lightweight conversational chat. Configured via `CHAT_LLM_*` env vars (falls back to `FAST_LLM_*`). Supports:
- `generate()` -- single-shot reply
- `stream()` -- streaming reply chunks
- `route_intent()` -- non-streaming structured `{reply, action}` envelope for capability dispatch
- `route_intent_stream()` -- streaming variant that yields text chunks immediately, then emits action after `<<<ACTION>>>` delimiter detection

Both providers use OpenAI-compatible `/v1/chat/completions` endpoints and manage their own `httpx.AsyncClient` lifecycle.

## Contracts

### Core enums

- `ReviewStatus`: `provisional`, `approved`, `corrected`, `rejected`
- `TargetType`: `evidence_item`, `entity`, `missed_evidence`, `task`, `native_extraction`, `translated_extraction`, `translation`, `fusion`, `report`

### Search and group models

| Type | Purpose |
|---|---|
| `EvidenceSearchResult` | Pivoted summary row with gene/variant/disease/classification, title, created_at |
| `EvidenceSearchResponse` | Paginated search response |
| `EvidenceGroupDetailResponse` | Full group detail with items, traces, distribution, full document text, blocks |
| `EvidenceGroupItem` | One field-level item within a group |
| `EvidenceFieldDistribution` | Distribution counts by category/field/status/track |
| `EvidenceTrackTrace` | Original/translated trace pair with highlight info |
| `EvidenceChainHighlight` | Highlightable source text with offset clamping and source_span reference |

### Feedback models

| Type | Purpose |
|---|---|
| `EvidenceCardPayload` | Predefined card-level schema with `DIFF_FIELDS` whitelist and `from_field_payload()` projection |
| `EvidencePatchRequest` | PATCH request body with field validation and model validator |
| `PatchResultResponse` | PATCH response with delta details |
| `DeltaEntry` | Single field change (old_value vs new_value) |
| `ReviewAuditEventResponse` | Audit event with deltas and metadata |

### Traceability models

| Type | Purpose |
|---|---|
| `TrackSpan` | Single-track source span with highlight offsets |
| `BilingualSpan` | Cross-track bilingual traceability pair |
| `SourceSpanDict` | TypedDict for structured source span JSONB fields |

### Chat models

| Type | Purpose |
|---|---|
| `ChatSessionResponse` | Session metadata with message count |
| `ChatMessageResponse` | Message with role, content, optional action |
| `ChatAction` | Action envelope with intent and slots |
| `ChatActionIntent` | Literal type for the eight capability intents |

### Literature models

| Type | Purpose |
|---|---|
| `LiteratureProfileSummary` | Summary row for literature search results |
| `LiteratureSearchResponse` | Paginated literature search response |
| `LiteratureProfileDetailResponse` | Full literature profile with evidence groups, author list, review notes |
| `EvidenceGroupSummary` | Evidence group summary within a literature profile |
| `EvidenceFieldItem` | Field item within an evidence group |
| `EvidenceGroupSummaryDict` | TypedDict for summary fields extracted from an evidence group |

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

## Testing

```bash
cd backend
uv run pytest tests/core/visualize_evidence_with_expert_in_loop/ -v
```

## Related Modules

- **Phase 3 (Standardize Entities)**: Produces the field-level evidence stored in `canonical_evidence_items` and the read models (`literature_profiles`, `frontend_search_index`)
- **Phase 3 Repository**: `StandardizationRepository.refresh_literature_profile()` and `refresh_search_index()` maintain the same read models that FeedbackService refreshes after patches
- **DAO Layer**: `CanonicalEvidenceItem`, `SourceDocumentIdentifier`, `RunEvidenceItem`, `NormalizedEntity`, `EvidenceEntityBinding`, `ChatSession`, `ChatMessage`, `ReviewAuditEvent`, `PipelineRunState`

## Performance Notes

- Field-level pivoting happens in application layer (not SQL) to maintain flexibility
- Search uses DB-level GROUP BY + pagination (pass 1) then fetches detail rows only for the current page (pass 2)
- Batch-loads identifiers and metadata in single queries to avoid N+1 problem
- Pagination is applied after grouping to ensure consistent page sizes
- Filters on gene/variant/disease narrow matching group_ids before the two-pass pagination
- Group detail deduplicates by `(field_id, track)` keeping the most recently updated row
- Full document text is loaded from DB first, then falls back to disk (pipeline output) on demand
- Chat provider uses connection pooling via httpx `AsyncClient`
- SSE keepalive events are emitted on 10-second stalls to prevent client disconnect

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `sqlalchemy[asyncio]` | Async database queries |
| `pydantic` | Response validation and typed contracts |
| `fastapi` | API routing |
| `httpx` | Async HTTP for LLM provider calls |
| `loguru` | Structured logging |
