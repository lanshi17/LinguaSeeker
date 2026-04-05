# M2 Task Creation Flow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the M2 single-page task creation flow so users can clarify fuzzy intent, confirm a persisted task sheet, and then either upload literature or continue to candidate retrieval.

**Architecture:** Add a dedicated pre-execution task-creation surface that separates clarification, confirmation, and branch submission into explicit actions. Implement in small TDD increments so the request draft lifecycle is stable before wiring upload and candidate-routing behavior.

**Tech Stack:** FastAPI backend, existing ACMG-Lingua request/task services, Pydantic DTOs, pytest, frontend task-creation UI in the existing frontend stack, repository docs under `docs/`.

---

### Task 1: Audit existing task-creation surfaces and choose extension points

**Files:**
- Read: `docs/PRD.md`
- Read: `docs/APP_FLOW.md`
- Read: `docs/FRONTEND_GUIDELINES.md`
- Read: `docs/IMPLEMENTATION_PLAN.md`
- Read: `main.py`
- Read: `src/`
- Test: existing request/task API tests under `tests/`

**Step 1: Identify current request-creation endpoints and DTOs**
- Find exact files that currently create `request_id`, accept uploads, or represent request/task payloads.
- Write down the exact extension points before changing code.

**Step 2: Identify current frontend or presentation entry points**
- Find the page/module/component that should host the single-page task creation flow.
- If no current frontend module exists here, document the exact new file path that will be created.

**Step 3: Record the minimal slice boundary**
- Confirm this implementation only covers:
  - clarification
  - task-sheet confirmation
  - upload branch
  - fetch-candidate branch handoff
- Explicitly exclude later M2 slices from code changes.

**Step 4: Verify with focused discovery notes**
Run the smallest relevant inspection commands/tests needed to prove the target files are the correct integration points.

**Step 5: Commit**
Do not commit unless explicitly requested by the user.

---

### Task 2: Add failing backend tests for clarification contract

**Files:**
- Create/Modify: exact backend request/task API test file once identified from Task 1
- Modify: exact clarification/request DTO module once identified from Task 1
- Modify: exact route/service module once identified from Task 1

**Step 1: Write failing test for `needs_clarification` response**
Example shape:
```python
def test_task_creation_clarification_returns_follow_up_question(client):
    response = client.post("/api/.../clarify", json={"message": "Find PS3 evidence for ..."})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "needs_clarification"
    assert payload["question"]
```

**Step 2: Run test to verify it fails**
Run: `uv run pytest -q <exact_test_path>::test_task_creation_clarification_returns_follow_up_question`
Expected: FAIL because endpoint/shape does not yet exist or does not match.

**Step 3: Write failing test for `task_form_ready` after max clarification rounds**
Example shape:
```python
def test_task_creation_after_second_round_returns_task_form(client):
    response = client.post("/api/.../clarify", json={
        "message": "same intent",
        "round": 2,
        "partial_fields": {"goal": "..."}
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "task_form_ready"
    assert payload["request_id"]
    assert payload["task_form_text"]
    assert set(payload["fields"]) >= {"goal", "disease", "country", "language"}
```

**Step 4: Run test to verify it fails**
Run: `uv run pytest -q <exact_test_path>::test_task_creation_after_second_round_returns_task_form`
Expected: FAIL.

**Step 5: Commit**
Do not commit unless explicitly requested by the user.

---

### Task 3: Implement minimal clarification backend contract

**Files:**
- Modify: exact route module discovered in Task 1
- Modify: exact service/orchestration module discovered in Task 1
- Modify: exact DTO/schema module discovered in Task 1
- Test: same backend clarification tests from Task 2

**Step 1: Add request/response DTOs for clarification action**
Include only the minimal fields required:
- user message
- optional session/request identifier
- round count
- partial fields
- outcome status
- question text or task-form payload

**Step 2: Implement max-two-round logic**
- if more clarification is needed and round < 2 -> return `needs_clarification`
- otherwise -> generate task form and inject defaults for missing fields

**Step 3: Persist draft task-sheet text and structured metadata**
- ensure both text and structured fields are stored when task form becomes ready
- ensure `request_id` is created as part of this path if required by current architecture

**Step 4: Run focused tests**
Run: `uv run pytest -q <exact_clarification_test_path>`
Expected: PASS for the new clarification tests.

**Step 5: Commit**
Do not commit unless explicitly requested by the user.

---

### Task 4: Add failing backend tests for task-sheet confirmation

**Files:**
- Modify: same backend API/service test file or a nearby request/task API test file
- Modify: exact confirmation DTO/service/route files identified in Task 1

