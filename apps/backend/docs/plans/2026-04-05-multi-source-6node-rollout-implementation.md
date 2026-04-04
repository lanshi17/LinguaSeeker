# Multi-Source 6-Node Rollout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the existing backend baseline into a real multi-source + 6-node rollout by removing the hidden PubMed-only gate, wiring acquisition through the unified workflow, and preserving source traceability.

**Architecture:** Keep `src/domain/literature/unified/workflow.py` as the single routing surface for provider selection, retries, and source tracing. Reuse the existing acquisition planner and 6-node supervisor graph, but route non-upload acquisition through the unified workflow and verify the state contract with focused tests before broad regression runs.

**Tech Stack:** FastAPI backend, LangGraph, existing literature gateway adapters, pytest, Pydantic models, repository docs under `docs/`.

---

### Task 1: Replace MVP-only unified-workflow assumptions with failing tests

**Files:**
- Modify: `tests/test_literature_unified_workflow.py`
- Modify: `tests/unit/test_unified_source_selection_and_trace.py`
- Read: `src/domain/literature/unified/workflow.py`
- Read: `src/domain/literature/unified/models.py`

**Step 1: Write the failing test for explicit web routing**

```python
@pytest.mark.asyncio
async def test_unified_workflow_routes_to_web_provider_when_requested(monkeypatch):
    ...
    result = await literature_unified_workflow(
        {"query": "https://cyberleninka.ru/article/n/test", "prefer": "web", "raw": True}
    )
    assert result["success"] is True
    assert result["route"]["used"] == "web"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_literature_unified_workflow.py::test_unified_workflow_routes_to_web_provider_when_requested`
Expected: FAIL because the workflow still returns `mvp_pubmed_only`.

**Step 3: Write the failing test for explicit non-PMC API provider allowance**

```python
@pytest.mark.asyncio
async def test_unified_workflow_allows_explicit_unpaywall_provider(monkeypatch):
    ...
    result = await literature_unified_workflow(
        {"query": "10.1000/xyz-123", "prefer": "api", "api_provider": "unpaywall"}
    )
    assert result["success"] is True
    assert result["route"]["api_provider"] == "unpaywall"
```

**Step 4: Run test to verify it fails**

Run: `uv run pytest -q tests/test_literature_unified_workflow.py::test_unified_workflow_allows_explicit_unpaywall_provider`
Expected: FAIL because the workflow still rejects non-PMC API providers.

**Step 5: Commit**

Do not commit unless explicitly requested by the user.

---

### Task 2: Implement unified-workflow multi-source routing

**Files:**
- Modify: `src/domain/literature/unified/workflow.py`
- Modify: `src/domain/literature/unified/models.py`
- Test: `tests/test_literature_unified_workflow.py`
- Test: `tests/unit/test_unified_source_selection_and_trace.py`

**Step 1: Add the minimal routing helpers needed for web execution**

Implement only the smallest helpers required to:
1. choose `used=web` when `prefer=web` or `web_provider` is provided
2. preserve current API routing behavior for `crossref` / `pmc` / `unpaywall`
3. return route summaries in one stable shape

**Step 2: Remove the `mvp_pubmed_only` gates**

Delete the branches that reject:
1. any `web` preference
2. any non-PMC `api_provider`

Do not add new provider behavior outside the providers already present in the codebase.

**Step 3: Preserve retries and `source_trace`**

Keep per-attempt trace records for:
1. provider name
2. attempt number
3. success flag
4. item/download counts
5. warnings
6. error text

**Step 4: Run focused tests**

Run: `uv run pytest -q tests/test_literature_unified_workflow.py tests/unit/test_unified_source_selection_and_trace.py`
Expected: PASS.

**Step 5: Commit**

Do not commit unless explicitly requested by the user.

---

### Task 3: Add failing tests for acquisition-node integration with the unified workflow

**Files:**
- Modify: `tests/test_agents_acquisition.py`
- Read: `src/agents/acquisition/node.py`
- Read: `src/domain/literature/acquisition_agent.py`

**Step 1: Write the failing test for web acquisition invoking the unified workflow**

```python
def test_run_acquisition_node_web_invokes_unified_workflow(monkeypatch):
    ...
    result = acquisition_node.run_acquisition_node(state)
    assert result["node_trace"]["acquisition"] == "success"
    assert result["node_trace"]["acquisition_result"]["route"]["used"] == "web"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_agents_acquisition.py::test_run_acquisition_node_web_invokes_unified_workflow`
Expected: FAIL because the node currently stops at planning and never calls the unified workflow.

**Step 3: Write the failing test for no-result acquisition**

