# Backend 6-Node Contract Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the backend cleanup so every user-visible `processing_steps` payload exposes the v1 six-node contract and never includes `reasoning`.

**Architecture:** Keep the supervisor graph topology unchanged so the internal `reasoning` node can still run between `extraction` and `arbitration`. Narrow only the public processing-step contract by removing `reasoning` from normalization/finalization output and updating regression tests to lock that boundary.

**Tech Stack:** Python, FastAPI-adjacent backend services, LangGraph supervisor pipeline, pytest, JSON fixtures under `tests/fixtures`, design/plan docs under `docs/plans`.

---

### Task 1: Lock the six-node contract with failing regression tests

**Files:**
- Modify: `tests/test_supervisor_e2e.py:78-125`
- Modify: `tests/test_state_transitions.py:61-132`
- Modify: `tests/test_golden_fixtures.py:122-137`
- Test: `tests/test_supervisor_e2e.py`
- Test: `tests/test_state_transitions.py`
- Test: `tests/test_golden_fixtures.py`

**Step 1: Write the failing test updates in supervisor end-to-end coverage**

Replace the happy-path assertions so they require `reasoning` to be absent while `classification` and `adjudication` remain completed.

```python
assert "reasoning" not in result["processing_steps"]
assert result["processing_steps"]["classification"]["status"] == "COMPLETED"
assert result["processing_steps"]["adjudication"]["status"] == "COMPLETED"
```

Apply this to both:
- `TestHappyPaths.test_upload_happy_path`
- `TestHappyPaths.test_web_happy_path`

**Step 2: Strengthen the state-transition regression**

Add a focused normalization assertion proving legacy `reasoning` input is ignored.

```python
def test_normalize_processing_steps_drops_legacy_reasoning_entry(self) -> None:
    normalized = normalize_processing_steps(
        {
            "reasoning": {"status": "COMPLETED"},
            "classification": {"status": "RUNNING"},
        }
    )

    assert "reasoning" not in normalized
    assert normalized["classification"]["status"] == ProcessingStepStatus.running.value
```

**Step 3: Keep the golden-fixture assertion explicit**

Retain the existing six-node assertions in `tests/test_golden_fixtures.py` so fixture validation remains a contract lock.

**Step 4: Run the focused supervisor test to verify RED**

Run:
```bash
uv run pytest -q tests/test_supervisor_e2e.py
```

Expected: FAIL because `src/agents/supervisor.py` still writes `processing_steps["reasoning"]` during `finalize()`.

**Step 5: Run the helper and fixture tests to verify current baseline**

Run:
```bash
uv run pytest -q tests/test_state_transitions.py tests/test_golden_fixtures.py
```

Expected: either PASS already or fail only if the new normalization assertion exposes another lingering contract leak.

**Step 6: Commit**

```bash
git add tests/test_supervisor_e2e.py tests/test_state_transitions.py tests/test_golden_fixtures.py
git commit -m "test: lock six-node processing contract"
```

Do not commit unless explicitly requested by the user.

---

### Task 2: Remove `reasoning` from supervisor finalization output

**Files:**
- Modify: `src/agents/supervisor.py:129-155`
- Test: `tests/test_supervisor_e2e.py`

**Step 1: Write the minimal implementation change**

Delete the `reasoning` `_mark_step(...)` block from `finalize()` and leave only the public contract steps.

Target shape:

```python
def finalize(state: SupervisorState) -> SupervisorState:
    updated = dict(state)
    _mark_step(
        updated,
        step="classification",
        status=ProcessingStepStatus.completed,
        message="Classification completed",
        node_name="acmg",
    )
    _mark_step(
        updated,
        step="adjudication",
        status=ProcessingStepStatus.completed,
        message="Adjudication completed",
        node_name="arbitration",
    )
    _finalize_processing_steps(updated)
    updated["current_node"] = "finalize"
    updated["workflow_status"] = "completed"
    return cast(SupervisorState, cast(object, updated))
```

**Step 2: Run the supervisor test to verify GREEN**

Run:
```bash
uv run pytest -q tests/test_supervisor_e2e.py
```

Expected: PASS with both happy-path tests confirming that `reasoning` is absent from `processing_steps`.

**Step 3: Run the helper regression to ensure no new workflow-state breakage**

Run:
```bash
uv run pytest -q tests/test_supervisor.py
```

Expected: PASS.

**Step 4: Commit**

```bash
git add src/agents/supervisor.py tests/test_supervisor_e2e.py tests/test_supervisor.py
git commit -m "fix: stop exposing reasoning in processing steps"
```

Do not commit unless explicitly requested by the user.

---

### Task 3: Prove normalization drops legacy `reasoning` payloads

**Files:**
- Modify: `tests/test_state_transitions.py:119-132`
- Test: `tests/test_state_transitions.py`
- Read/Verify: `src/services/enum.py:185-224`

**Step 1: Verify the normalization path relies on `PROCESSING_NODE_TO_STEP` membership**

