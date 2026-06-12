# CrossEvidence Pipeline Correctness Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stop silent pipeline state corruption, evidence payload data loss, and auth/status contract drift in the production four-stage workflow.

**Architecture:** Keep the existing orchestrated vertical slice shape: `backend/src/agents/` owns workflow topology and run lifecycle; feature slices keep business logic; `backend/src/dao/postgresql/` owns durable cross-worker state. Use PostgreSQL for worker ownership, heartbeat, and active-source dedup because the current runner state is process-local while production runs multiple backend workers. Keep Phase 4 review as an explicit HTTP workflow and add a finalize action that moves successful runs from `awaiting_review` to `completed`.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2 async ORM, Alembic, LangGraph, pytest/pytest-asyncio, Next.js 15, TypeScript, Axios, npm via nvm.

**Status:** completed
**Created:** 2026-06-11
**Completed:** 2026-06-12
**PR:** merged to dev

---

## Execution Notes

Use @executing-plans for task-by-task execution. Use @test-driven-development for every behavior change, @systematic-debugging for any unexpected failure, @verification-before-completion before claiming completion, @git-auto-commit for each commit/push, and @doc-organize after the docs updates.

Before implementation, re-run the `.old_version/` search in Task 1. The quick planning scan found old supervisor `finalize` tests and node patterns, but no reusable multi-worker heartbeat or active-payload contract implementation.

Line numbers in the `Files:` lists are orientation anchors from the planning review. Before editing each task, re-check current locations with `rg` and `nl -ba` because nearby files are active.

This plan intentionally fixes the verified P0/P1 correctness issues first:

- Multi-worker false failure on status polling and startup recovery.
- Destructive `active_payload` overwrite on evidence patch.
- Missing pipeline `completed` terminal transition.
- Broken single-phase mode.
- Phase 3 ambiguous/unmapped skip semantics.
- URL parser fallback typo.
- Production auth fail-open and frontend status/header drift.

Out of scope for this plan:

- Moving phase artifacts from local disk to object storage.
- LangGraph checkpointer-based resume.
- Global cross-worker LLM quota.
- Phase 3 batching/performance work.
- Full OpenAPI TypeScript codegen.
- Model-server changes, unless tests reveal a direct contract dependency.

## Success Criteria

1. `GET /api/v1/pipeline/runs/{id}/status` never mutates a run from another worker.
2. Startup recovery only fails stale active runs whose heartbeat is older than the lease timeout.
3. Evidence patching preserves `active_payload.group_id`, `value`, `source`, `track`, and other unknown keys.
4. Expert review can explicitly finalize a run as `completed`.
5. Phase mode runs only the requested phase and requires a previous run for target phases 2 and 3.
6. Phase 3 does not set `NO_CANDIDATES` when ambiguous or unmapped entities exist.
7. Production settings cannot start with an empty `API_KEY`.
8. Backend and frontend status/auth contracts match the current API.

---

### Task 1: Baseline And Old-Version Review

**Files:**
- Read: `backend/.old_version/src/agents/supervisor.py`
- Read: `backend/.old_version/tests/test_supervisor.py`
- Read: `backend/.old_version/tests/test_stream_supervisor.py`
- Read: `backend/src/agents/orchestrator.py:181-279`
- Read: `backend/src/agents/runner.py:46-208`
- Read: `backend/src/agents/state_persistence.py:95-162`
- Read: `backend/src/core/visualize_evidence_with_expert_in_loop/feedback_service.py:41-104`
- Read: `backend/src/core/standardize_entities_and_align_knowledge/repositories.py:938-987`

**Step 1: Search old-version recovery/finalize code**

Run:

```bash
cd backend
rg -n "recover_orphaned|heartbeat|finalize|human_review|active_payload|PipelineRunState" .old_version src tests
```

Expected: Results include old supervisor finalization patterns but no ready-made heartbeat lease implementation.

**Step 2: Capture current focused failures**

Run:

```bash
cd backend
uv run pytest tests/agents/test_runner.py tests/agents/test_orchestrator.py tests/core/visualize_evidence_with_expert_in_loop/test_feedback_service.py tests/agents/test_phase_3_adapter.py tests/core/ingest_and_digitize_data/parse_document/test_orchestrator.py -q
```

Expected: Current baseline should pass or expose existing known failures. If it fails for unrelated untracked work, stop and record the exact failing tests before editing.

**Step 3: Commit**

No commit for read-only baseline work.

---

### Task 2: Add Durable Pipeline Run Lease Columns

**Files:**
- Modify: `backend/src/dao/postgresql/models.py:623-664`
- Create: `database/migrations/versions/2026-06-11_add_pipeline_run_leases.py`
- Modify: `backend/tests/dao/postgresql/test_models.py:297-315`
- Modify: `backend/tests/dao/postgresql/test_alembic_migration.py:191-235`

**Step 1: Write failing model and migration tests**

Add tests that assert `PipelineRunState` exposes durable ownership fields:

```python
def test_pipeline_run_state_has_lease_columns() -> None:
    table = PipelineRunState.__table__
    column_names = {column.name for column in table.columns}

    assert "owner_worker_id" in column_names
    assert "heartbeat_at" in column_names
    assert "source_key" in column_names


def test_pipeline_run_state_has_active_source_index() -> None:
    table = PipelineRunState.__table__
    index_names = {idx.name for idx in table.indexes}

    assert "ix_pipeline_run_states_owner_heartbeat" in index_names
    assert "ux_pipeline_run_states_active_source_key" in index_names
```

In `test_alembic_migration.py`, update the head expectation from `add_created_at_search_idx` to `pipeline_run_leases_20260611` and add a chain test that asserts:

