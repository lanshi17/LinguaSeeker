# Release Closure Program Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Record the release-closure program accurately and finish the final acceptance/report closeout on `yangzs-agents`.

**Architecture:** Tasks `1-13` are already landed on the current branch: KG outbox/consumer/backfill, multi-variant graph fan-out, remaining M2 result/export surfaces, acceptance helpers, and repo-wide quality cleanup are present in code and re-verified by focused tests and static checks. The active remaining work is to lock the real 100-paper manifest, run the acceptance/report flow, and execute the final verification sweep.

**Tech Stack:** FastAPI, Celery, PostgreSQL, SQLAlchemy, Neo4j, LangGraph, React/Vite, Vitest, pytest, `uv`, `loguru`.

**Git Note:** This repository often runs under “do not commit unless explicitly requested.” Each task includes a suggested commit step, but only run it if the user explicitly asks for commits in the execution session.

**Current Branch Snapshot (verified against actual code on 2026-04-06):**
1. `Task 1-13` are already landed on `yangzs-agents`.
2. The only active backlog items are `Task 14` and `Task 15`.
3. `Task 14` is blocked until `docs/acceptance/v1.0-100-paper-manifest.json` is populated with the real fixed 100-paper set and `locked=true`.
4. Historical task bodies below are retained as execution provenance for the already-landed slices.

---

### Task 1: Close `Task 7` baseline docs and capture merged-branch regression evidence

**Files:**
- Modify: `docs/plans/README.md`
- Modify: `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md`
- Modify: `docs/plans/2026-04-05-m3-m4-service-boundary-and-contract-verification-implementation.md`
- Modify: `progress.txt`
- Modify: `lesson.md`

**Step 1: Run the merged-branch focused regression baseline**

Run:
```bash
uv run pytest -q tests/unit/test_traceability.py tests/unit/test_release_reporting.py tests/unit/test_tasks.py tests/integration/test_task_api.py tests/test_task_manager_pdf_download.py tests/test_literature_unified_workflow.py tests/test_agents_acquisition.py tests/test_supervisor.py tests/test_supervisor_e2e.py
```

Expected: PASS. If it fails, stop here and fix the branch before any new functionality.

**Step 2: Update docs so they describe the current merged branch exactly**

Required outcomes:
1. `Task 4-6` are described as already landed.
2. The historical checkpoint state at `Task 1` time records remaining work as:
   - KG independent service
   - multi-variant graph fan-out
   - remaining frontend result/export surfaces
   - repo-wide quality cleanup
   - real 100-paper acceptance run
3. The real acceptance run remains explicitly unfinished.

**Step 3: Record the closeout checkpoint**

Append one `progress.txt` entry and one `lesson.md` note summarizing:
1. what was verified
2. what remains
3. that this checkpoint is documentation/regression only

**Step 4: Re-run the same focused suite**

Run the same command from Step 1.

Expected: PASS again.

**Step 5: Commit**

```bash
git add docs/plans/README.md docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md docs/plans/2026-04-05-m3-m4-service-boundary-and-contract-verification-implementation.md progress.txt lesson.md
git commit -m "docs: close release baseline task 7 state"
```

---

### Task 2: Add failing tests for a PostgreSQL-backed KG event outbox

**Files:**
- Create: `tests/unit/test_kg_events.py`
- Modify: `src/infrastructure/models.py`
- Modify: `src/infrastructure/postgres.py`
- Create: `src/services/kg_events.py`
- Create: `database/alembic/versions/20260406_01_add_kg_event_outbox.py`

**Step 1: Write the failing outbox tests**

```python
def test_create_kg_event_persists_minimal_outbox_payload(...):
    event = service.create_kg_event(
        request_id=request_id,
        paper_task_id=paper_task_id,
        document_id=document_id,
        event_type="paper_completed",
        idempotency_key="kg:v1.0:paper_completed:paper-1",
        payload={"release_no": "v1.0"},
    )
    assert event.status == "pending"
    assert event.payload["release_no"] == "v1.0"


def test_create_kg_event_is_idempotent_by_key(...):
    first = service.create_kg_event(..., idempotency_key="same-key", ...)
    second = service.create_kg_event(..., idempotency_key="same-key", ...)
    assert second.event_id == first.event_id
```

