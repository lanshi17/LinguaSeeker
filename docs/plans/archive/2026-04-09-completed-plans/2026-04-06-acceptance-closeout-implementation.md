# Acceptance Closeout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Record how `Task 14` and `Task 15` were executed for the mixed-source `v1.0` acceptance closeout.

**Architecture:** The acceptance manifest now carries execution inputs per paper row, the placeholder acceptance enqueue path has been replaced by a real internal executor, and the current `web`, `pubmed`, and internal non-`pubmed` `api` paths have been executed to complete the real acceptance manifest. The final release verification sweep has also been run. This document now remains as execution provenance for the completed closeout slice.

**Tech Stack:** FastAPI, Celery, PostgreSQL, SQLAlchemy, LangGraph, pytest, Vitest, `uv`, `loguru`.

---

### Task 1: Extend the acceptance manifest schema for executable rows

**Files:**
- Modify: `src/services/release_reporting.py`
- Modify: `tests/unit/test_release_reporting.py`
- Modify: `docs/acceptance/v1.0-100-paper-manifest.json`

**Step 1: Write the failing schema tests**

Add tests like:

```python
def test_acceptance_manifest_accepts_entry_kind_source_and_request_payload() -> None:
    manifest = AcceptanceManifest.model_validate(
        {
            "release_no": "v1.0",
            "locked": True,
            "expected_paper_count": 1,
            "papers": [
                {
                    "paper_id": "api-001",
                    "entry_kind": "api",
                    "source": "pmc",
                    "request_payload": {"query": "BARD1"},
                    "status": "queued",
                }
            ],
        }
    )
    assert manifest.papers[0].entry_kind == "api"
    assert manifest.papers[0].source == "pmc"
```

```python
def test_release_gate_summary_ignores_execution_metadata_for_counts() -> None:
    manifest = AcceptanceManifest.model_validate(...)
    summary = calculate_release_gate_summary(manifest)
    assert summary.manifest_entry_count == 1
```

**Step 2: Run the tests to verify failure**

Run:
```bash
uv run pytest -q tests/unit/test_release_reporting.py
```

Expected: FAIL because the manifest model does not yet accept execution metadata.

**Step 3: Implement the schema change**

In `src/services/release_reporting.py`:
1. add `entry_kind: Optional[str]`
2. add `source: Optional[str]`
3. add `request_payload: Optional[dict[str, Any]]`
4. add `request_id: Optional[str]`
5. keep summary/report calculations backward-compatible

Update the scaffold manifest shape in `docs/acceptance/v1.0-100-paper-manifest.json` so future real rows follow the executable schema.

**Step 4: Re-run the tests**

Run:
```bash
uv run pytest -q tests/unit/test_release_reporting.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/services/release_reporting.py tests/unit/test_release_reporting.py docs/acceptance/v1.0-100-paper-manifest.json
git commit -m "feat: extend acceptance manifest schema"
```

---

### Task 2: Add an internal acceptance executor and replace the placeholder enqueue lambda

**Files:**
- Create: `src/services/acceptance_executor.py`
- Create: `tests/unit/test_acceptance_executor.py`
- Modify: `scripts/run_acceptance_set.py`
- Modify: `src/services/acceptance_runner.py`

**Step 1: Write failing executor tests**

Add tests like:

```python
def test_enqueue_manifest_paper_dispatches_web_entries(monkeypatch) -> None:
    result = enqueue_manifest_paper(paper, dispatchers={...})
    assert result["request_id"] == "req-1"
    assert result["paper_task_id"] == "paper-1"
```

```python
def test_run_acceptance_set_uses_real_executor_and_writes_ids(monkeypatch) -> None:
    report = run_acceptance_set(manifest, enqueue=executor.enqueue_manifest_paper)
    assert manifest.papers[0].request_id == "req-1"
    assert manifest.papers[0].paper_task_id == "paper-1"
```

**Step 2: Run the tests to verify failure**

Run:
```bash
uv run pytest -q tests/unit/test_acceptance_executor.py tests/unit/test_acceptance_runner.py
```

Expected: FAIL because no real executor exists and the runner does not write `request_id`.

**Step 3: Implement the executor skeleton**

In `src/services/acceptance_executor.py`:
1. load one manifest paper row
2. validate `entry_kind`, `source`, and `request_payload`
3. dispatch to:
   - `enqueue_web_manifest_paper(...)`
   - `enqueue_api_manifest_paper(...)`
4. return a normalized dict with:
   - `request_id`
   - `paper_task_id`

In `src/services/acceptance_runner.py`:
1. keep `run_acceptance_set(...)` generic
2. write `request_id` back to the manifest paper row when returned by the enqueuer

In `scripts/run_acceptance_set.py`:
1. replace the placeholder lambda
2. instantiate and call the real acceptance executor
3. retain `--write`

**Step 4: Re-run the tests**

