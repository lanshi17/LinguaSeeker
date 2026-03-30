# M2 Task Creation Flow Design

## Goal
Design the M2 entry flow for ACMG-Lingua so users can turn fuzzy intent into a persisted task sheet, confirm structured task fields, and then either upload literature directly or continue into candidate retrieval.

## Scope
This design covers only the M2 **task creation flow**:
- interactive clarification
- task-sheet generation and confirmation
- upload vs skip-upload branching
- validation, persistence, and error-handling behavior

Out of scope for this document:
- candidate list page details
- request monitoring page details
- results page details
- PDF export details
- KG/M3 behavior
- M4 acceptance instrumentation

## Frozen Constraints from Product Docs
The design follows these frozen requirements:
- clarification rounds: maximum 2
- fixed task-sheet fields: `目标` / `疾病` / `国家` / `语种`
- task-sheet text and structured metadata must both be persisted
- user may upload PDF/DOCX and skip literature acquisition
- upload limits:
  - max 10 files
  - max 10MB per file
  - max 50MB total
- if user neither uploads nor later selects candidates, response is `failed + INPUT_INVALID`
- failed API responses follow `status=failed`, `error_code`, `log_link`
- duplicate upload semantics remain success-path behavior with `FILE_DUPLICATE`

## Chosen Approach
Use a **single-page task creation flow** with three vertically ordered zones:
1. Agent clarification zone
2. Task-sheet confirmation zone
3. Entry branch zone (upload now vs fetch candidates)

### Why this approach
This best matches the frozen product narrative:
`模糊输入 -> 最多两轮澄清 -> 任务单确认 -> 上传/跳过分支`

Compared with a wizard flow, it keeps state visible in one place and makes it easier to preserve context across clarification, confirmation, and branching. Compared with a form-first flow, it preserves the PRD requirement that fuzzy intent is first translated by the interaction agent into a task sheet.

## Page Architecture
### 1. Agent clarification zone
A chat-like zone where the user enters fuzzy intent and the interaction agent asks follow-up questions.

Requirements:
- display clarification round count (`1/2`, `2/2`)
- stop clarification after round 2
- if fields are still missing after round 2, inject defaults from the whitelist and produce a task sheet
- preserve conversation history for retry/reload recovery

### 2. Task-sheet confirmation zone
A read-first confirmation area that shows:
- natural-language task-sheet text
- structured fields:
  - `目标`
  - `疾病`
  - `国家`
  - `语种`

Behavior:
- natural-language task-sheet remains visible because it is part of the persisted contract
- structured fields can be edited before confirmation
- defaults are labeled explicitly, for example:
  - `国家：不限（默认）`
  - `语种：auto（默认）`
- confirmation action is explicit: `确认任务单并继续`

### 3. Entry branch zone
After confirmation, exactly two mutually exclusive actions are shown:
- `上传文献并跳过检索`
- `继续检索候选文献`

Rules:
- upload branch skips literature acquisition
- fetch-candidates branch transitions to candidate retrieval flow
- buttons lock during submission to prevent duplicate request creation

## UI State Model
The page should use explicit pre-execution states:
- `clarifying`
- `task_form_ready`
- `task_form_invalid`
- `ready_to_submit`
- `submitting`

Branch outcomes:
- `submitted_with_upload`
- `submitted_without_upload`

After branch submission, normal request runtime states continue under the frozen request contract:
- `queued`
- `running`
- `partial_failed`
- `failed`
- `success`

## Backend/API Contract
The flow should be split into three actions rather than one overloaded endpoint.

### Action 1: Clarification
Purpose: convert fuzzy input into a bounded task sheet within at most two rounds.

Request should include:
- current user utterance
- optional conversation/session identifier
- current clarification round count
- any partial structured task fields already known

Response should return one of two outcomes:

#### `needs_clarification`
- assistant question text
- updated round count
- partial extracted fields

#### `task_form_ready`
- natural-language task-sheet text
- structured fields:
  - `goal`
  - `disease`
  - `country`
  - `language`
- applied-default metadata
- generated `request_id`

Rules:
- maximum clarification rounds is 2
- after round 2, backend must generate a task sheet with defaults where required
- task-sheet text and structured metadata are both persisted

### Action 2: Task-form confirmation
Purpose: accept the reviewed or edited task sheet before branching.

Request should include:
- `request_id`
- final task-sheet text
- final structured fields
- confirmation flag

Response should include:
- confirmed task-sheet payload
- persisted metadata summary
- available branch options (`upload_now`, `fetch_candidates`)

Rules:
- confirmation is required before either branch
- malformed or incomplete fixed fields are rejected with `INPUT_INVALID`
- the confirmed task sheet becomes the canonical request definition