**Step 2: Run the tests to verify they fail**

Run:
```bash
uv run pytest -q tests/unit/test_kg_events.py
```

Expected: FAIL because the outbox model/helpers do not exist.

**Step 3: Add the minimal outbox schema and helpers**

Implement:
1. a new SQLAlchemy model for KG events
2. PostgreSQL helpers to create, fetch, list pending, and update event status
3. a thin service wrapper in `src/services/kg_events.py`
4. an Alembic migration that creates the outbox table and indexes

Minimal model fields:
```python
event_id: UUID
request_id: UUID | None
paper_task_id: UUID | None
document_id: UUID | None
event_type: str
idempotency_key: str
status: str  # pending/running/success/failed
payload: dict
attempt_count: int
last_error: str | None
created_at / updated_at
```

**Step 4: Re-run the tests**

Run:
```bash
uv run pytest -q tests/unit/test_kg_events.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/unit/test_kg_events.py src/infrastructure/models.py src/infrastructure/postgres.py src/services/kg_events.py database/alembic/versions/20260406_01_add_kg_event_outbox.py
git commit -m "feat: add kg event outbox"
```

---

### Task 3: Wire paper-success paths to emit KG outbox events without regressing paper success

**Files:**
- Modify: `tests/unit/test_tasks.py`
- Modify: `src/services/task_manager.py`
- Modify: `src/services/kg_events.py`

**Step 1: Write failing paper-success emission tests**

```python
def test_process_pubmed_paper_task_emits_kg_event_after_success(monkeypatch):
    ...
    result = tasks_module.process_pubmed_paper_task.run(...)
    assert fake_kg_events.created[0]["paper_task_id"] == paper_task_id
    assert result["status"] == "success"


def test_process_pubmed_paper_task_keeps_success_when_kg_emit_fails(monkeypatch):
    ...
    result = tasks_module.process_pubmed_paper_task.run(...)
    assert result["status"] == "success"
    assert fake_pg.paper_logs[-1]["message"].startswith("KG event enqueue failed")
```

Mirror the same behavior for the upload and web success paths if they are implemented through different code branches.

**Step 2: Run the failing tests**

Run:
```bash
uv run pytest -q tests/unit/test_tasks.py::test_process_pubmed_paper_task_emits_kg_event_after_success tests/unit/test_tasks.py::test_process_pubmed_paper_task_keeps_success_when_kg_emit_fails
```

Expected: FAIL because task success does not emit KG events yet.

**Step 3: Implement additive KG event emission**

Add a small helper in `task_manager.py`:
```python
def _emit_kg_event_for_success(...):
    return kg_events.create_kg_event(
        event_type="paper_completed",
        idempotency_key=...,
        payload={"release_no": "v1.0"},
    )
```

Rules:
1. emit only after PostgreSQL evidence/results are persisted
2. log enqueue success/failure on the paper task
3. never downgrade a successful paper to failed because event enqueue failed

**Step 4: Re-run the targeted tests**

Run the same command from Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/unit/test_tasks.py src/services/task_manager.py src/services/kg_events.py
git commit -m "feat: emit kg events from paper success paths"
```

---

### Task 4: Add failing tests for the independent KG consumer and dedicated Celery queue

**Files:**
- Create: `tests/unit/test_kg_consumer.py`
- Modify: `src/celery_app.py`
- Create: `src/services/kg_consumer.py`
- Create: `src/services/kg_tasks.py`
- Create: `scripts/kg_consumer.py`

**Step 1: Write the failing consumer tests**

```python
def test_process_kg_event_loads_event_and_resyncs_document(monkeypatch):
    ...
    result = kg_consumer.process_kg_event(event_id)
    assert result["status"] == "success"
    assert fake_sync.calls == ["doc-1"]


