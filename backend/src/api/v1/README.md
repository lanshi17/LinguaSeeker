# API v1 Routes

> REST endpoint definitions for CrossEvidence's v1 API. All routes are mounted under `/api/v1` and delegate to the orchestrator or Phase 4 services via injected dependencies.

## Route Map

```
/api/v1
├── /pipeline
│   ├── POST /run                              # Start a pipeline run
│   └── GET  /runs/{processing_run_id}/status  # Poll run status
├── /evidence
│   └── PATCH /{canonical_evidence_id}         # Patch evidence card (Phase 4)
├── /delta-audit
│   └── GET /                                  # List audit events (Phase 4)
├── /source-link
│   ├── GET /{canonical_evidence_id}/bilingual # Bilingual traceability span
│   └── GET /{canonical_evidence_id}/{track}   # Single-track source span
└── /chat
    ├── POST   /sessions                       # Create chat session
    ├── GET    /sessions/{run_id}              # List sessions for a run
    ├── GET    /sessions/{sid}/messages        # List messages
    ├── POST   /sessions/{sid}/messages        # Append message (auto-reply)
    └── GET    /sessions/{sid}/stream          # SSE streaming reply
```

## Public API

### Pipeline Routes (`pipeline.py`)

| Endpoint | Method | Request | Response | Description |
|----------|--------|---------|----------|-------------|
| `/pipeline/run` | POST | `PipelineRunRequest` | `PipelineRunResponse` (202) | Start async pipeline run. Returns immediately with `processing_run_id`. |
| `/pipeline/runs/{id}/status` | GET | — | `PipelineStatusResponse` | Poll pipeline status with per-phase details. Checks memory cache first, then PostgreSQL. |

#### `PipelineRunRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source_type` | `"local" \| "online"` | required | Document source |
| `mode` | `"full" \| "phase"` | `"full"` | Run all phases or a single phase |
| `target_phase` | `int \| None` | `None` | Phase 1–3 (required when `mode="phase"`) |
| `filename` | `str \| None` | `None` | Original filename (local upload) |
| `content_base64` | `str \| None` | `None` | Base64-encoded file content (local upload) |
| `query` | `str \| None` | `None` | Search query (online) |
| `identifiers` | `list[str] \| None` | `None` | DOI/PMID/PMCID (online) |

### Evidence Routes (`evidence.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/evidence/{id}` | PATCH | Apply expert feedback patch to a canonical evidence card. Returns `PatchResult`. |

### Chat Routes (`chat.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/sessions` | POST | Create a new chat session bound to a processing run |
| `/chat/sessions/{run_id}` | GET | List all chat sessions for a processing run |
| `/chat/sessions/{sid}/messages` | GET | List messages in a session |
| `/chat/sessions/{sid}/messages` | POST | Append message; auto-generates AI reply for user messages |
| `/chat/sessions/{sid}/stream` | GET | SSE streaming AI reply with 15s keepalive heartbeat |

### Delta Audit Routes (`delta_audit.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/delta-audit/` | GET | List review audit events. Filters: `canonical_evidence_id`, `reviewer_id`, `limit`. |

### Source Link Routes (`source_link.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/source-link/{id}/bilingual` | GET | Retrieve bilingual (original + translated) traceability span |
| `/source-link/{id}/{track}` | GET | Retrieve source span for one track (`original` or `translated`) |

## Internal Design

- Pipeline routes manage a global `_pipeline_runner` singleton set during app startup via `set_pipeline_runner()`.
- Phase 4 routes use `get_phase4_factory()` to create per-request service instances with fresh DB sessions.
- All routes are thin — validation via Pydantic models, error handling via `HTTPException`, zero business logic.
- Duplicate run prevention: `POST /pipeline/run` checks `runner.is_running_for_source()` and returns 409 if a run is already in progress for the same source key.

## Testing

```bash
cd backend
uv run pytest tests/api/ -v
```