Run:
```bash
uv run pytest -q tests/unit/test_acceptance_executor.py tests/unit/test_acceptance_runner.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/services/acceptance_executor.py src/services/acceptance_runner.py scripts/run_acceptance_set.py tests/unit/test_acceptance_executor.py tests/unit/test_acceptance_runner.py
git commit -m "feat: add acceptance executor skeleton"
```

---

### Task 3: Reuse the current `web` and `pubmed` submit flows inside the acceptance executor

**Files:**
- Modify: `src/services/acceptance_executor.py`
- Modify: `tests/unit/test_acceptance_executor.py`
- Modify: `src/api/routes/task.py` (only if a small extraction helper is needed)
- Modify: `src/services/dtos.py` (only if direct model construction needs a tiny schema tweak)

**Step 1: Write failing dispatch tests**

Add tests like:

```python
def test_enqueue_web_manifest_paper_calls_existing_web_flow(monkeypatch) -> None:
    result = executor.enqueue_manifest_paper(web_paper)
    assert result["paper_task_id"] == "web-paper-1"
```

```python
def test_enqueue_api_manifest_paper_reuses_pubmed_submit_for_pubmed_source(monkeypatch) -> None:
    result = executor.enqueue_manifest_paper(pubmed_paper)
    assert result["paper_task_id"] == "pubmed-paper-1"
```

**Step 2: Run the tests to verify failure**

Run:
```bash
uv run pytest -q tests/unit/test_acceptance_executor.py
```

Expected: FAIL because the executor does not yet call the current route flows.

**Step 3: Implement the reuse paths**

In `src/services/acceptance_executor.py`:
1. for `entry_kind="web"`, construct `WebLiteratureCrawlRequest` and call `create_task_request_by_web_crawl(...)`
2. for `entry_kind="api"` and `source="pubmed"`, construct `PubMedSelectionSubmitRequest` and call `submit_pubmed_selection(...)`
3. normalize the returned `TaskRequestCreateResponse` into one acceptance-executor result

Rule:
1. acceptance rows stay `entry_kind="api"` for PubMed
2. only the internal executor is allowed to special-case `source="pubmed"`

**Step 4: Re-run the tests**

Run:
```bash
uv run pytest -q tests/unit/test_acceptance_executor.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/services/acceptance_executor.py tests/unit/test_acceptance_executor.py src/api/routes/task.py src/services/dtos.py
git commit -m "feat: reuse web and pubmed flows for acceptance executor"
```

---

### Task 4: Add the missing internal non-`pubmed` `api` submit path and queue entry

**Files:**
- Create: `src/services/api_request_submission.py`
- Modify: `src/services/acceptance_executor.py`
- Modify: `src/infrastructure/postgres.py`
- Modify: `tests/unit/test_acceptance_executor.py`
- Create: `tests/unit/test_api_request_submission.py`

**Step 1: Write failing submission tests**

Add tests like:

```python
def test_submit_api_acceptance_item_creates_request_document_and_paper_task(monkeypatch) -> None:
    result = submit_api_acceptance_item(...)
    assert result["request_id"]
    assert result["paper_task_id"]
```

```python
def test_submit_api_acceptance_item_enqueues_process_api_paper_task(monkeypatch) -> None:
    result = submit_api_acceptance_item(...)
    assert fake_apply_async.called
```

**Step 2: Run the tests to verify failure**

Run:
```bash
uv run pytest -q tests/unit/test_api_request_submission.py tests/unit/test_acceptance_executor.py
```

Expected: FAIL because there is no internal non-`pubmed` `api` submit helper.

**Step 3: Implement the helper**

In `src/services/api_request_submission.py`:
1. create `task_request`
2. create `document`
3. create `paper_task`
4. persist request/document metadata carrying the real provider and normalized request payload
5. enqueue `process_api_paper_task`
6. return:
   - `request_id`
   - `paper_task_id`

In `src/services/acceptance_executor.py`:
1. route `entry_kind="api"` with non-`pubmed` source into `submit_api_acceptance_item(...)`

**Step 4: Re-run the tests**

Run:
```bash
uv run pytest -q tests/unit/test_api_request_submission.py tests/unit/test_acceptance_executor.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/services/api_request_submission.py src/services/acceptance_executor.py src/infrastructure/postgres.py tests/unit/test_api_request_submission.py tests/unit/test_acceptance_executor.py
git commit -m "feat: add internal api acceptance submit path"
```

---

### Task 5: Implement `process_api_paper_task` using the current literature pipeline helpers

**Files:**
- Modify: `src/services/task_manager.py`
- Modify: `src/celery_app.py`
- Modify: `tests/unit/test_tasks.py`
- Create: `tests/unit/test_process_api_paper_task.py`

**Step 1: Write failing task tests**

Add tests like:

```python
def test_process_api_paper_task_success_persists_source_trace_and_emits_kg_event(monkeypatch):
    result = process_api_paper_task.run(...)
    assert result["status"] == "success"
    assert result["trace_chain"]["steps"]["acquisition"]["outcome"] == "success"
```