def test_process_kg_event_marks_failure_and_preserves_attempt_count(monkeypatch):
    ...
    with pytest.raises(RuntimeError):
        kg_consumer.process_kg_event(event_id)
    assert fake_events.updated[-1]["status"] == "failed"
    assert fake_events.updated[-1]["attempt_count"] == 1
```

**Step 2: Run the tests to verify failure**

Run:
```bash
uv run pytest -q tests/unit/test_kg_consumer.py
```

Expected: FAIL because the consumer and KG queue do not exist.

**Step 3: Implement the consumer and Celery task**

Implementation requirements:
1. add a dedicated `kg` queue in `src/celery_app.py`
2. include `src.services.kg_tasks`
3. implement `process_kg_event(event_id)` in `src/services/kg_consumer.py`
4. implement a Celery task in `src/services/kg_tasks.py` that calls the consumer
5. add `scripts/kg_consumer.py` as a CLI wrapper for replaying a single event or a pending batch

Reuse the existing graph path:
```python
sync_service = get_graph_sync_service()
sync_service.resync_document(document_id)
```

**Step 4: Re-run the consumer tests**

Run:
```bash
uv run pytest -q tests/unit/test_kg_consumer.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/unit/test_kg_consumer.py src/celery_app.py src/services/kg_consumer.py src/services/kg_tasks.py scripts/kg_consumer.py
git commit -m "feat: add independent kg consumer queue"
```

---

### Task 5: Add failing tests for resumable KG backfill

**Files:**
- Create: `tests/unit/test_kg_backfill.py`
- Create: `src/services/kg_backfill.py`
- Create: `scripts/kg_backfill.py`

**Step 1: Write the failing backfill tests**

```python
def test_backfill_runs_from_checkpoint_and_updates_checkpoint_file(tmp_path, monkeypatch):
    checkpoint = tmp_path / "kg-backfill.json"
    ...
    report = run_kg_backfill(checkpoint_path=checkpoint, batch_size=2)
    assert report["processed"] == 2
    assert json.loads(checkpoint.read_text())["last_paper_task_id"] == "paper-2"


def test_backfill_resume_skips_completed_prefix(tmp_path, monkeypatch):
    checkpoint.write_text(json.dumps({"last_paper_task_id": "paper-2"}))
    ...
    report = run_kg_backfill(checkpoint_path=checkpoint, batch_size=10)
    assert report["processed_paper_task_ids"] == ["paper-3"]
```

**Step 2: Run the tests to verify failure**

Run:
```bash
uv run pytest -q tests/unit/test_kg_backfill.py
```

Expected: FAIL because the backfill runner does not exist.

**Step 3: Implement minimal resumable backfill**

Implementation rules:
1. backfill source is PostgreSQL paper/evidence data, not Neo4j
2. reuse the same consumer execution path used by incremental events
3. checkpoint format is explicit JSON with at least `last_paper_task_id` and timestamp
4. allow `--batch-size` and `--checkpoint` in the CLI wrapper

**Step 4: Re-run the tests**

Run:
```bash
uv run pytest -q tests/unit/test_kg_backfill.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/unit/test_kg_backfill.py src/services/kg_backfill.py scripts/kg_backfill.py
git commit -m "feat: add resumable kg backfill"
```

---

### Task 6: Add failing tests for multi-variant graph fan-out

**Files:**
- Create: `tests/unit/test_graph_variant_fanout.py`
- Modify: `src/domain/graph/sync.py`
- Modify: `src/infrastructure/postgres.py`

**Step 1: Write the failing fan-out tests**

```python
def test_sync_evidence_fans_out_multiple_variants_into_multiple_pg_rows(monkeypatch):
    evidence_output = {
        "extracted_fields": {
            "variant": {
                "hgvs_c": "c.1972C>T; c.1935_1954dup; c.1526T>C",
                "hgvs_p": "p.Arg658Cys; p.Glu652fs; p.Ile509Thr",
            },
            ...
        }
    }
    result = service.sync_evidence(document_id, evidence_output)
    assert result["pg_evidence_ids"] == [1, 2, 3]