**Step 1: Write failing test for successful confirmation persistence**
Example shape:
```python
def test_confirm_task_form_persists_final_text_and_fields(client, ready_request_id):
    response = client.post(f"/api/.../{ready_request_id}/confirm", json={
        "task_form_text": "...",
        "fields": {...},
        "confirmed": True,
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == ready_request_id
    assert payload["confirmed"] is True
```

**Step 2: Write failing test for invalid fixed fields**
```python
def test_confirm_task_form_rejects_missing_required_fields(client, ready_request_id):
    response = client.post(f"/api/.../{ready_request_id}/confirm", json={
        "task_form_text": "...",
        "fields": {"goal": "..."},
        "confirmed": True,
    })
    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "INPUT_INVALID"
```

**Step 3: Run tests to verify failure**
Run: `uv run pytest -q <exact_confirmation_test_path>`
Expected: FAIL.

**Step 4: Commit**
Do not commit unless explicitly requested by the user.

---

### Task 5: Implement minimal task-sheet confirmation action

**Files:**
- Modify: exact route/service/DTO modules for confirmation
- Test: confirmation tests from Task 4

**Step 1: Add confirmation request/response DTOs**
- request_id
- final task-form text
- final structured fields
- confirmation flag

**Step 2: Implement validation**
Reject malformed or incomplete fixed fields with `INPUT_INVALID`.

**Step 3: Persist canonical confirmed task sheet**
- keep task-sheet text
- keep structured metadata
- mark request draft as confirmed using the current persistence model

**Step 4: Return branch options cleanly**
Return a stable response that enables:
- upload branch
- fetch-candidates branch

**Step 5: Run focused tests**
Run: `uv run pytest -q <exact_confirmation_test_path>`
Expected: PASS.

**Step 6: Commit**
Do not commit unless explicitly requested by the user.

---

### Task 6: Add failing tests for upload branch constraints and duplicate handling

**Files:**
- Modify: upload/request API tests
- Modify: upload route/service modules

**Step 1: Write failing test for valid upload branch**
Assert confirmed request + valid files transitions into upload-processing path.

**Step 2: Write failing test for file validation**
Cover at least:
- wrong type -> `FILE_TYPE_UNSUPPORTED`
- too large -> `FILE_TOO_LARGE`
- too many files -> request rejected
- total size too large -> request rejected

**Step 3: Write failing test for duplicate semantics**
Assert duplicate upload:
- creates new `paper_task_id`
- returns `duplicate_of`
- indicates success semantics

**Step 4: Run tests to verify failure**
Run: `uv run pytest -q <exact_upload_branch_test_path>`
Expected: FAIL.

**Step 5: Commit**
Do not commit unless explicitly requested by the user.

---

### Task 7: Implement upload branch submission

**Files:**
- Modify: upload/request route module
- Modify: upload service/orchestration module
- Modify: request persistence/service modules if needed
- Test: upload branch tests from Task 6

**Step 1: Accept confirmed task-sheet reference plus file batch**
Do not allow upload before confirmation.

**Step 2: Re-check all upload constraints server-side**
- PDF/DOCX only
- max 10 files
- max 10MB each
- max 50MB total

**Step 3: Route into existing upload-processing path**
Reuse current upload/request code rather than inventing a parallel path.

**Step 4: Preserve duplicate-file behavior**
Do not change the existing `FILE_DUPLICATE` success contract.

**Step 5: Run focused tests**
Run: `uv run pytest -q <exact_upload_branch_test_path>`
Expected: PASS.

**Step 6: Commit**
Do not commit unless explicitly requested by the user.

---

### Task 8: Add failing tests for fetch-candidates branch handoff

**Files:**
- Modify: request/task API test file covering candidate entry
- Modify: route/service modules handling candidate acquisition handoff

**Step 1: Write failing test for confirmed request entering candidate-fetch path**
Assert the confirmed request moves into candidate retrieval rather than upload processing.

**Step 2: Write failing test for invalid branch state**
If branch submission is attempted before confirmation, assert `INPUT_INVALID` or current contract-equivalent rejection.

**Step 3: Run tests to verify failure**
Run: `uv run pytest -q <exact_fetch_branch_test_path>`
Expected: FAIL.

**Step 4: Commit**
Do not commit unless explicitly requested by the user.

---

### Task 9: Implement fetch-candidates branch submission

**Files:**
- Modify: candidate-entry route/service module
- Modify: request lifecycle/persistence module if needed
- Test: fetch-branch tests from Task 8

**Step 1: Accept confirmed task-sheet reference**
Require a confirmed task sheet before entering candidate fetch.

**Step 2: Persist branch choice and route cleanly**
Record that the request enters candidate-acquisition path without starting upload handling.

**Step 3: Preserve downstream invalid-empty-selection behavior**
Do not silently alter the frozen rule that no upload + no later selection becomes `INPUT_INVALID`.

