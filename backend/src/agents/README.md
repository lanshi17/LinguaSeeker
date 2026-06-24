# Agents (Orchestrator)

> Pipeline orchestrator layer for LinguaSeeker. Owns LangGraph topology, pipeline state, phase adapters, concurrency control, content-hash dedup, and state persistence. Contains zero business rules -- all domain logic lives in `core/` feature slices.

## Quick Start

```python
from src.agents.contracts import PipelineGraphState, PipelineMode, SourceType
from src.agents.runner import PipelineRunner

# Create initial state
state = PipelineGraphState(
    processing_run_id="uuid-here",
    source_document_id="uuid-here",
    mode=PipelineMode.FULL,
    source_type=SourceType.LOCAL,
)

# Start background execution (runner is assembled in wiring.py)
task = runner.start(state)
result = await task  # or poll with runner.get_last_state(run_id)
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  PipelineRunner                          │
│  asyncio.Task management, semaphore, crash recovery      │
│  processing cache check, content hash computation        │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              PipelineOrchestrator                         │
│  LangGraph state machine: 3 nodes + conditional edges    │
│                                                          │
│  phase_1 ──(success?)──► phase_2 ──(success?)──► phase_3 │
│     │ FAIL→END             │ FAIL→END             │      │
│     └──► END               └──► END               └─►END │
│                                                          │
│  After Phase 3: pipeline_status = COMPLETED              │
│  (Phase 4 operates independently via HTTP API)           │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
  ┌───────────┐ ┌───────────┐ ┌───────────┐
  │Phase1Adapt│ │Phase2Adapt│ │Phase3Adapt│  ← Thin adapters
  │acquire +  │ │translate +│ │standardize│    (error classification)
  │parse      │ │extract    │ │& align    │
  └───────────┘ └───────────┘ └───────────┘
        │            │            │
        ▼            ▼            ▼
   core/ Phase 1  core/ Phase 2  core/ Phase 3  ← Business logic
```

## Directory Map

| File | Purpose |
|------|---------|
| `contracts.py` | All typed contracts: `PipelineGraphState`, enums, error hierarchy, state transition guards, phase output models |
| `orchestrator.py` | `PipelineOrchestrator` -- LangGraph graph wiring, phase execution, routing decisions |
| `runner.py` | `PipelineRunner` -- background asyncio.Task management, semaphore, crash recovery, processing cache, run listing |
| `concurrency.py` | `PipelineSemaphore`, `RetryablePhaseExecutor` -- concurrency limit + retry with exponential backoff |
| `state_persistence.py` | `SessionBoundStatePersistence`, `DirectStatePersistence` -- PostgreSQL state save/load, orphan recovery, run listing |
| `processing_cache.py` | `DocumentProcessingCacheService` -- two-tier (L1 Redis + L2 PostgreSQL) cache for identical-document dedup |
| `content_hash.py` | `compute_content_hash` and helpers -- SHA-256 hashing of file bytes, markdown, or online keys for dedup |
| `phase_1_adapter.py` | `Phase1Adapter` -- wraps acquisition + parsing services |
| `phase_2_adapter.py` | `Phase2Adapter` -- wraps translation + evidence extraction services |
| `phase_3_adapter.py` | `Phase3Adapter` -- wraps entity standardization service |
| `phase_4_factory.py` | `Phase4ServiceFactory` -- creates Phase 4 services (feedback, chat, source_linker, delta_audit) with per-request sessions. Long-lived dependencies (cfg, ChatLLMProvider) injected at construction. |

## Public API