```

```python
def test_sync_evidence_keeps_paper_level_success_shape_when_fanout_occurs(monkeypatch):
    result = service.sync_evidence(document_id, evidence_output)
    assert result["neo4j_synced"] is True
    assert result["skipped"] is False
```

**Step 2: Run the tests to verify failure**

Run:
```bash
uv run pytest -q tests/unit/test_graph_variant_fanout.py
```

Expected: FAIL because graph sync still collapses multiple variants into one record.

**Step 3: Add a dedicated fan-out helper**

Create an internal helper in `src/domain/graph/sync.py` or a small adjacent helper module that:
1. splits multi-value HGVS strings
2. pairs `hgvs_c` and `hgvs_p` conservatively
3. returns one normalized variant payload per row
4. falls back to one row when splitting is impossible

Minimal shape:
```python
[
    {"variant_hgvs_c": "c.1972C>T", "variant_hgvs_p": "p.Arg658Cys"},
    {"variant_hgvs_c": "c.1935_1954dup", "variant_hgvs_p": "p.Glu652fs"},
]
```

**Step 4: Persist one PostgreSQL row per normalized variant**

Update `sync_evidence()` and `create_evidence_record()` call sites so PostgreSQL is the first place where fan-out becomes real.

**Step 5: Re-run the tests**

Run:
```bash
uv run pytest -q tests/unit/test_graph_variant_fanout.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add tests/unit/test_graph_variant_fanout.py src/domain/graph/sync.py src/infrastructure/postgres.py
git commit -m "feat: fan out multi-variant graph evidence"
```

---

### Task 7: Add failing tests that KG consumer uses fan-out PostgreSQL rows unchanged

**Files:**
- Modify: `tests/unit/test_kg_consumer.py`
- Modify: `tests/unit/test_kg_backfill.py`
- Modify: `src/services/kg_consumer.py`
- Modify: `src/services/kg_backfill.py`

**Step 1: Extend the consumer/backfill tests**

```python
def test_process_kg_event_resyncs_document_after_pg_fanout(monkeypatch):
    ...
    assert fake_sync.calls == ["doc-1"]
    assert fake_sync.received_pg_variant_count == 3
```

```python
def test_backfill_reuses_same_resync_path_as_incremental_consumer(monkeypatch):
    ...
    assert fake_sync.calls == ["doc-1", "doc-2"]
```

**Step 2: Run the tests to verify at least one fails**

Run:
```bash
uv run pytest -q tests/unit/test_kg_consumer.py tests/unit/test_kg_backfill.py
```

Expected: FAIL until the consumer/backfill path is verified against fan-out expectations.

**Step 3: Keep consumer and backfill logic PG-first**

Implementation rule:
1. do not split variants inside the KG consumer
2. do not create a second variant-normalization path in KG code
3. only consume the already normalized PostgreSQL state

**Step 4: Re-run the tests**

Run the same command from Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/unit/test_kg_consumer.py tests/unit/test_kg_backfill.py src/services/kg_consumer.py src/services/kg_backfill.py
git commit -m "test: pin kg consumer against pg fanout contract"
```

---

### Task 8: Add failing tests for a stable paper-task detail read model

**Files:**
- Modify: `tests/integration/test_task_api.py`
- Modify: `src/services/dtos.py`
- Modify: `src/api/routes/task.py`

**Step 1: Write failing backend tests for `GET /tasks/papers/{paper_task_id}`**

```python
def test_get_paper_task_detail_returns_trace_chain_warning_codes_and_result(client, postgres_stub):
    response = client.get(f"{cfg.api_prefix}/tasks/papers/{paper_task_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["paper_task_id"] == str(paper_task_id)
    assert payload["warning_codes"] == ["FULLTEXT_UNAVAILABLE"]
    assert payload["trace_chain"]["steps"]["acquisition"]["status"] == "COMPLETED"
    assert payload["result_payload"]["graph_sync_result"]["neo4j_ok"] is True
```

