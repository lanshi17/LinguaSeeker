# Phase 4: Evidence Visualization & Expert Feedback Loop

> P0 feature slice enabling clinical experts to review extracted evidence, provide corrections, and engage in AI-assisted dialogue.

## Quick Start

```python
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.visualize_evidence_with_expert_in_loop.feedback_service import FeedbackService
from src.core.visualize_evidence_with_expert_in_loop.contracts import EvidencePatchRequest, ReviewStatus

# Patch an evidence card
service = FeedbackService(session)
patch = EvidencePatchRequest(
    fields={"phenotype": "Fabry disease", "classification": "Pathogenic"},
    change_reason="Bilingual correction",
)
result = await service.patch_evidence(
    canonical_evidence_id=evidence_id,
    patch=patch,
)
print(result.new_status)  # ReviewStatus.CORRECTED
```

## Architecture

```
                     API Layer (src/api/v1/)
                     ┌─────────────────────────────┐
                     │ evidence.py  │  chat.py      │
                     │ delta_audit  │  source_link  │
                     └──────────┬───────────────────┘
                                │
                     ┌──────────▼───────────────────┐
                     │   Service Layer (this module) │
                     ├───────────────────────────────┤
                     │  feedback_service.py          │
                     │  delta_audit_service.py       │
                     │  chat_service.py              │
                     │  source_linker.py             │
                     ├───────────────────────────────┤
                     │  contracts.py   providers.py  │
                     └──────────┬───────────────────┘
                                │
                     ┌──────────▼───────────────────┐
                     │  DAO Layer (src/dao/models.py) │
                     │  review_audit_events          │
                     │  chat_sessions                │
                     │  chat_messages                │
                     └──────────────────────────────┘
```

**Data flow:**
1. Expert patches evidence card → `FeedbackService` computes deltas → `DeltaAuditService` records audit event
2. Expert asks question → `ChatService` detects intent → `ReasoningLLMProvider` streams reply
3. Expert traces source → `SourceLinker` retrieves bilingual spans via `canonical_evidence_id` anchor

## Public API

### contracts.py

| Type | Kind | Description |
|------|------|-------------|
| `ReviewStatus` | `str, Enum` | State machine: `provisional → approved \| corrected \| rejected` |
| `TargetType` | `str, Enum` | Feedback targets: `evidence_item`, `entity`, `missed_evidence` (+ 6 declared) |
| `EvidenceCardPayload` | `BaseModel` | Fixed-schema card with `DIFF_FIELDS: ClassVar` for delta diff |
| `DeltaEntry` | `BaseModel` | Single field change; validates `field` against `DIFF_FIELDS` |
| `EvidencePatchRequest` | `BaseModel` | PATCH body with `fields`, `change_reason`, `new_status` |
| `BilingualSpan` | `BaseModel` | Cross-track traceability result with `original_track` + `translated_track` |
| `ChatSessionResponse` | `BaseModel` | Session response with `message_count` |
| `ChatMessageResponse` | `BaseModel` | Message response with `role`, `content`, optional `evidence_id` |

### FeedbackService

```python
service = FeedbackService(session: AsyncSession)
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `patch_evidence` | `(*, canonical_evidence_id, patch, reviewer_id=None) → PatchResult` | Apply patch, compute deltas, auto-transition to CORRECTED if fields changed |

### DeltaAuditService

```python
service = DeltaAuditService()
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `compute_deltas` | `(old: EvidenceCardPayload, new: EvidenceCardPayload) → list[DeltaEntry]` | **Static.** Returns empty list if payloads are identical (zero-noise). |
| `record_audit_event` | `(session, *, canonical_evidence_id, ...) → ReviewAuditEvent` | Persist audit event with JSONB field_deltas |
| `list_audit_events` | `(session, *, canonical_evidence_id=None, limit=100) → list` | Query audit events with optional filters |

### ChatService

```python
service = ChatService(session: AsyncSession)
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `create_session` | `(*, processing_run_id, user_id=None) → ChatSessionResponse` | Create session bound to a processing run |
| `append_message` | `(*, session_id, role, content, ...) → ChatMessageResponse` | Append message to session |
| `list_messages` | `(*, session_id, limit=100) → list[ChatMessageResponse]` | Chronological message listing |
| `list_sessions` | `(*, processing_run_id) → list[ChatSessionResponse]` | All sessions for a run, with message counts |
| `generate_reply` | `(*, session_id, user_message, evidence_id=None) → str \| None` | AI reply for questions; `None` for notes |
| `stream_reply` | `(*, session_id, user_message, evidence_id=None) → AsyncIterator[dict]` | SSE events: `{type: text\|done\|error}` |

### SourceLinker

```python
linker = SourceLinker(session: AsyncSession)
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_track_span` | `(*, canonical_evidence_id, track) → TrackSpan \| None` | Single-track span from `source_span` JSONB |
| `get_bilingual_span` | `(*, canonical_evidence_id) → BilingualSpan` | Both tracks; `alignment_confidence=1.0` if both present |

### ReasoningLLMProvider

```python
provider = ReasoningLLMProvider()
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `generate` | `(*, system_prompt, user_message, context="") → str` | Single-shot completion via OpenAI-compatible API |
| `stream` | `(*, system_prompt, user_message, context="") → AsyncIterator[str]` | SSE streaming; parses `data: [DONE]` terminator |

