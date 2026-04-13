# Acceptance Closeout Design

> **Status:** `EXECUTED`
> **Scope:** Complete `Task 14` and `Task 15` for the `v1.0` release closeout on `yangzs-agents`.
> **Frozen Contract Sources:** `docs/PRD.md`, `docs/BACKEND_STRUCTURE.md`, `docs/APP_FLOW.md`, `docs/TECH_STACK.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/plans/2026-04-06-release-closure-program-design.md`, `docs/plans/2026-04-06-release-closure-program-implementation.md`

## Goal
Turn the remaining release closeout into an executable mixed-source acceptance flow:
1. lock the real 100-paper manifest
2. enqueue the acceptance set through real repository code paths
3. sync actual paper-task results back into the manifest
4. render the final release report
5. run the final verification sweep

## Current Branch Reality
The current branch already contains:
1. KG outbox / consumer / backfill code paths
2. multi-variant graph fan-out persistence
3. request monitor / document / export frontend surfaces
4. acceptance summary and report rendering helpers
5. passing focused backend/frontend/static verification slices

The branch is no longer blocked on acceptance execution. This closeout slice has been executed:
1. 100-paper manifest is locked and executable
2. acceptance set has been run and synced
3. final release report has been published
4. final verification sweep has been executed

The remaining release concern is gate follow-up (`DURATION_SLA_BREACHED`), not Task 14/15 executability.

## Constraints
1. The real HTTP/API product surface for this slice is treated as two entry kinds only:
   - `api`
   - `web`
2. The acceptance set will be mixed-source:
   - `api` about `0.7`
   - `web` about `0.2`
   - `pubmed` about `0.1`, but represented as `entry_kind="api"` with `source="pubmed"`
3. The acceptance executor should run inside the repository by calling current route/service code directly, not by going out through HTTP.
4. The manifest schema may be extended.
5. `Task 15` should remain a verification-only closeout step after the real acceptance run completes.

## Options Considered
### Option 1: Internal mixed-source executor over current route/service layer
Add an internal acceptance executor that reads the manifest, dispatches by `entry_kind`, reuses existing `web` and `pubmed` submit flows where available, and adds one minimal internal submit path for the remaining `api` providers.

Pros:
1. smallest surface-area change that produces a real acceptance run
2. preserves current external API surface
3. keeps `Task 15` verification commands largely unchanged

Cons:
1. introduces an acceptance-specific orchestration layer
2. still requires one new internal `api` submit path

### Option 2: Add a new public `/requests/api/submit` route
Expose a full public `api` submit route and make the acceptance runner call route functions only.

Pros:
1. cleaner user-facing symmetry with current `web` flow
2. easier to reuse outside acceptance

Cons:
1. expands release closeout into a product/API change
2. larger regression surface than needed

### Option 3: Create a fully generic request-orchestration service
Abstract all request creation paths behind one new service and migrate `web`, `pubmed`, and new `api` submission to it.

Pros:
1. best long-term architecture
2. single orchestration surface

Cons:
1. too large for release closeout
2. high risk of unintended churn in already-landed flows

## Chosen Approach
Use Option 1.

This keeps the external product surface stable and focuses only on the minimum code needed to make `Task 14` real. The acceptance executor becomes an internal release tool, not a new public API. Existing `web` and `pubmed` code paths are reused where possible; only the missing non-`pubmed` `api` path is added.

## Manifest Model
The manifest remains the release source of truth, but each paper entry becomes both:
1. an execution instruction
2. a result-tracking record

### Manifest-level fields
Keep:
1. `release_no`
2. `expected_paper_count`
3. `locked`
4. `generated_at`
5. `notes`

### Paper-level fields
Keep:
1. `paper_id`
2. `paper_task_id`
3. `status`
4. `error_code`
5. `duration_seconds`
6. `worker_started_at`
7. `completed_at`
8. `title`
9. `notes`

Add:
1. `entry_kind`: `api | web`
2. `source`: concrete provider or source bucket, for example `pubmed`, `pmc`, `crossref`, `doaj`, `jstage`, `unpaywall`, `web`
3. `request_payload`: normalized execution input
4. `request_id`: optional request UUID written back after enqueue

### Example paper record
```json
{
  "paper_id": "v1.0-api-001",
  "entry_kind": "api",
  "source": "pmc",
  "request_payload": {
    "task_form": "{\"goal\":\"PS3/BS3 evidence\",\"disease\":\"...\",\"country\":\"US\",\"language\":\"EN\"}",
    "query": "BARD1 hereditary breast cancer",
    "identifiers": ["PMCID:PMC1234567"],
    "selected_title": "Functional analysis of ...",
    "detail_link": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/"
  },
  "request_id": null,
  "paper_task_id": null,
  "status": "queued",
  "error_code": null,
  "duration_seconds": null,
  "worker_started_at": null,
  "completed_at": null,
  "title": "Functional analysis of ...",
  "notes": null
}
```