**Step 2: Run the test to verify it fails**

Run:
```bash
uv run pytest -q tests/integration/test_task_api.py::test_get_paper_task_detail_returns_trace_chain_warning_codes_and_result
```

Expected: FAIL because the endpoint/DTO does not exist.

**Step 3: Implement the additive read-model DTO and route**

Add:
1. `PaperTaskDetailResponse` in `src/services/dtos.py`
2. `GET /tasks/papers/{paper_task_id}` in `src/api/routes/task.py`

Include at least:
```python
paper_task_id
request_id
document_id
status
workflow_status
processing_steps
warning_codes
trace_chain
fulltext_unavailable
result_payload
parsing_metadata
duplicate_of
```

**Step 4: Re-run the test**

Run the same command from Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/integration/test_task_api.py src/services/dtos.py src/api/routes/task.py
git commit -m "feat: add paper task detail read model"
```

---

### Task 9: Add failing frontend tests for request monitor, document, and export views

**Files:**
- Modify: `../frontend/src/services/api.ts`
- Modify: `../frontend/src/types/api.ts`
- Modify: `../frontend/src/pages/requests/request-monitor-page.test.tsx`
- Create: `../frontend/src/pages/documents/document-page.test.tsx`
- Modify: `../frontend/src/pages/requests/request-export-page.test.tsx`
- Create: `../frontend/src/utils/normalizePaperResult.ts`
- Create: `../frontend/src/utils/normalizePaperResult.test.ts`

**Step 1: Write failing monitor-page tests**

```tsx
it('renders duplicate/fulltext labels and 6-node detail from paper task detail API', async () => {
  ...
  expect(await screen.findByText(/fulltext unavailable/i)).toBeInTheDocument();
  expect(screen.getByText(/classification/i)).toBeInTheDocument();
  expect(screen.getByText(/adjudication/i)).toBeInTheDocument();
});
```

**Step 2: Write failing document/export tests**

```tsx
it('document page renders classification and adjudication summary cards', async () => {
  ...
  expect(await screen.findByText(/ACMG classification/i)).toBeInTheDocument();
  expect(screen.getByText(/Expert adjudication/i)).toBeInTheDocument();
});

