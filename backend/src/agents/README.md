# Agents (Orchestrator)

> Pipeline orchestrator layer for CrossEvidence. Owns LangGraph topology, pipeline state, phase adapters, concurrency control, and state persistence. Contains zero business rules — all domain logic lives in `core/` feature slices.

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
│  After Phase 3: pipeline_status = AWAITING_REVIEW        │
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
| `contracts.py` | All typed contracts: `PipelineGraphState`, enums, error hierarchy, phase output models |
| `orchestrator.py` | `PipelineOrchestrator` — LangGraph graph wiring, phase execution, routing decisions |
| `runner.py` | `PipelineRunner` — background asyncio.Task management, semaphore, crash recovery |
| `concurrency.py` | `PipelineSemaphore`, `RetryablePhaseExecutor` — concurrency limit + retry with exponential backoff |
| `state_persistence.py` | `SessionBoundStatePersistence`, `DirectStatePersistence` — PostgreSQL state save/load |
| `phase_1_adapter.py` | `Phase1Adapter` — wraps acquisition + parsing services |
| `phase_2_adapter.py` | `Phase2Adapter` — wraps translation + evidence extraction services |
| `phase_3_adapter.py` | `Phase3Adapter` — wraps entity standardization service |
| `phase_4_factory.py` | `Phase4ServiceFactory` — creates Phase 4 services with per-request sessions |

## Public API

### `PipelineOrchestrator`

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(phase_adapters, state_persistence, retry_executor)` | Wire adapters, persistence, and retry logic |
| `run` | `async (state: PipelineGraphState) -> PipelineGraphState` | Execute pipeline (full or single-phase mode) |

### `PipelineRunner`

| Method | Signature | Description |
|--------|-----------|-------------|
| `start` | `(initial_state: PipelineGraphState) -> asyncio.Task` | Start background pipeline execution |
| `get_last_state` | `async (run_id: str) -> PipelineGraphState \| None` | Read state (memory cache → PostgreSQL fallback, no mutation) |
| `get_last_state_cached` | `(run_id: str) -> PipelineGraphState \| None` | Fast path: memory cache only |
| `is_running` | `(run_id: str) -> bool` | Check if a run is currently active |
| `is_running_for_source` | `(source_key: str) -> bool` | Dedup check by filename/query |

### `PipelineGraphState`

```python
class PipelineGraphState(BaseModel):
    processing_run_id: str              # UUID string
    source_document_id: str             # UUID string
    mode: PipelineMode                  # FULL or PHASE
    source_type: SourceType             # LOCAL or ONLINE
    target_phase: int | None            # 1-3 for single-phase mode
    pipeline_status: PipelineStatus     # PENDING → RUNNING → AWAITING_REVIEW | FAILED
    phase_1_status: PhaseStatusDetail   # Per-phase timing + errors
    phase_2_status: PhaseStatusDetail
    phase_3_status: PhaseStatusDetail
    phase_1_output: Phase1Output | None # pdf_path, md_path, metadata_path
    phase_2_output: Phase2Output | None # output_dir, translation paths, extraction path
    phase_3_output: Phase3Output | None # match/standardized/ambiguous/unmapped counts
    skip_phase_3_reason: SkipPhase3Reason | None
```

### Error Hierarchy

```
PhaseError (base)
├── RetryablePhaseError    # Transient: timeouts, rate limits → retried by RetryablePhaseExecutor
└── PermanentPhaseError    # Permanent: invalid input, parser exhaustion → no retry
```

### `RetryablePhaseExecutor`

| Method | Signature | Description |
|--------|-----------|-------------|
| `execute_with_retry` | `async (operation, state, phase_name) -> Any` | Execute with exponential backoff on `RetryablePhaseError` |

Default: 2 retries, 30s base backoff (30s → 60s).

## Internal Design

### Adapter Error Classification

Phase adapters translate domain exceptions into classified orchestrator errors:
- `ConnectionError`, `TimeoutError`, `openai.APITimeoutError`, `httpx.TimeoutException`, `MinerUTimeoutError` → `RetryablePhaseError`
- `ParserExhaustedError`, config errors, invalid input → `PermanentPhaseError`
- Unknown exceptions → `PermanentPhaseError` (safe default)

### State Persistence

State is saved to PostgreSQL (`pipeline_run_states` table) after each phase completes (success or failure). `SessionBoundStatePersistence` creates a fresh session per operation to avoid stale-session bugs in long-lived contexts. `PipelineRunner.get_last_state()` checks in-memory cache first, then falls back to DB without changing the stored status. Orphan recovery runs once during app startup via `recover_orphaned_runs()`.

### Single-Phase Mode

When `mode=PHASE`, the orchestrator validates that all upstream phases have completed before executing the target phase. E.g., Phase 3 requires Phase 1 and Phase 2 to be `COMPLETED`.

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
assert result.pipeline_status == PipelineStatus.AWAITING_REVIEW
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

## Testing

```bash
cd backend
uv run pytest tests/agents/ -v
```

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `langgraph` | `StateGraph`, `END` — pipeline state machine |
| `pydantic` | `PipelineGraphState` and all typed contracts |
| `sqlalchemy[asyncio]` | State persistence to `pipeline_run_states` |
| `loguru` | Structured logging per phase |