```python
def test_process_api_paper_task_marks_fulltext_unavailable_when_only_metadata_exists(monkeypatch):
    result = process_api_paper_task.run(...)
    assert result["fulltext_unavailable"] is True
```

**Step 2: Run the tests to verify failure**

Run:
```bash
uv run pytest -q tests/unit/test_process_api_paper_task.py tests/unit/test_tasks.py
```

Expected: FAIL because the task does not exist.

**Step 3: Implement the task**

In `src/services/task_manager.py`:
1. add `process_api_paper_task`
2. acquisition:
   - call `literature_unified_workflow(...)`
   - set `prefer="api"`
   - set `api_provider=source`
   - preserve `source_trace`
3. if a PDF is downloaded:
   - continue through parsing -> translation -> extraction -> acmg using current shared helpers
4. if only metadata/abstract evidence is available:
   - continue through the PubMed-style fallback path
   - set `fulltext_unavailable=true`
5. on success:
   - update paper status
   - persist `warning_codes`, `trace_chain`
   - emit KG event

In `src/celery_app.py`:
1. add an explicit route for `tasks.process_api_paper` if needed

**Step 4: Re-run the tests**

Run:
```bash
uv run pytest -q tests/unit/test_process_api_paper_task.py tests/unit/test_tasks.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/services/task_manager.py src/celery_app.py tests/unit/test_process_api_paper_task.py tests/unit/test_tasks.py
git commit -m "feat: add api acceptance paper task"
```

---

### Task 6: Execute the real `Task 14` acceptance run

**Files:**
- Modify: `docs/acceptance/v1.0-100-paper-manifest.json`
- Create: `docs/release/v1.0-release-report.md`
- Modify: `progress.txt`
- Modify: `lesson.md` (only if a new debugging root cause is discovered)

**Step 1: Populate and lock the real manifest**

Fill `docs/acceptance/v1.0-100-paper-manifest.json` with:
1. exactly 100 rows
2. mixed-source composition matching the agreed acceptance split
3. executable fields:
   - `entry_kind`
   - `source`
   - `request_payload`
4. `locked=true`

**Step 2: Run the acceptance executor**

Run:
```bash
uv run python scripts/run_acceptance_set.py --manifest docs/acceptance/v1.0-100-paper-manifest.json --write
```

Expected:
1. real `request_id` / `paper_task_id` values are written back
2. enqueue failures are recorded honestly, not hidden

**Step 3: Sync actual task results into the manifest**

Run:
```bash
uv run python scripts/sync_acceptance_manifest.py --manifest docs/acceptance/v1.0-100-paper-manifest.json --write
```

Expected:
1. executed rows have actual `status`
2. `error_code` is populated when relevant
3. timing fields are populated when available

**Step 4: Render the final release report**

Run:
```bash
uv run python scripts/release_report.py --manifest docs/acceptance/v1.0-100-paper-manifest.json --output docs/release/v1.0-release-report.md
```

Expected: honest gate output based on the real run.

**Step 5: Verify acceptance/report helpers**

Run:
```bash
uv run pytest -q tests/unit/test_acceptance_executor.py tests/unit/test_api_request_submission.py tests/unit/test_process_api_paper_task.py tests/unit/test_acceptance_runner.py tests/unit/test_release_reporting.py
```

Expected: PASS.

**Step 6: Record the acceptance milestone**

Update:
1. `progress.txt`
2. `lesson.md` only if the real run reveals a new root cause worth preserving

**Step 7: Commit**

```bash
git add docs/acceptance/v1.0-100-paper-manifest.json docs/release/v1.0-release-report.md progress.txt lesson.md
git commit -m "release: run mixed-source v1.0 acceptance"
```

---

### Task 7: Run `Task 15` final verification sweep

**Files:**
- Verify only

**Step 1: Run the backend focused release suite**

```bash
uv run pytest -q tests/unit/test_kg_events.py tests/unit/test_kg_consumer.py tests/unit/test_kg_backfill.py tests/unit/test_graph_variant_fanout.py tests/unit/test_acceptance_executor.py tests/unit/test_api_request_submission.py tests/unit/test_process_api_paper_task.py tests/unit/test_acceptance_runner.py tests/unit/test_release_reporting.py tests/unit/test_traceability.py tests/unit/test_tasks.py tests/integration/test_task_api.py tests/test_task_manager_pdf_download.py tests/test_literature_unified_workflow.py tests/test_agents_acquisition.py tests/test_supervisor.py tests/test_supervisor_e2e.py
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

**Step 5: Record final closeout**

Update:
1. `progress.txt`
2. `lesson.md` only if the final sweep uncovers a new root cause

**Step 6: Commit**

```bash
git add progress.txt lesson.md
git commit -m "release: complete final verification sweep"
```