## Execution Architecture
### 1. Acceptance executor
Add an internal executor service, for example `src/services/acceptance_executor.py`.

Responsibilities:
1. validate one manifest paper entry
2. dispatch by `entry_kind` and `source`
3. call the correct current route/service code path
4. return real `request_id` and `paper_task_id`
5. let `run_acceptance_set.py` write those ids back into the manifest

### 2. `web` execution path
Reuse the existing web request creation flow by calling `create_task_request_by_web_crawl(...)` directly.

Expected `request_payload` fields:
1. `task_form`
2. `source="web"`
3. `urls`
4. `force_refresh` when needed

### 3. `api` execution path
The `api` bucket splits internally by provider:
1. `source="pubmed"` reuses the existing PubMed submit flow
2. all other `api` providers use one new internal submit helper

#### Why `pubmed` stays inside `api`
The acceptance surface only distinguishes `api` and `web`, but `pubmed` already has a stable request creation flow in the repo. Treating it as `entry_kind="api"` plus `source="pubmed"` keeps the manifest aligned with the real acceptance mix while still reusing the best existing code path.

### 4. New internal non-`pubmed` `api` submit helper
Add one internal helper, for example `submit_api_acceptance_item(...)`, responsible for:
1. creating `task_request`
2. creating `document`
3. creating `paper_task`
4. writing request/document metadata that preserves the real provider
5. enqueueing one new Celery task, `process_api_paper_task`

This helper is intentionally internal-only. It does not create a new public route.

### 5. New `process_api_paper_task`
Add one new Celery task in `src/services/task_manager.py`.

Execution outline:
1. acquisition:
   - call `literature_unified_workflow(...)`
   - force `prefer="api"`
   - set `api_provider=source`
   - persist `source_trace`
2. if a full-text PDF is available:
   - continue through parsing -> translation -> extraction -> acmg using current shared helpers
3. if full text is unavailable but metadata/abstract evidence is available:
   - continue through the same fallback pattern used by the current PubMed direct path
   - set `fulltext_unavailable=true`
4. on success:
   - persist status, `warning_codes`, `trace_chain`
   - emit KG outbox event
5. on terminal failure:
   - persist frozen `error_code`

## Result Sync Model
`scripts/sync_acceptance_manifest.py` should continue to sync by `paper_task_id`.

This means:
1. `run_acceptance_set.py` must write the real `paper_task_id` back to each manifest row
2. `sync_manifest_from_postgres(...)` can keep using `get_paper_task(...)` when `paper_task_id` exists
3. a dedicated `get_acceptance_result_by_paper_id(...)` implementation is optional, not required for the first honest run

## Failure Handling
1. one acceptance paper failing to enqueue must not abort the whole run
2. enqueue failures should be written back to the manifest honestly
3. manifest sync should overwrite result fields only from actual PostgreSQL task state
4. release report rendering should never invent success or completion

## Task 14 Done Criteria
`Task 14` is complete only when:
1. `docs/acceptance/v1.0-100-paper-manifest.json` contains exactly `100` locked records
2. every record has `entry_kind`, `source`, and `request_payload`
3. `scripts/run_acceptance_set.py --write` writes back real `request_id` / `paper_task_id` values or explicit failures
4. `scripts/sync_acceptance_manifest.py --write` refreshes actual results for all executable rows
5. `docs/release/v1.0-release-report.md` is rendered from the real manifest state

## Task 15 Done Criteria
`Task 15` is complete only when:
1. the backend focused release suite passes
2. the frontend test/build/lint slice passes
3. `basedpyright src/` passes
4. `ruff check src/ tests/` passes
5. release artifacts exist on disk
6. `progress.txt` records the final closeout
7. `lesson.md` is updated only if the real run uncovers a new debugging root cause

## Testing Strategy
1. unit tests for manifest schema extension
2. unit tests for acceptance executor dispatch
3. unit tests for the internal non-`pubmed` `api` submit helper
4. task tests for `process_api_paper_task`
5. regression tests for acceptance sync/report helpers
6. final `Task 15` verification commands run only after the real acceptance manifest is executed

## Non-Goals
1. no new public `/requests/api/...` route in this slice
2. no redesign of the already-landed `web` or `pubmed` product surface
3. no new PDF rendering backend
4. no attempt to hide an incomplete acceptance run behind synthetic results

## Risks
1. mixed-source manifest normalization can drift if `request_payload` is underspecified
2. non-`pubmed` `api` providers may vary in metadata/fulltext availability, so fallback handling must stay honest
3. acceptance runner correctness depends on writing back real `paper_task_id` values, not placeholders

## Recommended Execution Order
1. extend manifest schema for executable records
2. add the acceptance executor and real `run_acceptance_set.py` wiring
3. reuse `web` and `pubmed` submit paths
4. add the internal non-`pubmed` `api` submit/helper + Celery task
5. lock the real 100-paper manifest
6. execute `Task 14`
7. execute `Task 15`