```python
lease_revision = script.get_revision("pipeline_run_leases_20260611")
assert lease_revision is not None
assert lease_revision.down_revision == "add_created_at_search_idx"
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/dao/postgresql/test_models.py::test_pipeline_run_state_has_lease_columns tests/dao/postgresql/test_models.py::test_pipeline_run_state_has_active_source_index tests/dao/postgresql/test_alembic_migration.py::test_head_revision_points_to_pipeline_status_extraction -q
```

Expected: FAIL because the ORM columns and new migration do not exist yet, and the head revision still points at `add_created_at_search_idx`.

**Step 3: Implement ORM fields and migration**

Add these ORM columns and indexes to `PipelineRunState`:

```python
source_key: Mapped[str | None] = mapped_column(Text, nullable=True)
owner_worker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Add indexes:

```python
Index("ix_pipeline_run_states_owner_heartbeat", "owner_worker_id", "heartbeat_at")
Index(
    "ux_pipeline_run_states_active_source_key",
    "source_key",
    unique=True,
    postgresql_where=text("source_key IS NOT NULL AND pipeline_status IN ('pending', 'running')"),
)
```

Create `database/migrations/versions/2026-06-11_add_pipeline_run_leases.py`:

```python
"""Add pipeline run worker leases.

Revision ID: pipeline_run_leases_20260611
Revises: add_created_at_search_idx
Create Date: 2026-06-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "pipeline_run_leases_20260611"
down_revision = "add_created_at_search_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pipeline_run_states", sa.Column("source_key", sa.Text(), nullable=True))
    op.add_column("pipeline_run_states", sa.Column("owner_worker_id", sa.String(length=128), nullable=True))
    op.add_column("pipeline_run_states", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_pipeline_run_states_owner_heartbeat",
        "pipeline_run_states",
        ["owner_worker_id", "heartbeat_at"],
        unique=False,
    )
    op.create_index(
        "ux_pipeline_run_states_active_source_key",
        "pipeline_run_states",
        ["source_key"],
        unique=True,
        postgresql_where=sa.text("source_key IS NOT NULL AND pipeline_status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("ux_pipeline_run_states_active_source_key", table_name="pipeline_run_states")
    op.drop_index("ix_pipeline_run_states_owner_heartbeat", table_name="pipeline_run_states")
    op.drop_column("pipeline_run_states", "heartbeat_at")
    op.drop_column("pipeline_run_states", "owner_worker_id")
    op.drop_column("pipeline_run_states", "source_key")
```

**Step 4: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/dao/postgresql/test_models.py tests/dao/postgresql/test_alembic_migration.py -q
```

Expected: PASS for model and migration structure tests.

**Step 5: Commit**

```bash
git add backend/src/dao/postgresql/models.py database/migrations/versions/2026-06-11_add_pipeline_run_leases.py backend/tests/dao/postgresql/test_models.py backend/tests/dao/postgresql/test_alembic_migration.py
git commit -m "fix: add durable pipeline run leases"
```

---

### Task 3: Make Status Polling Read-Only And Heartbeat-Aware

**Files:**
- Modify: `backend/src/agents/state_persistence.py:85-162`
- Modify: `backend/src/agents/runner.py:16-208`
- Modify: `backend/src/api/v1/pipeline.py:198-206`
- Modify: `backend/tests/agents/test_runner.py:113-431`
- Modify: `backend/tests/agents/test_state_persistence_layer.py`
- Modify: `backend/tests/api/test_pipeline_api.py:251-272`

**Step 1: Write failing runner tests**

In `test_runner.py`, replace the existing orphan-on-poll expectation with read-only behavior:

```python
@pytest.mark.asyncio
async def test_get_last_state_does_not_fail_active_db_run_from_another_worker(
    sample_state, mock_orchestrator, mock_semaphore, mock_persistence
):
    db_state = sample_state.model_copy(deep=True)
    db_state.pipeline_status = PipelineStatus.RUNNING
    mock_persistence.load.return_value = db_state

    runner = PipelineRunner(
        orchestrator=mock_orchestrator,
        semaphore=mock_semaphore,
        state_persistence=mock_persistence,
        worker_id="worker-b",
        heartbeat_interval_seconds=0.01,
    )

    result = await runner.get_last_state("run-123")

    assert result is db_state
    assert result.pipeline_status == PipelineStatus.RUNNING
    mock_persistence.save.assert_not_awaited()
```

Add a test that cancellation/error state is copied from the latest cached state, not `initial_state`:

```python
@pytest.mark.asyncio
async def test_runner_error_state_preserves_latest_phase_outputs(
    sample_state, mock_semaphore, mock_persistence
):
    from src.agents.contracts import Phase1Output, PhaseStatus, PhaseStatusDetail

    latest = sample_state.model_copy(deep=True)
    latest.phase_1_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)
    latest.phase_1_output = Phase1Output(
        pdf_path="/tmp/a.pdf",
        md_path="/tmp/a.md",
        metadata_path="/tmp/a.json",
        output_dir="/tmp",
    )

    orch = MagicMock()
    orch.run = AsyncMock(side_effect=RuntimeError("boom"))

    runner = PipelineRunner(
        orchestrator=orch,
        semaphore=mock_semaphore,
        state_persistence=mock_persistence,
        worker_id="worker-a",
        heartbeat_interval_seconds=0.01,
    )
    runner.remember_state(sample_state.processing_run_id, latest)

    task = await runner.start(sample_state)
    await task

    final_state = runner.get_last_state_cached(sample_state.processing_run_id)
    assert final_state is not None
    assert final_state.phase_1_output == latest.phase_1_output
    assert final_state.phase_1_status.status == PhaseStatus.COMPLETED
    assert final_state.pipeline_status == PipelineStatus.FAILED
```

Add a test for cross-worker source dedup through persistence:

```python
@pytest.mark.asyncio
async def test_is_running_for_source_checks_persistence_when_cache_misses(
    sample_state, mock_orchestrator, mock_semaphore, mock_persistence
):
    mock_persistence.has_active_source_key = AsyncMock(return_value=True)
    runner = PipelineRunner(mock_orchestrator, mock_semaphore, mock_persistence)

    assert await runner.is_running_for_source("pmid:123") is True
    mock_persistence.has_active_source_key.assert_awaited_once_with("pmid:123")
```

Add an API race test for the unique `source_key` constraint:

```python
@pytest.mark.asyncio
async def test_post_pipeline_run_duplicate_source_key_race_returns_409(async_client):
    from sqlalchemy.exc import IntegrityError

    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        runner = MagicMock()
        runner.is_running_for_source = AsyncMock(return_value=False)
        runner.start = AsyncMock(
            side_effect=IntegrityError("insert", {}, Exception("duplicate source_key"))
        )
        mock_get_runner.return_value = runner

        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "local",
                "mode": "full",
                "filename": "same.pdf",
                "content_base64": "JVBERi0xLjQK",
            },
        )

    assert response.status_code == 409
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/agents/test_runner.py::test_get_last_state_does_not_fail_active_db_run_from_another_worker tests/agents/test_runner.py::test_runner_error_state_preserves_latest_phase_outputs tests/agents/test_runner.py::test_is_running_for_source_checks_persistence_when_cache_misses tests/api/test_pipeline_api.py::test_post_pipeline_run_duplicate_source_key_race_returns_409 -q
```

Expected: FAIL because `get_last_state()` still writes failure states, `is_running_for_source()` is synchronous/in-memory only, error state is copied from `initial_state`, and the API cannot yet map a source-key insert race to 409.

**Step 3: Implement persistence APIs**

In `SessionBoundStatePersistence`, change `save()` to accept optional ownership metadata:

```python
async def save(
    self,
    state: PipelineGraphState,
    *,
    owner_worker_id: str | None = None,
    heartbeat_at: datetime | None = None,
) -> None:
    ...
```

Persist `source_key=state.source_key`, `owner_worker_id`, and `heartbeat_at` on insert/update when provided. Add:

```python
async def heartbeat(self, processing_run_id: str, owner_worker_id: str) -> bool:
    """Refresh heartbeat for an active run owned by this worker."""


async def has_active_source_key(self, source_key: str) -> bool:
    """Return True when any pending/running run owns this source key."""
```

Keep `DirectStatePersistence` signature compatible by accepting the same keyword arguments and storing only `state_json`/`pipeline_status`.

**Step 4: Implement runner ownership and read-only status**

In `PipelineRunner.__init__`, add:

```python
worker_id: str | None = None,
heartbeat_interval_seconds: float = 15.0,
```

Default `worker_id` to `f"{socket.gethostname()}:{os.getpid()}:{id(self)}"`.

Change `PipelineRunner.start()` to `async def start(...) -> asyncio.Task`. It must perform the initial durable claim before scheduling the background task:

- Save initial state with `owner_worker_id=self._worker_id` and `heartbeat_at=datetime.now(timezone.utc)` before `asyncio.create_task(...)`.
- Let `sqlalchemy.exc.IntegrityError` from that first save propagate to the API route; this is the race-proof duplicate-source guard behind the pre-check.
- Start a heartbeat task before acquiring the process-local semaphore.
- Cancel the heartbeat task in `finally`.
- On exception/cancel, use `last_state or initial_state` as the `model_copy()` base.

Change `get_last_state()` to:

```python
state = await self._persistence.load(processing_run_id)
if state is not None:
    self.remember_state(processing_run_id, state)
return state
```

Change `is_running_for_source()` to `async def` and fall back to `await self._persistence.has_active_source_key(source_key)`.

Update `backend/src/api/v1/pipeline.py` to await the async source check and `await runner.start(initial_state)`. Wrap `await runner.start(...)` in `try/except IntegrityError` and return HTTP 409 with the same duplicate-source message. This catches the partial unique index race when two workers submit the same source at the same time.

Design tradeoff: `get_last_state()` must stay read-only. Removing write-side orphan detection from GET means a failed heartbeat mechanism is not detected by polling. Stale active rows are handled by explicit heartbeat recovery; do not reintroduce GET-triggered writes because that is the multi-worker false-failure bug this task fixes.

**Step 5: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/agents/test_runner.py tests/agents/test_state_persistence_layer.py tests/api/test_pipeline_api.py::test_post_pipeline_run_duplicate_prevention -q
```

Expected: PASS. The duplicate-prevention API test should mock `runner.is_running_for_source = AsyncMock(return_value=True)`, and tests that start the runner directly must use `task = await runner.start(sample_state)`.

**Step 6: Commit**

```bash
git add backend/src/agents/state_persistence.py backend/src/agents/runner.py backend/src/api/v1/pipeline.py backend/tests/agents/test_runner.py backend/tests/agents/test_state_persistence_layer.py backend/tests/api/test_pipeline_api.py
git commit -m "fix: make pipeline status polling read-only"
```

---

### Task 4: Stale-Heartbeat Recovery And Startup Guard

**Files:**
- Modify: `backend/src/agents/state_persistence.py:136-162`
- Modify: `backend/src/agents/runner.py:155-157`
- Modify: `backend/app/main.py:90-104`
- Modify: `backend/tests/agents/test_state_persistence_layer.py`
- Modify: `backend/tests/integration/test_app_startup.py`

**Step 1: Write failing stale recovery tests**

Add tests for `recover_orphaned_runs()`:

```python
@pytest.mark.asyncio
async def test_recover_orphaned_runs_ignores_fresh_heartbeat(session_factory, running_state):
    persistence = SessionBoundStatePersistence(session_factory)
    await persistence.save(
        running_state,
        owner_worker_id="worker-a",
        heartbeat_at=datetime.now(timezone.utc),
    )

    recovered = await persistence.recover_orphaned_runs(heartbeat_timeout_seconds=120)

    assert recovered == 0
    loaded = await persistence.load(running_state.processing_run_id)
    assert loaded is not None
    assert loaded.pipeline_status == PipelineStatus.RUNNING
```

Add the stale case:

```python
@pytest.mark.asyncio
async def test_recover_orphaned_runs_fails_stale_heartbeat(session_factory, running_state):
    persistence = SessionBoundStatePersistence(session_factory)
    await persistence.save(
        running_state,
        owner_worker_id="worker-a",
        heartbeat_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )

    recovered = await persistence.recover_orphaned_runs(heartbeat_timeout_seconds=120)

    assert recovered == 1
    loaded = await persistence.load(running_state.processing_run_id)
    assert loaded is not None
    assert loaded.pipeline_status == PipelineStatus.FAILED
    assert loaded.error_message == "Pipeline heartbeat expired"
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/agents/test_state_persistence_layer.py -q -k "recover_orphaned_runs"
```

Expected: FAIL because recovery still fails every pending/running run without heartbeat filtering.

**Step 3: Implement stale heartbeat recovery**

Change `recover_orphaned_runs()` signature:

```python
async def recover_orphaned_runs(self, *, heartbeat_timeout_seconds: int = 300) -> int:
```

Keep the timeout paired with `PipelineRunner(heartbeat_interval_seconds=15.0)`: `300 / 15 = 20` missed heartbeats before a run is marked failed. This five-minute grace period is deliberate; it avoids failing long LLM calls during transient event-loop or database pressure.

Select only active runs where:

- `pipeline_status` is `pending` or `running`, and
- `heartbeat_at < now - timeout`, or
- `heartbeat_at IS NULL` and `updated_at < now - timeout` for legacy rows.

Use `Pipeline heartbeat expired` for the error message. Keep `_derive_error_phase(state)`.

**Step 4: Guard startup recovery**

In `backend/app/main.py`, avoid multi-worker recovery races by wrapping standalone table creation and recovery in a PostgreSQL advisory lock. Add a small helper near `lifespan()`:

```python
async def _try_startup_lock(engine: AsyncEngine) -> bool:
    result = await conn.execute(text("SELECT pg_try_advisory_lock(hashtext('cross_evidence_backend_startup'))"))
```

Use the same connection to release with `pg_advisory_unlock(...)` in `finally`. If lock acquisition returns false, skip `search_index_metadata.create_all()` and `runner.recover_orphaned_runs()` in that worker and log at info level.

**Step 5: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/agents/test_state_persistence_layer.py tests/integration/test_app_startup.py -q
```

Expected: PASS. Existing startup tests may need their engine/connection mocks updated for the advisory lock query.

**Step 6: Commit**

```bash
git add backend/src/agents/state_persistence.py backend/src/agents/runner.py backend/app/main.py backend/tests/agents/test_state_persistence_layer.py backend/tests/integration/test_app_startup.py
git commit -m "fix: recover only stale pipeline heartbeats"
```

---

### Task 5: Fix Single-Phase Mode And Review Finalization

**Files:**
- Modify: `backend/src/agents/orchestrator.py:161-279`
- Modify: `backend/src/api/v1/pipeline.py:37-314`
- Modify: `backend/src/agents/state_persistence.py:127-162`
- Modify: `backend/src/agents/runner.py`
- Modify: `backend/tests/agents/test_orchestrator.py:162-192`
- Modify: `backend/tests/api/test_pipeline_api.py`

**Step 1: Write failing orchestrator tests**

Add tests:

```python
@pytest.mark.asyncio
async def test_phase_mode_target_1_stops_after_phase_1(
    sample_state, mock_adapters, mock_persistence, mock_retry_executor
):
    state = sample_state.model_copy(update={"mode": PipelineMode.PHASE, "target_phase": 1})
    state_after_1 = state.model_copy(deep=True)
    state_after_1.phase_1_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)
    mock_adapters["phase_1"].run.return_value = state_after_1

    async def _pass_through(**kw):
        return await kw["operation"](kw["state"])

    mock_retry_executor.execute_with_retry.side_effect = _pass_through
    orchestrator = PipelineOrchestrator(mock_adapters, mock_persistence, mock_retry_executor)

    result = await orchestrator.run(state)

    assert result.phase_1_status.status == PhaseStatus.COMPLETED
    assert result.pipeline_status == PipelineStatus.AWAITING_REVIEW
    mock_adapters["phase_2"].run.assert_not_called()
    mock_adapters["phase_3"].run.assert_not_called()
```

Add target phase 2:

```python
@pytest.mark.asyncio
async def test_phase_mode_target_2_starts_at_phase_2_when_upstream_complete(...):
    state = PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.PHASE,
        source_type=SourceType.LOCAL,
        target_phase=2,
        phase_1_status=PhaseStatusDetail(status=PhaseStatus.COMPLETED),
        phase_1_output=Phase1Output(...),
    )
    ...
    mock_adapters["phase_1"].run.assert_not_called()
    mock_adapters["phase_2"].run.assert_called_once()
    mock_adapters["phase_3"].run.assert_not_called()
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/agents/test_orchestrator.py::test_phase_mode_target_1_stops_after_phase_1 tests/agents/test_orchestrator.py::test_phase_mode_target_2_starts_at_phase_2_when_upstream_complete -q
```

Expected: FAIL because the graph always starts at `phase_1` and does not stop at the target phase.

**Step 3: Implement conditional entry and stop-after-target routing**

First verify the LangGraph API in the active environment:

```bash
cd backend
uv run python - <<'PY'
from langgraph.graph import StateGraph
assert hasattr(StateGraph, "set_conditional_entry_point")
PY
```

Expected: PASS on the current `langgraph` 1.2.x installation. If it fails, use the compatible `START` fallback:

```python
from langgraph.graph import START

graph.add_conditional_edges(
    START,
    self._route_entry,
    {"phase_1": "phase_1", "phase_2": "phase_2", "phase_3": "phase_3"},
)
```

In `PipelineOrchestrator`, add:

```python
def _route_entry(self, state: PipelineGraphState) -> str:
    if state.mode == PipelineMode.PHASE and state.target_phase is not None:
        return f"phase_{state.target_phase}"
    return "phase_1"


def _is_target_phase_complete(self, state: PipelineGraphState, phase: int) -> bool:
    return state.mode == PipelineMode.PHASE and state.target_phase == phase
```

Use `graph.set_conditional_entry_point(self._route_entry, {"phase_1": "phase_1", "phase_2": "phase_2", "phase_3": "phase_3"})`.

Update `_route_after_phase_1()` and `_route_after_phase_2()` to return `"end"` when the target phase is complete. Keep full mode unchanged.

**Step 4: Add API support for rerunning phase 2/3 from existing state**

Extend `PipelineRunRequest`:

```python
processing_run_id: str | None = None
```

Validation:

- `mode="phase"` still requires `target_phase`.
- If `target_phase > 1`, require `processing_run_id`.
- When `mode="phase"` and `processing_run_id` is present, do not require `content_base64`, `pre_parsed_markdown`, `query`, or `identifiers`.

In `start_pipeline_run()`:

- If phase mode uses an existing `processing_run_id`, call `existing_state = await runner.get_last_state(body.processing_run_id)`.
- Return 404 if missing.
- Build `initial_state = existing_state.model_copy(deep=True, update={"mode": PipelineMode.PHASE, "target_phase": body.target_phase, "pipeline_status": PipelineStatus.PENDING, "error_message": None, "error_phase": None, "completed_at": None})`.
- Do not create a new `source_document_id`.
- Return the existing run id and source document id.

**Step 5: Add review finalization endpoint**

Add response model:

```python
class PipelineFinalizeResponse(BaseModel):
    processing_run_id: str
    pipeline_status: str
    completed_at: str
```

Add route:

```python
@router.post("/runs/{processing_run_id}/finalize", response_model=PipelineFinalizeResponse)
async def finalize_pipeline_run(processing_run_id: str, _api_key: str | None = Depends(require_api_key)):
    runner = get_pipeline_runner()
    state = await runner.get_last_state(processing_run_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Pipeline run {processing_run_id} not found")
    if state.pipeline_status == PipelineStatus.COMPLETED:
        return PipelineFinalizeResponse(...)
    if state.pipeline_status != PipelineStatus.AWAITING_REVIEW:
        raise HTTPException(status_code=409, detail="Only awaiting_review runs can be finalized")
    finalized = await runner.finalize_review(processing_run_id)
    if finalized is None:
        raise HTTPException(status_code=404, detail=f"Pipeline run {processing_run_id} not found")
    return PipelineFinalizeResponse(...)
```

Add `finalize_review()` to `PipelineRunner` and `SessionBoundStatePersistence`. It must only transition `PipelineStatus.AWAITING_REVIEW -> PipelineStatus.COMPLETED`. The route does the pre-transition guard; repeat calls against already completed runs are idempotent at the route layer.

**Step 6: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/agents/test_orchestrator.py tests/api/test_pipeline_api.py -q
```

Expected: PASS. Existing full pipeline orchestration tests must remain unchanged.

**Step 7: Commit**

```bash
git add backend/src/agents/orchestrator.py backend/src/api/v1/pipeline.py backend/src/agents/state_persistence.py backend/src/agents/runner.py backend/tests/agents/test_orchestrator.py backend/tests/api/test_pipeline_api.py
git commit -m "fix: repair phase mode and review finalization"
```

---

### Task 6: Make Evidence Patches Preserve Field-Level Payloads

**Files:**
- Modify: `backend/src/dao/postgresql/contracts.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/repositories.py:944-960`
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py:54-90`
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/feedback_service.py:67-80`
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/delta_audit_service.py:21-42`
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py:205-217`
- Modify: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_feedback_service.py`
- Modify: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py`
- Modify: `backend/tests/core/standardize_entities_and_align_knowledge/test_repositories.py`

**Step 1: Write failing field-level payload regression test**

Add to `test_feedback_service.py`:

```python
async def test_patch_preserves_field_level_active_payload_keys(self, db_session: AsyncSession) -> None:
    evidence_id = await self._create_test_evidence(
        db_session,
        field_id="B.disease_diagnosis",
        active_payload={
            "field_id": "B.disease_diagnosis",
            "field_name": "Disease diagnosis",
            "value": "Fabry disease",
            "group_id": "case-1",
            "track": "original",
            "source": {"text_snippet": "Fabry disease was diagnosed"},
            "entity_id": "entity-1",
        },
    )

    service = FeedbackService(db_session)
    await service.patch_evidence(
        canonical_evidence_id=evidence_id,
        patch=EvidencePatchRequest(fields={"disease": "Fabry disease type I"}),
        reviewer_id=None,
    )

    evidence = await db_session.get(CanonicalEvidenceItem, evidence_id)
    assert evidence is not None
    assert evidence.active_payload["group_id"] == "case-1"
    assert evidence.active_payload["source"] == {"text_snippet": "Fabry disease was diagnosed"}
    assert evidence.active_payload["track"] == "original"
    assert evidence.active_payload["entity_id"] == "entity-1"
    assert evidence.active_payload["value"] == "Fabry disease type I"
```

Update `_create_test_evidence()` to accept optional `field_id` and `active_payload`.

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_feedback_service.py::TestFeedbackService::test_patch_preserves_field_level_active_payload_keys -q
```

Expected: FAIL because `FeedbackService` replaces the whole payload with an `EvidenceCardPayload` dump.

**Step 3: Add canonical payload contract and projection helpers**

In `backend/src/dao/postgresql/contracts.py`, add a Pydantic model:

```python
class CanonicalEvidencePayload(BaseModel):
    """Field-level JSONB contract for CanonicalEvidenceItem.active_payload."""

    model_config = ConfigDict(extra="allow")

    value: str | list[str] | None = None
    group_id: str | None = None
    track: str | None = None
    field_id: str | None = None
    field_name: str | None = None
    source: dict[str, object] | None = None
    entity_id: str | None = None
```

`source` remains a permissive JSON object because extraction providers may attach additional raw span metadata. This is a field type, not a naked function return.

In Phase 3 repository payload creation, ensure the field id is always in the payload:

```python
payload = {
    **row.raw_payload,
    "field_id": row.field_id,
    "track": row.track,
    "entity_id": entity_ids_by_candidate_id.get(spec.candidate_id),
}
```

**Step 4: Add card projection helpers**

In `contracts.py`, keep `EvidenceCardPayload` as the review/delta projection, not the storage schema. Add:

```python
FIELD_ID_TO_CARD_FIELD: dict[str, str] = {
    "A.gene_symbol": "gene",
    "B.disease_diagnosis": "disease",
    "B.clinical_diagnosis": "disease",
    "J.authority_classification": "classification",
}


def card_field_for_field_id(field_id: str) -> str | None:
    if field_id.startswith("A.variant_hgvs_") or field_id == "A.variant_legacy_name":
        return "variant"
    return FIELD_ID_TO_CARD_FIELD.get(field_id)
```

Add:

```python
@classmethod
def from_field_payload(cls, *, field_id: str, payload: Mapping[str, object]) -> "EvidenceCardPayload":
    card = cls()
    card_field = card_field_for_field_id(field_id)
    if card_field is not None:
        return card.model_copy(update={card_field: payload.get("value")})
    return card
```

**Step 5: Change `FeedbackService.patch_evidence()` to merge, not replace**

Use field-level payload as the storage source:

```python
payload = dict(evidence.active_payload or {})
field_id = str(payload.get("field_id") or evidence.field_id)
old_card = EvidenceCardPayload.from_field_payload(field_id=field_id, payload=payload)

new_card_data = old_card.model_dump()
new_card_data.update(patch.fields)
new_card = EvidenceCardPayload(**new_card_data)
field_deltas = DeltaAuditService.compute_deltas(old_card, new_card)

card_field = card_field_for_field_id(field_id)
if card_field in patch.fields:
    payload["value"] = patch.fields[card_field]
payload.update({"field_id": field_id})
evidence.active_payload = payload
```

Do not write `new_card.model_dump()` into `active_payload`.

**Step 6: Update chat context projection**

In `chat_service.py`, replace direct `payload.get("gene")` reads with `EvidenceCardPayload.from_field_payload(field_id=evidence.field_id, payload=payload)`, then read the projected card fields:

```python
payload = evidence.active_payload or {}
card = EvidenceCardPayload.from_field_payload(
    field_id=evidence.field_id,
    payload=payload,
)

context_parts = [
    "**Evidence Card**",
    f"Gene: {card.gene or 'N/A'}",
    f"Variant: {card.variant or 'N/A'}",
    f"Phenotype: {card.phenotype or 'N/A'}",
    f"Disease: {card.disease or 'N/A'}",
    f"Classification: {card.classification or 'N/A'}",
    f"Evidence Strength: {card.evidence_strength or 'N/A'}",
    f"Summary: {card.summary or 'N/A'}",
]
```

This intentionally projects one field-level `CanonicalEvidenceItem` into one populated card field. It does not attempt to reconstruct a whole evidence group from a single canonical row.

**Step 7: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_feedback_service.py tests/core/visualize_evidence_with_expert_in_loop/test_feedback_profile_refresh.py tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py tests/core/standardize_entities_and_align_knowledge/test_repositories.py -q
```

Expected: PASS. Search tests should continue to read `active_payload["value"]` and `active_payload["group_id"]`.

**Step 8: Commit**

```bash
git add backend/src/dao/postgresql/contracts.py backend/src/core/standardize_entities_and_align_knowledge/repositories.py backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py backend/src/core/visualize_evidence_with_expert_in_loop/feedback_service.py backend/src/core/visualize_evidence_with_expert_in_loop/delta_audit_service.py backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py backend/tests/core/visualize_evidence_with_expert_in_loop/test_feedback_service.py backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py backend/tests/core/standardize_entities_and_align_knowledge/test_repositories.py
git commit -m "fix: preserve field-level evidence payloads"
```

---

### Task 7: Fix Phase 3 Skip Semantics

**Files:**
- Modify: `backend/src/agents/phase_3_adapter.py:123-145`
- Modify: `backend/tests/agents/test_phase_3_adapter.py:120-162`

**Step 1: Write failing ambiguous/unmapped tests**

Add tests:

```python
@pytest.mark.asyncio
async def test_phase_3_does_not_skip_when_ambiguous_entities_exist(sample_state):
    result_state = await _run_phase_3_with_counts(
        sample_state,
        match_count=1,
        standardized_count=0,
        ambiguous_count=1,
        unmapped_count=0,
    )

    assert result_state.skip_phase_3_reason is None
    assert result_state.phase_3_status.summary["ambiguous_count"] == 1


@pytest.mark.asyncio
async def test_phase_3_does_not_skip_when_unmapped_entities_exist(sample_state):
    result_state = await _run_phase_3_with_counts(
        sample_state,
        match_count=1,
        standardized_count=0,
        ambiguous_count=0,
        unmapped_count=1,
    )

    assert result_state.skip_phase_3_reason is None
    assert result_state.phase_3_status.summary["unmapped_count"] == 1
```

Extract the existing mock setup into `_run_phase_3_with_counts(...)`.

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/agents/test_phase_3_adapter.py::test_phase_3_does_not_skip_when_ambiguous_entities_exist tests/agents/test_phase_3_adapter.py::test_phase_3_does_not_skip_when_unmapped_entities_exist -q
```

Expected: FAIL because `standardized_count == 0` still sets `NO_CANDIDATES`.

**Step 3: Implement total candidate check**

Change the skip condition:

```python
candidate_count = (
    standardization_result.standardized_count
    + standardization_result.ambiguous_count
    + standardization_result.unmapped_count
)
if candidate_count == 0:
    state.skip_phase_3_reason = SkipPhase3Reason.NO_CANDIDATES
```

Include all counts in `phase_3_status.summary` for both skipped and non-skipped success paths:

```python
summary={
    "match_count": standardization_result.match_count,
    "standardized_count": standardization_result.standardized_count,
    "ambiguous_count": standardization_result.ambiguous_count,
    "unmapped_count": standardization_result.unmapped_count,
}
```

**Step 4: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/agents/test_phase_3_adapter.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/agents/phase_3_adapter.py backend/tests/agents/test_phase_3_adapter.py
git commit -m "fix: preserve phase 3 review candidates"
```

---

### Task 8: Fix URL Fallback Download Streaming

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/parse_document/orchestrator.py:117-124`
- Modify: `backend/tests/core/ingest_and_digitize_data/parse_document/test_orchestrator.py:152-168`

**Step 1: Write failing real-httpx-interface test**

Update `_make_pdf_response()` in the test to expose `aiter_bytes`, not the non-existent `ait_bytes`:

```python
async def _aiter_bytes():
    yield pdf_bytes

mock_response.aiter_bytes = _aiter_bytes
```

Add an assertion in `test_url_fallback_downloads_to_temp_and_cleans_up()`:

```python
assert mock_response.aiter_bytes is not None
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_orchestrator.py::test_url_fallback_downloads_to_temp_and_cleans_up -q
```

Expected: FAIL with `AttributeError: ait_bytes` before the fix.

**Step 3: Implement typo fix**

Change:

```python
async for chunk in resp.ait_bytes():
```

to:

```python
async for chunk in resp.aiter_bytes():
```

**Step 4: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/core/ingest_and_digitize_data/parse_document/test_orchestrator.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/parse_document/orchestrator.py backend/tests/core/ingest_and_digitize_data/parse_document/test_orchestrator.py
git commit -m "fix: stream parser fallback downloads"
```

---

### Task 9: Fail Closed In Production And Align Frontend Contracts

**Files:**
- Modify: `backend/src/core/config.py:203-406`
- Modify: `backend/tests/core/test_config.py`
- Modify: `frontend/src/lib/types/common.ts:20-26`
- Modify: `frontend/src/lib/api/client.ts:28-35`
- Modify: `frontend/src/lib/config/types.ts`
- Modify: `frontend/src/lib/config/api.ts`
- Modify: `frontend/src/features/pipeline/components/PhaseTimeline.tsx`
- Modify: `frontend/src/features/pipeline/components/PhaseDetailCard.tsx`
- Modify: `frontend/src/features/chat/components/forms/PipelineStatusCard.tsx`
- Modify: `frontend/tests/config/layeredConfig.test.ts`

**Step 1: Write failing backend config tests**

Add:

```python
def test_production_requires_api_key() -> None:
    with pytest.raises(ValueError, match="API_KEY"):
        Settings(environment="production", api_key="")


def test_production_accepts_api_key() -> None:
    settings = Settings(environment="production", api_key="secret")

    assert settings.is_production is True
    assert settings.api_key == "secret"
```

Add config propagation assertions:

```python
def test_llm_temperature_and_retries_are_propagated() -> None:
    settings = Settings(
        fast_llm_temperature=0.2,
        fast_llm_max_retries=3,
        reasoning_llm_temperature=0.1,
        reasoning_llm_max_retries=4,
    )

    assert settings.llm.temperature == 0.2
    assert settings.llm.max_retries == 3
    assert settings.reasoning.temperature == 0.1
    assert settings.reasoning.max_retries == 4
```

**Step 2: Run backend tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/core/test_config.py::test_production_requires_api_key tests/core/test_config.py::test_llm_temperature_and_retries_are_propagated -q
```

Expected: FAIL because production accepts empty `api_key`, and nested LLM configs do not expose temperature/max_retries.

**Step 3: Implement backend config changes**

Add fields to `LLMConfig` and `ReasoningConfig`:

```python
temperature: float | None = None
max_retries: int = 0
```

Pass flat values into nested configs in `_build_nested()`.

At the end of `_build_nested()`:

```python
if self.is_production and not self.api_key.strip():
    raise ValueError("API_KEY must be set when ENVIRONMENT=production")
```

**Step 4: Write frontend contract tests**

In `layeredConfig.test.ts`, assert API config exposes a non-public header name for local auth token mapping:

```typescript
it("pipeline statuses match backend lifecycle", () => {
  const statuses: ProcessingStatus[] = [
    "pending",
    "running",
    "awaiting_review",
    "completed",
    "failed",
    "skipped",
  ];
  assert.equal(statuses.includes("awaiting_review"), true);
});
```

Add a client interceptor test if the existing test harness supports importing `apiClient`; otherwise add a small pure helper in `frontend/src/lib/api/client.ts`:

```typescript
export function applyAuthHeaders(headers: AxiosRequestHeaders, token: string | null): void {
  if (!token) return;
  headers.Authorization = `Bearer ${token}`;
  headers["X-API-Key"] = token;
}
```

Test that both headers are applied for the current backend contract.

**Step 5: Implement frontend type/header changes**

Change `ProcessingStatus` to:

```typescript
export type ProcessingStatus =
  | "pending"
  | "running"
  | "awaiting_review"
  | "completed"
  | "failed"
  | "skipped";
```

Remove `"queued"` and `"cancelled"` from the shared backend status type. If UI components need display fallbacks for queued/cancelled, introduce a separate local UI-only type in that component.

Update `PhaseTimeline.tsx`, `PhaseDetailCard.tsx`, and `PipelineStatusCard.tsx` style/icon maps so they cover `pending`, `running`, `awaiting_review`, `completed`, `failed`, and `skipped`. Use `pending` wherever the UI currently means backend "not started"; keep `awaiting_review` visually distinct from `completed`.

Update the Axios interceptor to set `X-API-Key` from the same local token as a short-term compatibility bridge:

```typescript
if (token && config.headers) {
  config.headers.Authorization = `Bearer ${token}`;
  config.headers["X-API-Key"] = token;
}
```

Do not introduce `NEXT_PUBLIC_API_KEY`; that would expose a production secret in the browser.

Record this as technical debt in the code comment: `Authorization: Bearer` represents user auth, while `X-API-Key` is the backend's static service key. Sending the same browser token in both headers is only a transitional compatibility shim. The follow-up architecture should either implement real backend bearer-token auth or move static API-key injection to a Next.js server-side proxy that reads a server-only environment variable.

**Step 6: Run backend and frontend tests**

Run:

```bash
cd backend
uv run pytest tests/core/test_config.py tests/api/test_auth.py tests/api/test_pipeline_auth.py -q
```

Expected: PASS.

Run:

```bash
cd frontend
nvm use
npm run type-check
npm run lint
npm test
```

Expected: Type-check, lint, and frontend tests pass.

**Step 7: Commit**

```bash
git add backend/src/core/config.py backend/tests/core/test_config.py frontend/src/lib/types/common.ts frontend/src/lib/api/client.ts frontend/src/lib/config/types.ts frontend/src/lib/config/api.ts frontend/src/features/pipeline/components/PhaseTimeline.tsx frontend/src/features/pipeline/components/PhaseDetailCard.tsx frontend/src/features/chat/components/forms/PipelineStatusCard.tsx frontend/tests/config/layeredConfig.test.ts
git commit -m "fix: align auth and pipeline status contracts"
```

---

### Task 10: Focused Regression Suite And Documentation

**Files:**
- Modify: `progress.txt`
- Modify: `docs/README.md`
- Archive only if execution completes: `docs/plans/2026-06-11-pipeline-correctness-remediation.md`
- Optional: `lesson.md` if any debugging/failed approach happened during execution

**Step 1: Run focused backend suite**

Run:

```bash
cd backend
uv run pytest tests/agents tests/api/test_pipeline_api.py tests/api/test_pipeline_auth.py tests/core/visualize_evidence_with_expert_in_loop tests/core/ingest_and_digitize_data/parse_document/test_orchestrator.py tests/core/test_config.py tests/dao/postgresql/test_models.py tests/dao/postgresql/test_alembic_migration.py -q
```

Expected: PASS.

**Step 2: Run backend lint**

Run:

```bash
cd backend
uv run ruff check
```

Expected: PASS or only documented pre-existing failures. Do not ignore new failures from this plan.

**Step 3: Run frontend verification**

Run:

```bash
cd frontend
nvm use
npm run type-check
npm run lint
```

Expected: PASS.

**Step 4: Run migration check**

Run:

```bash
cd backend
uv run alembic -c ../database/alembic.ini heads
```

Expected: `pipeline_run_leases_20260611 (head)`.

**Step 5: Update progress**

Append:

```text
[2026-06-11] [Pipeline correctness remediation: multi-worker leases, payload preservation, phase mode, review finalization, auth/status contracts] [done]
```

If any bug investigation occurred, add a `lesson.md` entry with problem description, investigation, root cause, solution, and prevention.

**Step 6: Organize docs**

Run @doc-organize. Since the plan is still the execution record until merged, keep it indexed under `docs/plans/` during implementation. After all code is merged, mark the plan `completed`, move it to `docs/archive/plans/`, and update `docs/README.md`.

**Step 7: Final commit**

```bash
git add progress.txt docs/README.md docs/plans/2026-06-11-pipeline-correctness-remediation.md
git commit -m "docs: record pipeline remediation plan"
```

**Step 8: Final verification before handoff**

Run:

```bash
git status --short
```

Expected: no unintended changes. If unrelated user changes exist, leave them untouched and mention them in the handoff.
