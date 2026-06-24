# API v1 Routes

> REST endpoint definitions for LinguaSeeker's v1 API. All routes are mounted under `/api/v1` and delegate to the orchestrator or Phase 4 services via injected dependencies.

## Route Map

```
/api/v1
├── /auth
│   ├── POST   /login                                   # Validate password, set signed session cookie
│   ├── POST   /logout                                  # Delete session cookie
│   └── GET    /me                                      # Check session cookie validity
├── /pipeline
│   ├── POST   /run                                     # Start a pipeline run
│   ├── GET    /runs                                    # List pipeline run summaries (paginated)
│   └── GET    /runs/{processing_run_id}/status          # Poll run status
├── /evidence
│   ├── GET    /groups/detail                            # Evidence group detail with distribution
│   ├── PATCH  /{canonical_evidence_id}                  # Patch evidence card (Phase 4)
│   ├── GET    /search                                   # Search evidence cards with pagination
│   ├── GET    /literature/search                        # Search literature profiles
│   ├── GET    /literature/{source_document_id}/detail    # Full literature profile detail
│   └── POST   /literature/refresh                       # Refresh all literature profiles (admin)
├── /delta-audit
│   └── GET    /                                         # List audit events with filters
├── /source-link
│   ├── GET    /{canonical_evidence_id}/bilingual         # Bilingual traceability span
│   └── GET    /{canonical_evidence_id}/{track}           # Single-track source span
├── /chat
│   ├── POST   /sessions                                 # Create chat session
│   ├── GET    /sessions/{processing_run_id}              # List sessions for a run
│   ├── GET    /sessions/{session_id}/messages            # List messages
│   ├── POST   /sessions/{session_id}/messages            # Append message (auto-reply)
│   └── GET    /sessions/{session_id}/stream              # SSE streaming reply
└── /documents
    ├── GET    /{source_document_id}/annotations          # List annotations for a document
    ├── POST   /{source_document_id}/annotations          # Create annotation
    ├── PATCH  /{source_document_id}/annotations/{id}     # Update annotation (color, note)
    └── DELETE /{source_document_id}/annotations/{id}     # Delete annotation
```

## Public API

### Auth Routes (`auth.py`)

| Endpoint | Method | Request | Response | Description |
|----------|--------|---------|----------|-------------|
| `/auth/login` | POST | `LoginRequest` (`password: str`) | `LoginResponse` | Validate admin password against `API_KEY`, set HMAC-signed `ce_session` HttpOnly cookie (8-hour TTL). Returns 401 on invalid credentials, 500 if auth not configured. |
| `/auth/logout` | POST | -- | `LogoutResponse` | Delete the session cookie. |
| `/auth/me` | GET | -- | `AuthMeResponse` | Return `authenticated: true/false` based on session cookie validity. |

### Pipeline Routes (`pipeline.py`)

| Endpoint | Method | Request | Response | Description |
|----------|--------|---------|----------|-------------|
| `/pipeline/run` | POST | `PipelineRunRequest` | `PipelineRunResponse` (202) | Start async pipeline run. Rate-limited to 10/min. Returns immediately with `processing_run_id`. Checks for duplicate in-progress runs (409). Checks L1/L2 processing cache for identical content hash (returns `status: "cached"` on hit). |
| `/pipeline/runs` | GET | Query: `limit`, `offset`, `status`, `search` | `PipelineRunListResponse` | List pipeline run summaries (newest first) with optional status filter and substring search. |
| `/pipeline/runs/{id}/status` | GET | -- | `PipelineStatusResponse` | Poll pipeline status with per-phase details. Checks memory cache first, then PostgreSQL. |

#### `PipelineRunRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source_type` | `"local" \| "online"` | required | Document source |
| `mode` | `"full" \| "phase"` | `"full"` | Run all phases or a single phase |
| `target_phase` | `int \| None` | `None` | Phase 1--3 (required when `mode="phase"`) |
| `processing_run_id` | `str \| None` | `None` | Existing run ID for phase mode re-run (required when `target_phase > 1`) |
| `filename` | `str \| None` | `None` | Original filename (local upload) |
| `content_base64` | `str \| None` | `None` | Base64-encoded file content (local upload) |
| `pre_parsed_markdown` | `str \| None` | `None` | Pre-parsed markdown to bypass MinerU parsing (local upload) |
| `query` | `str \| None` | `None` | Search query (online) |
| `identifiers` | `list[str] \| None` | `None` | DOI/PMID/PMCID (online) |
| `relevance_gate` | `bool` | `true` | Enable relevance gate for online acquisition |
| `literature_types` | `list[str] \| None` | `None` | Document type filter for typed classification path |
| `target` / `extraction_target` | `ExtractionTarget \| None` | `None` | Target gene-disease hypothesis for Phase 2/3 |