```python
def test_run_acquisition_node_raises_when_unified_workflow_returns_no_result(monkeypatch):
    ...
    with pytest.raises(ValidationException, match="FETCH_NO_RESULT"):
        acquisition_node.run_acquisition_node(state)
```

**Step 4: Run test to verify it fails**

Run: `uv run pytest -q tests/test_agents_acquisition.py::test_run_acquisition_node_raises_when_unified_workflow_returns_no_result`
Expected: FAIL.

**Step 5: Commit**

Do not commit unless explicitly requested by the user.

---

### Task 4: Implement acquisition-node unified-workflow integration

**Files:**
- Modify: `src/agents/acquisition/node.py`
- Modify: `src/state/global_state.py`
- Test: `tests/test_agents_acquisition.py`

**Step 1: Add the minimal state fields required for acquisition results**

Store standardized acquisition data in state using exact keys that tests assert, for example:
1. `acquisition_plan`
2. `acquisition_result`
3. `node_trace["acquisition_detail"]`
4. `node_trace["acquisition_result"]`

**Step 2: Keep upload behavior unchanged**

Do not route upload through the unified workflow.

**Step 3: Call the unified workflow for `pubmed` and `web`**

Use planned normalized values as inputs. Preserve the selected source in the request payload.

**Step 4: Convert no-result paths into contract-aligned failures**

If the unified workflow returns no items and no downloads, raise `ValidationException` with a `FETCH_NO_RESULT`-aligned message.

**Step 5: Run focused tests**

Run: `uv run pytest -q tests/test_agents_acquisition.py`
Expected: PASS.

**Step 6: Commit**

Do not commit unless explicitly requested by the user.

---

### Task 5: Add failing regression tests for 6-node trace and status behavior

**Files:**
- Modify: `tests/test_supervisor.py`
- Modify: `tests/test_supervisor_e2e.py`
- Read: `src/agents/supervisor.py`

**Step 1: Write the failing test for 6-node happy-path trace preservation**

```python
def test_upload_happy_path_preserves_6_node_completion_and_trace():
    ...
    assert result["processing_steps"]["classification"]["status"] == "COMPLETED"
    assert result["processing_steps"]["adjudication"]["status"] == "COMPLETED"
```

Add one assertion that the acquisition trace additions do not remove the final completed state.

**Step 2: Write the failing test for source-based routing with `web`**

Assert that a `source="web"` state still compiles and finishes the acquisition path correctly when patched nodes succeed.

**Step 3: Run tests to verify failure**

Run: `uv run pytest -q tests/test_supervisor.py tests/test_supervisor_e2e.py`
Expected: At least one FAIL once new assertions are added.

**Step 4: Commit**

Do not commit unless explicitly requested by the user.

---

### Task 6: Implement supervisor compatibility fixes for the rollout

**Files:**
- Modify: `src/agents/supervisor.py`
- Test: `tests/test_supervisor.py`
- Test: `tests/test_supervisor_e2e.py`

**Step 1: Keep the graph order unchanged**

Do not add or remove nodes. The rollout must still compile with:
1. `interaction`
2. `acquisition`
3. `parsing`
4. `translation`
5. `extraction`
6. `reasoning`
7. `arbitration`

**Step 2: Normalize completed step output**

Ensure the finalize path still marks classification and adjudication as completed even when acquisition trace data becomes richer.

**Step 3: Run focused tests**

Run: `uv run pytest -q tests/test_supervisor.py tests/test_supervisor_e2e.py`
Expected: PASS.

**Step 4: Commit**

Do not commit unless explicitly requested by the user.

---

### Task 7: Run focused regression suite and update rollout docs

**Files:**
- Modify: `docs/plans/2026-03-22-v1.0-multi-source-6node-rollout.md`
- Modify: `progress.txt`
- Modify: `lesson.md`
- Test: `tests/test_literature_unified_workflow.py`
- Test: `tests/unit/test_unified_source_selection_and_trace.py`
- Test: `tests/test_agents_acquisition.py`
- Test: `tests/test_supervisor.py`
- Test: `tests/test_supervisor_e2e.py`

**Step 1: Update the baseline rollout doc**

Make the old high-level plan point to this implementation plan and summarize what was actually shipped.

**Step 2: Run the focused regression suite**

Run:
`uv run pytest -q tests/test_literature_unified_workflow.py tests/unit/test_unified_source_selection_and_trace.py tests/test_agents_acquisition.py tests/test_supervisor.py tests/test_supervisor_e2e.py`

Expected: PASS.

**Step 3: Record the milestone**

Add one entry to `progress.txt` for the multi-source + 6-node rollout slice and one debugging note to `lesson.md` if any issue was discovered during the rollout.

**Step 4: Commit**

Do not commit unless explicitly requested by the user.