## Internal Design

### Intent Detection

`ChatService._detect_intent` uses regex patterns to classify messages:

- **Correction** — `change ... to`, `update ... to`, `改为`, `修改...为`
- **Question** — `?`, `what`, `why`, `how`, `什么`, `为什么`
- **Note** — everything else (no AI reply generated)

### Delta Diff

`DeltaAuditService.compute_deltas` iterates `EvidenceCardPayload.DIFF_FIELDS` (12 fields) and compares old vs new values. Lists (e.g. `references`) are compared as wholes, not element-wise. Returns empty list when payloads are identical — no audit event is created for no-op patches.

### Field Injection Prevention

`DeltaEntry.validate_field` and `EvidencePatchRequest.validate_fields` reject any field name not in `EvidenceCardPayload.DIFF_FIELDS`. This prevents arbitrary attribute access on Pydantic models.

### Review Status State Machine

```
provisional ──→ approved
provisional ──→ corrected ──→ approved
provisional ──→ rejected
```

Explicit `new_status` in a patch overrides the auto-transition to CORRECTED.

## Usage Patterns

### Patch evidence and review audit trail

```python
from src.core.visualize_evidence_with_expert_in_loop.feedback_service import FeedbackService
from src.core.visualize_evidence_with_expert_in_loop.contracts import EvidencePatchRequest
from src.core.visualize_evidence_with_expert_in_loop.delta_audit_service import DeltaAuditService

service = FeedbackService(session)
patch = EvidencePatchRequest(
    fields={"phenotype": "Fabry 病", "gene": "GLA"},
    change_reason="Bilingual correction",
)
result = await service.patch_evidence(canonical_evidence_id=eid, patch=patch)

# Query audit history
audit = DeltaAuditService()
events = await audit.list_audit_events(session, canonical_evidence_id=eid)
```

### Chat with AI-assisted evidence review

```python
from src.core.visualize_evidence_with_expert_in_loop.chat_service import ChatService

service = ChatService(session)
session_resp = await service.create_session(processing_run_id=run_id)

# User asks a question → AI generates reply
await service.append_message(
    session_id=session_resp.chat_session_id,
    role="user", content="What gene is implicated?",
    evidence_id=evidence_id,
)
reply = await service.generate_reply(
    session_id=session_resp.chat_session_id,
    user_message="What gene is implicated?",
    evidence_id=evidence_id,
)

# User adds a note → no AI reply
reply = await service.generate_reply(
    session_id=session_resp.chat_session_id,
    user_message="Need to verify this later",
)
assert reply is None
```

### Bilingual source traceability

```python
from src.core.visualize_evidence_with_expert_in_loop.source_linker import SourceLinker

linker = SourceLinker(session)
span = await linker.get_bilingual_span(canonical_evidence_id=evidence_id)
# span.original_track.block_text → "Patient diagnosed with Fabry disease..."
# span.translated_track.block_text → "患者30岁时被诊断为法布雷病。"
```

### SSE streaming (API layer)

```python
# In API route handler:
async def event_generator():
    async for event in service.stream_reply(
        session_id=session_id,
        user_message="Explain the evidence strength",
        evidence_id=evidence_id,
    ):
        yield f"data: {json.dumps(event)}\n\n"

return StreamingResponse(event_generator(), media_type="text/event-stream")
```

## Testing

```bash
cd backend
uv run pytest tests/core/visualize_evidence_with_expert_in_loop/ -v
```

Tests use SQLite in-memory via the `db_session` fixture (JSONB swapped to JSON for compatibility). LLM calls are mocked via `unittest.mock.patch`.

| Test file | Covers | Tests |
|-----------|--------|-------|
| `test_contracts.py` | Pydantic models, enums, field validation | 9 |
| `test_delta_audit.py` | `compute_deltas` pure logic | 6 |
| `test_feedback_service.py` | `patch_evidence` with DB | 5 |
| `test_source_linker.py` | `get_track_span`, `get_bilingual_span` | 4 |
| `test_chat_service.py` | Session/message CRUD | 5 |
| `test_chat_ai.py` | Context building, intent detection, AI reply | 6 |
| `test_chat_sse.py` | SSE streaming, error handling | 3 |

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `pydantic` v2 | Typed contracts with `field_validator` |
| `sqlalchemy` 2.0 async | ORM + `AsyncSession` |
| `httpx` | LLM HTTP client (sync + streaming) |
| `loguru` | Structured logging |
| `fastapi` | API routes (upstream consumer) |