Confirm that `normalize_processing_steps()` only accepts steps that map into `default_processing_steps()`:

```python
step = PROCESSING_NODE_TO_STEP.get(str(raw_key).lower(), str(raw_key).lower())
if step not in normalized:
    continue
```

This is the mechanism that should already drop `reasoning` once the mapping is removed.

**Step 2: Add the focused regression if it does not exist yet**

```python
def test_normalize_processing_steps_drops_legacy_reasoning_entry(self) -> None:
    normalized = normalize_processing_steps(
        {
            "reasoning": {
                "status": "COMPLETED",
                "updated_at": "2026-03-30T00:00:00+00:00",
                "message": "Legacy reasoning step",
                "error_code": None,
            },
            "classification": {"status": "RUNNING"},
        }
    )

    assert set(normalized) == set(PROCESSING_STEP_ORDER)
    assert "reasoning" not in normalized
    assert normalized["classification"]["status"] == ProcessingStepStatus.running.value
```

**Step 3: Run the focused normalization test**

Run:
```bash
uv run pytest -q tests/test_state_transitions.py::TestProcessingStepTransitions::test_normalize_processing_steps_drops_legacy_reasoning_entry
```

Expected: PASS.

**Step 4: Run the full transition test module**

Run:
```bash
uv run pytest -q tests/test_state_transitions.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_state_transitions.py src/services/enum.py
git commit -m "test: verify legacy reasoning step is ignored"
```

Do not commit unless explicitly requested by the user.

---

### Task 4: Validate the golden fixture against the narrowed contract

**Files:**
- Modify: `tests/fixtures/golden_processing_state.json:240-262`
- Modify: `tests/test_golden_fixtures.py:122-137`
- Test: `tests/test_golden_fixtures.py`

**Step 1: Keep the fixture at exactly six processing steps**

The fixture should contain only:
- `acquisition`
- `parsing`
- `translation`
- `extraction`
- `classification`
- `adjudication`

The current desired JSON shape is:

```json
"processing_steps": {
  "acquisition": {"status": "SKIPPED", "updated_at": "...", "message": "Acquisition skipped due to duplicate upload", "error_code": null},
  "parsing": {"status": "COMPLETED", "updated_at": "...", "message": "PDF parsed", "error_code": null},
  "translation": {"status": "SKIPPED", "updated_at": "...", "message": "English source detected", "error_code": null},
  "extraction": {"status": "COMPLETED", "updated_at": "...", "message": "Evidence extracted", "error_code": null},
  "classification": {"status": "COMPLETED", "updated_at": "...", "message": "Evidence classified", "error_code": null},
  "adjudication": {"status": "COMPLETED", "updated_at": "...", "message": "Adjudication approved", "error_code": null}
}
```

**Step 2: Keep the fixture test explicit**

Ensure the fixture test still asserts:

```python
assert set(data["processing_steps"]) == set(PROCESSING_STEP_ORDER)
assert "reasoning" not in data["processing_steps"]
```

**Step 3: Run the golden fixture tests**

Run:
```bash
uv run pytest -q tests/test_golden_fixtures.py
```

Expected: PASS.

**Step 4: Commit**

```bash
git add tests/fixtures/golden_processing_state.json tests/test_golden_fixtures.py
git commit -m "test: align golden processing fixture with six-node contract"
```

Do not commit unless explicitly requested by the user.

---

### Task 5: Run the touched backend suite and inspect the final diff

**Files:**
- Modify: `src/agents/supervisor.py`
- Modify: `src/services/enum.py`
- Modify: `tests/test_supervisor_e2e.py`
- Modify: `tests/test_state_transitions.py`
- Modify: `tests/test_golden_fixtures.py`
- Modify: `tests/fixtures/golden_processing_state.json`

**Step 1: Run the focused touched suite together**

Run:
```bash
uv run pytest -q tests/test_supervisor_e2e.py tests/test_state_transitions.py tests/test_golden_fixtures.py
```

Expected: PASS.

**Step 2: If any failure mentions workflow helpers, run the nearby supervisor stream test**

Run:
```bash
uv run pytest -q tests/test_stream_supervisor.py
```

Expected: PASS. This confirms internal progress-node logging still works even though `reasoning` is no longer public in `processing_steps`.

**Step 3: Inspect the diff for scope control**

Run:
```bash
git diff -- src/agents/supervisor.py src/services/enum.py tests/test_supervisor_e2e.py tests/test_state_transitions.py tests/test_golden_fixtures.py tests/fixtures/golden_processing_state.json
```

Expected: only the six-node contract cleanup changes appear.

**Step 4: Commit**

```bash
git add src/agents/supervisor.py src/services/enum.py tests/test_supervisor_e2e.py tests/test_state_transitions.py tests/test_golden_fixtures.py tests/fixtures/golden_processing_state.json
git commit -m "fix: finalize six-node processing contract cleanup"
```

Do not commit unless explicitly requested by the user.