**Step 4: Run focused tests**
Run: `uv run pytest -q <exact_fetch_branch_test_path>`
Expected: PASS.

**Step 5: Commit**
Do not commit unless explicitly requested by the user.

---

### Task 10: Implement frontend single-page task-creation shell

**Files:**
- Create/Modify: exact frontend page/component paths identified in Task 1
- Test: exact frontend interaction test file path identified in Task 1

**Step 1: Write failing frontend test for page structure**
Assert the page renders three zones:
- clarification
- task-sheet confirmation
- branch actions

**Step 2: Run test to verify it fails**
Run the exact frontend test command for the project.
Expected: FAIL.

**Step 3: Add minimal page shell**
Render the three zones without full styling complexity.

**Step 4: Run test to verify it passes**
Run the same focused frontend test.
Expected: PASS.

**Step 5: Commit**
Do not commit unless explicitly requested by the user.

---

### Task 11: Wire frontend clarification and confirmation states

**Files:**
- Modify: frontend task-creation page/component(s)
- Modify: frontend API client/service modules
- Test: frontend interaction test file(s)

**Step 1: Write failing frontend tests for clarification round behavior**
Cover:
- round counter shown
- second round stops further clarification
- defaults appear when task form is auto-generated

**Step 2: Write failing frontend tests for confirmation editing**
Cover:
- generated task-form text is visible
- structured fields are editable
- confirm button enables branch zone

**Step 3: Run tests to verify failure**
Run exact focused frontend tests.
Expected: FAIL.

**Step 4: Implement minimal state handling**
- `clarifying`
- `task_form_ready`
- `task_form_invalid`
- `ready_to_submit`
- `submitting`

**Step 5: Run tests to verify pass**
Run exact focused frontend tests.
Expected: PASS.

**Step 6: Commit**
Do not commit unless explicitly requested by the user.

---

### Task 12: Wire frontend upload/skip branch behavior

**Files:**
- Modify: frontend task-creation page/component(s)
- Modify: upload UI helper/client modules
- Test: frontend branch interaction tests

**Step 1: Write failing tests for upload branch behavior**
Cover:
- valid upload path
- local file validation
- duplicate-result rendering shape

**Step 2: Write failing tests for skip-upload behavior**
Cover:
- fetch-candidates branch submission
- buttons lock during submission
- retry preserves confirmed task form

**Step 3: Run tests to verify failure**
Run exact focused frontend tests.
Expected: FAIL.

**Step 4: Implement minimal branch behavior**
Do not implement candidate page details here; only hand off correctly.

**Step 5: Run tests to verify pass**
Run exact focused frontend tests.
Expected: PASS.

**Step 6: Commit**
Do not commit unless explicitly requested by the user.

---

### Task 13: Run backend verification for the full M2 task-creation slice

**Files:**
- Test: all touched backend tests
- Verify: touched backend files with diagnostics

**Step 1: Run diagnostics on all changed backend files**
Use `lsp_diagnostics` on each changed backend file.
Expected: clean error diagnostics.

**Step 2: Run focused backend tests for this slice**
Run the exact set of request/task/upload/candidate tests touched above.
Expected: PASS.

**Step 3: Run broader regression slice**
Run the closest relevant integration/unit regression slice for request creation and upload handling.
Expected: PASS or documented unrelated pre-existing failures.

**Step 4: Commit**
Do not commit unless explicitly requested by the user.

---

### Task 14: Run frontend verification for the task-creation page

**Files:**
- Test: all touched frontend tests
- Verify: touched frontend files with diagnostics/build checks appropriate to the stack

**Step 1: Run diagnostics on changed frontend files**
Use the repo’s standard diagnostics/build mechanism.
Expected: clean results for touched files.

**Step 2: Run focused frontend tests**
Run the task-creation page/component tests.
Expected: PASS.

**Step 3: Run one broader frontend regression slice if available**
Choose the smallest broader suite that exercises routing/state around this page.
Expected: PASS or documented unrelated failures.

**Step 4: Commit**
Do not commit unless explicitly requested by the user.

---

### Task 15: Update project progress and handoff notes

**Files:**
- Modify: `progress.txt`
- Optionally modify: `lesson.md` if debugging/troubleshooting occurred during implementation

**Step 1: Append a milestone entry to `progress.txt`**
Record:
- what part of M2 was implemented
- which tests passed
- any remaining blockers intentionally left out of scope

**Step 2: If debugging was substantial, update `lesson.md`**
Capture root cause and verified fix pattern.

**Step 3: Run final verification commands again**
Re-run the exact final verification commands you cite in the progress update.
Expected: same successful result.

**Step 4: Commit**
Do not commit unless explicitly requested by the user.