### `PipelineOrchestrator`

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(phase_adapters, state_persistence, retry_executor)` | Wire adapters, persistence, and retry logic |
| `run` | `async (state: PipelineGraphState) -> PipelineGraphState` | Execute pipeline (full or single-phase mode) |
| `on_state_change` | `Callable[[str, PipelineGraphState], None] \| None` | Optional callback invoked after each state persistence so the runner can keep its in-memory cache in sync |

### `PipelineRunner`

| Method | Signature | Description |
|--------|-----------|-------------|
| `start` | `async (initial_state: PipelineGraphState) -> asyncio.Task` | Durable claim + background task. Heartbeat loop refreshes ownership while active. IntegrityError propagates as race-proof duplicate-source guard. |
| `get_last_state` | `async (run_id: str) -> PipelineGraphState \| None` | Read state (memory cache -> PostgreSQL fallback, no mutation). Only caches terminal DB states to avoid stale active rows. |
| `get_last_state_cached` | `(run_id: str) -> PipelineGraphState \| None` | Fast path: memory cache only |
| `is_running` | `(run_id: str) -> bool` | Check if a run is currently active |
| `is_running_for_source` | `async (source_key: str) -> bool` | Dedup check by filename/query; checks memory cache then persistence for cross-worker dedup |
| `list_runs` | `async (limit, offset, status, search) -> tuple[list[PipelineRunSummaryRow], int]` | List pipeline run summaries (newest first) with optional status/search filters |
| `check_processing_cache` | `async (content_hash: str) -> PipelineGraphState \| None` | Check L1/L2 processing cache for a previously completed result with the same content hash |
| `compute_initial_content_hash` | `async (state: PipelineGraphState) -> str \| None` | Compute the SHA-256 content hash for an initial pipeline state (file bytes, markdown, or online key) |
| `recover_orphaned_runs` | `async (heartbeat_timeout_seconds=300) -> int` | Mark heartbeat-stale non-terminal runs as FAILED |
| `shutdown` | `async (timeout=60.0) -> None` | Graceful shutdown: wait for active tasks, cancel stragglers |
| `remember_state` | `(run_id: str, state: PipelineGraphState) -> None` | Store state in LRU cache (max 100 entries) |

Constructor: `__init__(orchestrator, semaphore, state_persistence, processing_cache=None, worker_id=None, heartbeat_interval_seconds=15.0)`

### `DocumentProcessingCacheService`

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_cached_result` | `async (content_hash: str) -> CacheLookupResult \| None` | L1 Redis lookup, then L2 PostgreSQL with L1 backfill |
| `cache_result` | `async (content_hash: str, state: PipelineGraphState) -> None` | Upsert into L2 PostgreSQL, then set L1 Redis with TTL |

L1 key format: `docproc:{content_hash}`. TTL: 1 hour.

### `compute_content_hash`

| Function | Signature | Description |
|----------|-----------|-------------|
| `compute_content_hash` | `async (state: PipelineGraphState) -> str \| None` | Dispatches to file-hash, text-hash, or online-key-hash depending on source type. Returns `None` for phase re-run mode. |
| `compute_hash_from_file` | `async (file_path, scope_key=None) -> str` | Stream file in 1 MB chunks, SHA-256 |
| `compute_hash_from_text` | `(text, scope_key=None) -> str` | SHA-256 of encoded text |
| `compute_hash_from_bytes` | `(content, scope_key=None) -> str` | SHA-256 of raw bytes |

All hash functions optionally append an extraction target scope key so the same document processed for different gene-disease hypotheses does not collide.

### `PipelineGraphState`