### Action 3A: Upload branch submission
Purpose: user uploads files and skips literature acquisition.

Request should include:
- `request_id`
- confirmed task-sheet reference
- 1..10 files

Validation:
- file types: PDF/DOCX only
- max 10 files
- max 10MB each
- max 50MB total

Response should include:
- created `paper_task_id`s
- duplicate handling metadata if applicable
- next route: request monitoring page

Rule:
- using this branch skips candidate acquisition entirely

### Action 3B: Fetch-candidates branch submission
Purpose: move the confirmed task sheet into candidate acquisition.

Request should include:
- `request_id`
- confirmed task-sheet reference

Response should include:
- candidate fetch initiated or candidate page payload
- next route: candidate selection page

Rule:
- if the user later neither uploads nor selects candidates, failure becomes `failed + INPUT_INVALID`

## Validation and Error Handling
### Frontend validation
Frontend performs early validation for UX, but backend remains source of truth.

Form-level validation:
- all fixed fields must be present by confirmation time
- values may come from user input, agent extraction, or default injection

Upload validation:
- allowed types: PDF/DOCX
- file count: `1..10`
- single file size: `<=10MB`
- total size: `<=50MB`

Display layers:
- field-level errors
- file-level errors
- batch-level errors

### Backend validation
Reject with `INPUT_INVALID` when:
- confirmed task sheet is missing required fields
- user tries to continue with neither uploaded files nor later candidate selection
- clarification payload is structurally invalid
- branch choice conflicts with request state

Reject with specific file codes when:
- too large -> `FILE_TOO_LARGE`
- unsupported type -> `FILE_TYPE_UNSUPPORTED`

### Duplicate file behavior
On global SHA-256 duplicate:
- create a new `paper_task_id`
- set paper status to success
- attach `FILE_DUPLICATE`
- return `duplicate_of`
- skip processing nodes

Frontend should render this as successful reuse, not failure.

### Error contract presentation
All backend failures should preserve the frozen contract:
- `status=failed`
- `error_code`
- `log_link`

Stage-specific UI behavior:
- clarification stage: inline recovery, keep conversation context
- confirmation stage: form-level blocking banner, preserve edits
- upload stage: per-file results (accepted / duplicate reused / rejected)
- branch submission stage: preserve confirmed task sheet and allow retry

## Draft Persistence and Recovery
Persist draft state at these checkpoints:
1. after each clarification response
2. when task sheet becomes ready
3. when task sheet is confirmed
4. when upload or fetch branch is submitted

This supports:
- refresh recovery
- retry without restarting chat
- auditable task-sheet history

## Testing Strategy
### Frontend interaction coverage
Need tests for:
1. clarification happy path
2. default injection after max rounds
3. task-sheet editing before confirmation
4. upload branch success path
5. skip-upload to candidate-fetch path
6. validation failures for missing fields and upload constraints

### Backend/API contract coverage
Need tests for:
1. clarification action returning `needs_clarification`
2. clarification action returning `task_form_ready`
3. max-two-round enforcement
4. confirmation persistence and `INPUT_INVALID` rejection
5. upload branch validation and duplicate handling
6. fetch-candidates branch request linkage

### Integration coverage
Need end-to-end coverage for:
1. fuzzy intent -> clarify -> confirm -> upload -> request created
2. fuzzy intent -> clarify -> confirm -> fetch candidates
3. duplicate upload -> success semantics
4. no upload + no later selection -> `INPUT_INVALID`

## Implementation Boundaries
### In scope
- clarification UI and state
- task-sheet generation and confirmation
- upload/skip branch entry
- validation and persistence checkpoints
- routing into upload processing or candidate retrieval

### Out of scope
- candidate list page implementation details
- request monitoring page implementation details
- results page implementation details
- PDF export rendering details
- KG service work
- acceptance/reporting work

## Suggested Delivery Increments
1. Clarification + task-sheet generation
2. Task-sheet confirmation + structured editing
3. Upload branch with local validation and duplicate handling
4. Skip-upload branch into candidate acquisition

This keeps the entry orchestration surface stable before expanding into later M2 slices.

## Observability Guidance
Track at least:
- clarification rounds used
- default-injection frequency
- upload-vs-fetch branch split
- validation failure frequency by type
- duplicate-upload frequency

These signals reveal where users struggle and whether the two-round clarification rule is sufficient.

## Completion Criteria for This Slice
This design slice is complete when:
1. page architecture is fixed
2. clarification/confirmation/branch contract is fixed
3. validation and error rules are fixed
4. test strategy is fixed
5. implementation boundaries are explicit

## Approval Outcome
Approved direction: **single-page task creation flow** for M2 task creation, with clarification, task-sheet confirmation, and upload/skip branching as separate but connected product actions.