it('export page renders reading plus judgment sections for print view', async () => {
  ...
  expect(await screen.findByText(/Evidence judgment/i)).toBeInTheDocument();
  expect(screen.getByText(/ACMG classification/i)).toBeInTheDocument();
});
```

**Step 3: Run the frontend tests to verify failure**

Run:
```bash
npm --prefix ../frontend run test:run -- src/pages/requests/request-monitor-page.test.tsx src/pages/documents/document-page.test.tsx src/pages/requests/request-export-page.test.tsx src/utils/normalizePaperResult.test.ts
```

Expected: FAIL because the frontend still lacks the read-model client and richer rendering.

**Step 4: Add the frontend API/type surface**

Add:
1. `getPaperTaskDetail(...)` to `../frontend/src/services/api.ts`
2. matching response type to `../frontend/src/types/api.ts`
3. `normalizePaperResult(...)` helper for classification/adjudication/export-friendly view models

**Step 5: Re-run the tests**

Run the same command from Step 3.

Expected: still FAIL until the page implementations are updated in the next task.

**Step 6: Commit**

```bash
git add ../frontend/src/services/api.ts ../frontend/src/types/api.ts ../frontend/src/pages/requests/request-monitor-page.test.tsx ../frontend/src/pages/documents/document-page.test.tsx ../frontend/src/pages/requests/request-export-page.test.tsx ../frontend/src/utils/normalizePaperResult.ts ../frontend/src/utils/normalizePaperResult.test.ts
git commit -m "test(frontend): add request result and export coverage"
```

---

### Task 10: Implement the remaining M2 monitor/result/export surfaces

**Files:**
- Modify: `../frontend/src/pages/requests/request-monitor-page.tsx`
- Modify: `../frontend/src/pages/documents/document-page.tsx`
- Modify: `../frontend/src/pages/requests/request-export-page.tsx`
- Modify: `../frontend/src/services/api.ts`
- Modify: `../frontend/src/types/api.ts`
- Modify: `../frontend/src/utils/normalizePaperResult.ts`
- Test: `../frontend/src/pages/requests/request-monitor-page.test.tsx`
- Test: `../frontend/src/pages/documents/document-page.test.tsx`
- Test: `../frontend/src/pages/requests/request-export-page.test.tsx`
- Test: `../frontend/src/utils/normalizePaperResult.test.ts`

**Step 1: Update `RequestMonitorPage`**

Implementation requirements:
1. keep the existing route and overall page shell
2. fetch paper detail only when a paper row is expanded
3. render:
   - 6-node status
   - duplicate/fulltext-unavailable labels
   - warning codes
   - trace/source detail
4. do not break current request polling

**Step 2: Update `DocumentPage`**

Implementation requirements:
1. keep “Reading” and “Evidence judgment” tabs
2. replace raw JSON-only judgment view with structured cards sourced from `normalizePaperResult(...)`
3. keep a raw payload fallback block for unsupported payloads

**Step 3: Update `RequestExportPage`**

Implementation requirements:
1. keep the current route and print button
2. render a print-friendly reading section plus classification/adjudication section
3. preserve HTML print-to-PDF flow via `window.print()`
4. avoid introducing a server-side PDF renderer in this task

**Step 4: Run the frontend tests**

Run:
```bash
npm --prefix ../frontend run test:run -- src/pages/requests/request-monitor-page.test.tsx src/pages/documents/document-page.test.tsx src/pages/requests/request-export-page.test.tsx src/utils/normalizePaperResult.test.ts
```

Expected: PASS.

**Step 5: Run frontend build and lint**

Run:
```bash
npm --prefix ../frontend run build
npm --prefix ../frontend run lint
```

Expected: PASS.

**Step 6: Commit**

```bash
git add ../frontend/src/pages/requests/request-monitor-page.tsx ../frontend/src/pages/documents/document-page.tsx ../frontend/src/pages/requests/request-export-page.tsx ../frontend/src/services/api.ts ../frontend/src/types/api.ts ../frontend/src/utils/normalizePaperResult.ts ../frontend/src/pages/requests/request-monitor-page.test.tsx ../frontend/src/pages/documents/document-page.test.tsx ../frontend/src/pages/requests/request-export-page.test.tsx ../frontend/src/utils/normalizePaperResult.test.ts
git commit -m "feat(frontend): finish request monitor and export surfaces"
```

---

### Task 11: Add failing tests for acceptance manifest hydration and execution helpers

**Files:**
- Create: `tests/unit/test_acceptance_runner.py`
- Modify: `src/services/release_reporting.py`
- Create: `src/services/acceptance_runner.py`
- Create: `scripts/run_acceptance_set.py`
- Create: `scripts/sync_acceptance_manifest.py`

**Step 1: Write the failing acceptance helper tests**

```python
def test_sync_manifest_rows_from_postgres_updates_paper_statuses(tmp_path, monkeypatch):
    ...
    manifest = sync_manifest_from_postgres(manifest_path, postgres=fake_pg)
    assert manifest.papers[0].status == "success"
    assert manifest.papers[0].paper_task_id == "paper-1"


def test_run_acceptance_set_enqueues_missing_manifest_entries(monkeypatch):
    ...
    report = run_acceptance_set(manifest, enqueue=enqueuer)
    assert report["queued_count"] == 2