### Evidence Routes (`evidence.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/evidence/groups/detail` | GET | Return evidence group detail with distribution and traceability. Query params: `group_id`, `source_document_id` (at least one required). |
| `/evidence/{id}` | PATCH | Apply expert feedback patch to a canonical evidence card. Rate-limited to 30/min. Returns `PatchResult`. |
| `/evidence/search` | GET | Search evidence cards with field-level pivoting and pagination. Filters: `gene`, `variant`, `disease`, `pmid`, `doi`, `page`, `page_size`. |
| `/evidence/literature/search` | GET | Search literature profiles with per-article aggregation. Same filter params as evidence search. |
| `/evidence/literature/{source_document_id}/detail` | GET | Return full literature profile with all evidence groups. |
| `/evidence/literature/refresh` | POST | Refresh all literature profiles from canonical evidence. Admin endpoint, rate-limited to 5/min. |

### Chat Routes (`chat.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/sessions` | POST | Create a new chat session bound to a processing run. Rate-limited to 30/min. |
| `/chat/sessions/{run_id}` | GET | List all chat sessions for a processing run. |
| `/chat/sessions/{sid}/messages` | GET | List messages in a session. Query param: `limit` (default 100). |
| `/chat/sessions/{sid}/messages` | POST | Append message; optionally auto-generates AI reply when `auto_reply=true`. Rate-limited to 60/min. |
| `/chat/sessions/{sid}/stream` | GET | SSE streaming AI reply with 15s keepalive heartbeat. Rate-limited to 10/min. |

### Delta Audit Routes (`delta_audit.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/delta-audit` | GET | List review audit events. Filters: `canonical_evidence_id`, `source_document_id`, `reviewer_id`, `limit` (1--1000, default 100). |

### Source Link Routes (`source_link.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/source-link/{id}/bilingual` | GET | Retrieve bilingual (original + translated) traceability span |
| `/source-link/{id}/{track}` | GET | Retrieve source span for one track (`original` or `translated`). Returns null if no span exists. |

### Document Annotation Routes (`annotations.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/documents/{doc_id}/annotations` | GET | List annotations for a document. Optional query param: `track` (original/translated). |
| `/documents/{doc_id}/annotations` | POST | Create a new annotation. Fields: `track`, `paragraph_id`, `start_offset`, `end_offset`, `color`, `note`, `author`. Returns 201. |
| `/documents/{doc_id}/annotations/{annotation_id}` | PATCH | Update mutable fields (`color`, `note`) of an annotation. Returns 404 if annotation does not belong to the document. |
| `/documents/{doc_id}/annotations/{annotation_id}` | DELETE | Delete an annotation. Returns 204 on success, 404 if not found. |

## Internal Design

- Pipeline routes manage a global `_pipeline_runner` singleton set during app startup via `set_pipeline_runner()`.
- Phase 4 routes use `get_phase4_factory()` to create per-request service instances with fresh DB sessions.
- All routes are thin -- validation via Pydantic models, error handling via `HTTPException`, zero business logic.
- Duplicate run prevention: `POST /pipeline/run` checks `runner.is_running_for_source()` and returns 409 if a run is already in progress for the same source key.
- Processing cache: `POST /pipeline/run` computes a content hash and checks L1/L2 cache; returns cached result immediately if identical document was already processed.
- Upload path traversal prevention: filenames are sanitized via `PurePosixPath.name` to strip directory components.
- File size enforcement: base64 content is checked against `mineru.max_file_size_mb` before decoding.
- All routes are protected by `require_api_key` dependency (disabled when no API key is configured).
- Rate limits are enforced via the `@limiter.limit()` decorator using the shared slowapi singleton.

## Testing

```bash
cd backend
uv run pytest tests/api/ -v
```