```python
class PipelineGraphState(BaseModel):
    # Run identity (UUID strings)
    processing_run_id: str              # UUID string
    source_document_id: str             # UUID string
    # Execution mode
    mode: PipelineMode                  # FULL or PHASE
    source_type: SourceType             # LOCAL or ONLINE
    target_phase: int | None            # 1-3 for single-phase mode
    # Dedup
    source_key: str | None              # filename (local) or query (online)
    content_hash: str | None            # SHA-256 for L1/L2 processing cache
    # Overall pipeline status
    pipeline_status: PipelineStatus     # PENDING -> RUNNING -> COMPLETED | FAILED
    # Per-phase status (structured with timing and errors)
    phase_1_status: PhaseStatusDetail
    phase_2_status: PhaseStatusDetail
    phase_3_status: PhaseStatusDetail
    # Phase outputs (typed models)
    phase_1_output: Phase1Output | None # pdf_path, md_path, metadata_path, output_dir, images_dir
    phase_2_output: Phase2Output | None # output_dir, translation paths, source_language, extraction_result_path, original_text, translated_text, original_blocks, translated_blocks
    phase_3_output: Phase3Output | None # match/standardized/ambiguous/unmapped counts
    # Error tracking
    error_message: str | None
    error_phase: int | None
    # Execution metadata
    created_at: str
    started_at: str | None
    completed_at: str | None
    # Content-based routing
    skip_phase_3_reason: SkipPhase3Reason | None
    # Upload content
    upload_file_path: str | None
    pre_parsed_markdown: str | None     # Bypasses Phase 1 MinerU parsing
    # Online acquisition fields
    query: str | None
    identifiers: list[str] | None
    action: str | None
    relevance_gate: bool                # Default True
    literature_types: list[str] | None
    # Target gene-disease hypothesis for Phase 2/3
    extraction_target: ExtractionTarget | None
```

### Error Hierarchy

```
PhaseError (base)
├── RetryablePhaseError    # Transient: timeouts, rate limits -> retried by RetryablePhaseExecutor
└── PermanentPhaseError    # Permanent: invalid input, parser exhaustion -> no retry

InvalidStateTransitionError  # Programming/data-corruption guard: invalid status transition
```

State transition guards validate all pipeline and phase status transitions. Valid transitions are defined in `_VALID_PIPELINE_TRANSITIONS` and `_VALID_PHASE_TRANSITIONS`. Terminal states can return to PENDING for phase reruns.

### `RetryablePhaseExecutor`

| Method | Signature | Description |
|--------|-----------|-------------|
| `execute_with_retry` | `async (operation, state, phase_name) -> Any` | Execute with exponential backoff on `RetryablePhaseError` |

Default: 2 retries, 30s base backoff (30s -> 60s).

## Internal Design

### Adapter Error Classification

Phase adapters translate domain exceptions into classified orchestrator errors:
- `ConnectionError`, `TimeoutError`, `openai.APITimeoutError`, `openai.RateLimitError`, `httpx.TimeoutException`, `MinerUTimeoutError`, `CatalogExtractionError` -> `RetryablePhaseError`
- `FileNotFoundError`, `PermissionError`, `IsADirectoryError` -> `PermanentPhaseError` (OSError subclasses but non-transient)
- `ParserExhaustedError`, config errors, invalid input -> `PermanentPhaseError`
- Unknown exceptions -> `PermanentPhaseError` (safe default)

The retryable error tuple is built dynamically by `build_retryable_errors()` to handle optional dependencies (httpx, openai, MinerU).

### State Persistence

State is saved to PostgreSQL (`pipeline_run_states` table) after each phase completes (success or failure). `SessionBoundStatePersistence` creates a fresh session per operation to avoid stale-session bugs in long-lived contexts.

Each save performs a state transition guard check: loads the existing state from DB and validates that the new pipeline/phase status transitions are legal before committing. This defense-in-depth prevents corrupted state from reaching the database.

Worker ownership is tracked via `owner_worker_id` and `heartbeat_at` columns. The runner's heartbeat loop (default 15s interval) refreshes ownership while a pipeline is active. Orphan recovery marks runs with stale heartbeats (>300s) as FAILED during app startup. A PostgreSQL advisory lock prevents multi-worker races during recovery.

Additional persistence methods:
- `heartbeat(run_id, worker_id)` -- refresh ownership timestamp for active runs
- `has_active_source_key(source_key)` -- cross-worker dedup check
- `list_runs(limit, offset, status, search)` -- paginated run summaries (newest first)

### Processing Cache (L1/L2)

When a pipeline run completes, the final state is cached by content hash. On subsequent submissions with the same content hash, the cached result is returned immediately without re-running the pipeline.