```

**Step 2: Run the tests to verify failure**

Run:
```bash
uv run pytest -q tests/unit/test_acceptance_runner.py
```

Expected: FAIL because the helper/service/scripts do not exist.

**Step 3: Implement the acceptance helpers**

Add:
1. `sync_manifest_from_postgres(...)` to refresh manifest rows from actual paper-task results
2. `run_acceptance_set(...)` to enqueue missing items from the locked acceptance set
3. thin script wrappers for both services

Keep the existing release-report renderer as the final markdown layer.

**Step 4: Re-run the tests**

Run:
```bash
uv run pytest -q tests/unit/test_acceptance_runner.py tests/unit/test_release_reporting.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/unit/test_acceptance_runner.py src/services/release_reporting.py src/services/acceptance_runner.py scripts/run_acceptance_set.py scripts/sync_acceptance_manifest.py
git commit -m "feat: add acceptance execution helpers"
```

---

### Task 12: Run release-critical `basedpyright` / `ruff` cleanup on touched scopes

**Files:**
- Modify: touched backend/frontend files from Tasks 2-11

**Step 1: Run release-critical static checks**

Run:
```bash
uv run basedpyright src/services/kg_events.py src/services/kg_consumer.py src/services/kg_tasks.py src/services/kg_backfill.py src/services/acceptance_runner.py src/domain/graph/sync.py src/api/routes/task.py src/services/dtos.py src/services/task_manager.py
uv run ruff check src/services/kg_events.py src/services/kg_consumer.py src/services/kg_tasks.py src/services/kg_backfill.py src/services/acceptance_runner.py src/domain/graph/sync.py src/api/routes/task.py src/services/dtos.py src/services/task_manager.py tests/unit/test_kg_events.py tests/unit/test_kg_consumer.py tests/unit/test_kg_backfill.py tests/unit/test_graph_variant_fanout.py tests/integration/test_task_api.py tests/unit/test_acceptance_runner.py
npm --prefix ../frontend run lint
```

Expected: at least one failure if the touched scope still has type/lint debt.

**Step 2: Fix only touched-scope issues**

Rules:
1. no broad ignore files
2. no behavior-only changes to satisfy style rules
3. keep fixes local to release-critical paths

**Step 3: Re-run the same static checks**

Expected: PASS.

**Step 4: Commit**

```bash
git add src/services/kg_events.py src/services/kg_consumer.py src/services/kg_tasks.py src/services/kg_backfill.py src/services/acceptance_runner.py src/domain/graph/sync.py src/api/routes/task.py src/services/dtos.py src/services/task_manager.py tests/unit/test_kg_events.py tests/unit/test_kg_consumer.py tests/unit/test_kg_backfill.py tests/unit/test_graph_variant_fanout.py tests/integration/test_task_api.py tests/unit/test_acceptance_runner.py ../frontend/src/pages/requests/request-monitor-page.tsx ../frontend/src/pages/documents/document-page.tsx ../frontend/src/pages/requests/request-export-page.tsx ../frontend/src/services/api.ts ../frontend/src/types/api.ts ../frontend/src/utils/normalizePaperResult.ts
git commit -m "chore: clean release critical lint and type issues"
```

---

### Task 13: Run hotspot then full-repo `basedpyright` / `ruff`

**Files:**
- Modify: any files needed to clear remaining full-repo errors
- Modify: `progress.txt`
- Modify: `lesson.md`

**Step 1: Run hotspot checks first**

Run:
```bash
uv run basedpyright src/config.py src/services/task_manager.py src/api/routes/task.py src/domain/graph/sync.py
uv run ruff check src/config.py src/services/task_manager.py src/api/routes/task.py src/domain/graph/sync.py tests/
```

Fix until the hotspot slice is green.

**Step 2: Run full-repo checks**

Run:
```bash
uv run basedpyright src/
uv run ruff check src/ tests/
```

Expected: FAIL until the remaining repository debt is cleared.

**Step 3: Fix the remaining full-repo issues**

Rules:
1. keep behavior changes minimal
2. prefer local refactors and explicit typing
3. if a legacy file truly cannot be fixed without expanding scope, stop and ask rather than adding a blind ignore

**Step 4: Re-run the full-repo checks**

Run the same commands from Step 2.

Expected: PASS.

**Step 5: Record the cleanup milestone**

Append one `progress.txt` milestone and one `lesson.md` note for any notable root cause.

**Step 6: Commit**

```bash
git add progress.txt lesson.md src/ tests/
git commit -m "chore: clear repo-wide lint and type debt"
```

---

### Task 14: Lock the 100-paper manifest, execute the acceptance set, and publish the final release report

**Files:**
- Modify: `docs/acceptance/v1.0-100-paper-manifest.json`
- Create: `docs/release/v1.0-release-report.md`
- Modify: `progress.txt`
- Modify: `lesson.md`
- Test: `tests/unit/test_acceptance_runner.py`
- Test: `tests/unit/test_release_reporting.py`

**Step 1: Lock the acceptance set**

Populate `docs/acceptance/v1.0-100-paper-manifest.json` with the fixed 100-paper set:
1. exactly 100 entries
2. `locked=true`
3. stable paper identifiers
4. any pre-agreed metadata required to enqueue or reconcile the papers

**Step 2: Run the acceptance set**

Run:
```bash
uv run python scripts/run_acceptance_set.py --manifest docs/acceptance/v1.0-100-paper-manifest.json
```

Expected: all manifest entries are enqueued or confirmed already complete.

**Step 3: Sync actual paper results back into the manifest**

Run:
```bash
uv run python scripts/sync_acceptance_manifest.py --manifest docs/acceptance/v1.0-100-paper-manifest.json --write
```

Expected: manifest rows now contain actual `paper_task_id`, `status`, `error_code`, and durations.

**Step 4: Render the final release report**

Run:
```bash
uv run python scripts/release_report.py --manifest docs/acceptance/v1.0-100-paper-manifest.json --output docs/release/v1.0-release-report.md
```

Expected: rendered markdown report with honest `gate_status` based on the actual run.

**Step 5: Verify the acceptance/report stack**

Run:
```bash
uv run pytest -q tests/unit/test_acceptance_runner.py tests/unit/test_release_reporting.py
```

Expected: PASS.

**Step 6: Record the final closeout**

Update:
1. `progress.txt` with the final acceptance/report milestone
2. `lesson.md` with any new operational/debugging lessons from the real run

**Step 7: Commit**

```bash
git add docs/acceptance/v1.0-100-paper-manifest.json docs/release/v1.0-release-report.md progress.txt lesson.md
git commit -m "release: run v1.0 acceptance and publish report"
```

---

### Task 15: Final verification sweep before completion

**Files:**
- Verify only

**Step 1: Run the backend focused release suite**

```bash
uv run pytest -q tests/unit/test_kg_events.py tests/unit/test_kg_consumer.py tests/unit/test_kg_backfill.py tests/unit/test_graph_variant_fanout.py tests/unit/test_acceptance_runner.py tests/unit/test_release_reporting.py tests/unit/test_traceability.py tests/unit/test_tasks.py tests/integration/test_task_api.py tests/test_task_manager_pdf_download.py tests/test_literature_unified_workflow.py tests/test_agents_acquisition.py tests/test_supervisor.py tests/test_supervisor_e2e.py
```

Expected: PASS.

**Step 2: Run frontend tests/build/lint**

```bash
npm --prefix ../frontend run test:run -- src/pages/requests/request-monitor-page.test.tsx src/pages/documents/document-page.test.tsx src/pages/requests/request-export-page.test.tsx src/utils/normalizePaperResult.test.ts src/pages/tasks/__tests__/task-new-page.test.tsx src/pages/tasks/__tests__/pubmed-candidates-page.test.tsx
npm --prefix ../frontend run build
npm --prefix ../frontend run lint
```

Expected: PASS.

**Step 3: Run final static checks**

```bash
uv run basedpyright src/
uv run ruff check src/ tests/
```

Expected: PASS.

**Step 4: Verify release artifacts exist**

```bash
test -f docs/acceptance/v1.0-100-paper-manifest.json
test -f docs/release/v1.0-release-report.md
test -f scripts/kg_consumer.py
test -f scripts/kg_backfill.py
test -f scripts/run_acceptance_set.py
test -f scripts/sync_acceptance_manifest.py
```

Expected: PASS.

**Step 5: Commit**

Only if the execution session is explicitly doing commits and there are remaining unstaged changes.