Read path: L1 Redis -> L2 PostgreSQL (with L1 backfill) -> miss.
Write path: L2 PostgreSQL upsert -> L1 Redis set (1-hour TTL).

The content hash incorporates file bytes (local uploads), markdown text (pre-parsed), or a deterministic key from identifiers/query (online acquisition). An extraction target scope key is appended so the same document processed for different gene-disease hypotheses does not collide.

### Single-Phase Mode

When `mode=PHASE`, the orchestrator validates that all upstream phases have completed before executing the target phase. E.g., Phase 3 requires Phase 1 and Phase 2 to be `COMPLETED`.

### Pre-parsed Markdown Fast Path

When `state.pre_parsed_markdown` is set, Phase 1 skips MinerU parsing entirely and constructs Phase1Output directly from the provided markdown text. This is used when the online acquisition pipeline already parsed the PDF via MinerU batch processing.

### Phase 2 Dual-Track Extraction

Phase 2 runs dual-track evidence extraction (original + translated documents). If both tracks return NOT_RELEVANT, `skip_phase_3_reason` is set to `SkipPhase3Reason.NOT_RELEVANT` and Phase 3 is skipped. The extraction result is persisted to disk for Phase 3 consumption.

### Phase 3 Skip Conditions

Phase 3 is skipped when:
- `skip_phase_3_reason` is set by Phase 2 (NOT_RELEVANT)
- Standardization produces zero candidates (NO_CANDIDATES -- set after Phase 3 runs)

### State Transition Tables

Pipeline status transitions:

| From | Allowed To |
|------|------------|
| PENDING | RUNNING, FAILED |
| RUNNING | COMPLETED, FAILED |
| FAILED | PENDING (rerun) |
| COMPLETED | PENDING (rerun) |

Phase status transitions:

| From | Allowed To |
|------|------------|
| PENDING | RUNNING, SKIPPED, FAILED |
| RUNNING | COMPLETED, FAILED, SKIPPED |
| COMPLETED | PENDING (rerun) |
| SKIPPED | PENDING (rerun) |
| FAILED | PENDING (rerun) |

Identity transitions (same status) are always allowed for metadata-only saves.

### Duplicate Run Prevention

`PipelineRunner.is_running_for_source()` checks if any active task has the same `source_key` (filename or query). The API route returns 409 if a duplicate is detected.

## Usage Patterns

### Full pipeline run

```python
state = PipelineGraphState(
    processing_run_id=str(uuid.uuid4()),
    source_document_id=str(uuid.uuid4()),
    mode=PipelineMode.FULL,
    source_type=SourceType.LOCAL,
    upload_file_path="/tmp/uploaded.pdf",
)
task = runner.start(state)
result = await task
assert result.pipeline_status == PipelineStatus.COMPLETED
```

### Single-phase run

```python
state = PipelineGraphState(
    processing_run_id=str(uuid.uuid4()),
    source_document_id=str(uuid.uuid4()),
    mode=PipelineMode.PHASE,
    target_phase=2,
    source_type=SourceType.ONLINE,
    phase_1_status=PhaseStatusDetail(status=PhaseStatus.COMPLETED),
)
result = await runner.start(state)
```

### Processing cache check

```python
content_hash = await runner.compute_initial_content_hash(initial_state)
if content_hash:
    cached = await runner.check_processing_cache(content_hash)
    if cached is not None and cached.pipeline_status == PipelineStatus.COMPLETED:
        # Short-circuit: return cached result without re-running pipeline
        return cached
```

## Testing

```bash
cd backend
uv run pytest tests/agents/ -v
```

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `langgraph` | `StateGraph`, `END` -- pipeline state machine |
| `pydantic` | `PipelineGraphState` and all typed contracts |
| `sqlalchemy[asyncio]` | State persistence to `pipeline_run_states` via upsert + state transition guards |
| `redis` | L1 processing cache (volatile, fast) |
| `loguru` | Structured logging per phase |
| `aiofiles` | Async file I/O in phase adapters |
