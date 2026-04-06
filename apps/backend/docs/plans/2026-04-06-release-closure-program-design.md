# Release Closure Program Design

> **Status:** `EXECUTED THROUGH TASK 13; FINAL CLOSEOUT PENDING`
> **Scope:** Complete the final release closeout after Tasks `1-13` landed on `yangzs-agents`.
> **Frozen Contract Sources:** `docs/PRD.md`, `docs/BACKEND_STRUCTURE.md`, `docs/APP_FLOW.md`, `docs/TECH_STACK.md`, `docs/IMPLEMENTATION_PLAN.md`

## Goal
Close the remaining release gate in an order that reflects the verified branch state:
1. lock the fixed 100-paper manifest
2. execute the acceptance set and publish the final release report
3. run the final verification sweep and record closeout

## Problem Statement
The current branch already contains:
1. the 6-node main workflow
2. multi-source acquisition routing
3. M2 task-creation slice
4. `warning_codes` / `trace_chain` exposure
5. release-gate calculation and report tooling
6. KG outbox / consumer / backfill code paths
7. multi-variant graph fan-out persistence
8. request monitor / document / export frontend surfaces
9. repo-wide release-critical quality cleanup

But the branch is still not release-complete because:
1. `docs/acceptance/v1.0-100-paper-manifest.json` is still a scaffold instead of the locked per-release acceptance set
2. the real 100-paper acceptance run has not been executed
3. the final release report has not been published from actual acceptance results
4. the final verification sweep has not yet been recorded after the real acceptance run

## Chosen Approach
Use a narrow final-closeout sequence:

1. lock the real 100-paper manifest and mark it `locked=true`
2. run the acceptance set and sync actual paper results back into the manifest
3. render the final release report from the actual manifest state
4. re-run the final backend/frontend/static verification sweep
5. update tracking docs with the honest final closeout status

The five-phase closure program below is retained as historical execution provenance for the already-landed Tasks `1-13`.

## Non-Goals
This program does not:
1. redefine frozen statuses, error codes, retry policies, or retention rules
2. move KG logic back into the main service runtime path
3. introduce a new PDF rendering backend during release closeout
4. change request-level aggregation semantics for multi-variant papers
5. hide historical lint/type debt with broad ignores

## Architecture

Historical execution provenance for the already-landed slices:

### Phase A: Release Closeout Baseline `Status: Landed on current branch`
This phase is documentation and verification only.

Allowed work:
1. `docs/plans/`
2. `progress.txt`
3. `lesson.md`
4. release-facing documentation
5. focused regression tests that explain the current branch state

Not allowed:
1. shipping new business behavior
2. mixing KG or frontend feature work into the closeout pass

Outcome:
1. one clear description of what is already done on `yangzs-agents`
2. one clear description of what is still pending
3. fresh focused regression evidence for the merged branch

### Phase B: KG Independent Service `Status: Landed on current branch`
Implement the frozen KG boundary from the docs:
1. main service persists structured evidence in PostgreSQL
2. main service emits a KG event trigger
3. KG service reads from PostgreSQL
4. KG service updates Neo4j
5. initial full backfill supports resume from checkpoint

#### Event model
Use a small event payload with stable identifiers only:
1. `event_id`
2. idempotency key
3. `request_id`
4. `paper_task_id`
5. `document_id`
6. `release_no`
7. event timestamp

Do not transport the full evidence payload through Celery.

#### Recommended execution shape
1. main service writes an outbox/event row in PostgreSQL
2. main service enqueues a lightweight Celery trigger carrying the event reference
3. KG consumer loads the event row and evidence rows from PostgreSQL
4. KG consumer runs graph sync to Neo4j
5. retry queue uses the same retry policy as the expert-adjudication contract

#### Why this shape
1. PostgreSQL stays the only KG source of truth
2. incremental update and backfill reuse the same executor
3. broker payload remains small and stable
4. event delivery failures do not erase the fact that the paper already completed successfully

### Phase C: Multi-Variant Evidence Fan-Out `Status: Landed on current branch`
Current problem:
1. a paper with multiple variants is persisted as one merged evidence record
2. Neo4j receives one merged variant representation
3. downstream graph retrieval and ClinVar linking become inaccurate

Chosen fix:
1. keep one top-level `paper_task_id` and one top-level paper success/failure state
2. split normalized variant-level evidence before writing PostgreSQL evidence rows
3. persist one `EvidenceRecord`-equivalent row per normalized variant
4. let KG read those fan-out rows and create Neo4j links per variant

What stays unchanged:
1. request aggregation still works per paper
2. paper-task APIs still return one paper-level object
3. KG still reads from PostgreSQL rather than re-splitting payloads itself

Why PG-first fan-out matters:
If PostgreSQL keeps merged variants while Neo4j stores split variants, the system ends up with two incompatible truths. Fan-out must happen before KG consumption.

### Phase D: Remaining M2 Frontend Surfaces `Status: Landed on current branch`
Complete the frozen M2 user-visible loop by extending the current pages instead of inventing a second UI architecture.

#### Request monitoring
Continue using `RequestMonitorPage` as the request-level status entrypoint.
Extend it to show:
1. 6-node progress
2. `warning_codes`
3. `trace_chain`
4. `source_trace`
5. duplicate/fulltext-unavailable labels
6. request-level summary metrics

#### Reading/results
Continue using `DocumentPage` as the single-paper reading surface.
It should be the place for:
1. original/source text
2. English text
3. evidence anchors
4. trace-aware reading context

#### Export
Continue using `RequestExportPage` for export output.
For release closeout, prefer:
1. HTML export view
2. browser print-to-PDF flow

Do not add a new backend PDF rendering stack in this phase unless the current frontend route proves impossible.

### Phase E: Repo-Wide Quality Cleanup `Status: Landed on current branch`
Use three concentric scopes:

1. **Release-critical scope**
   Files touched by Phases A-D must be clean for `basedpyright` and `ruff`.
2. **Hotspot scope**
   Clean frequently touched backend/frontend entrypoints such as task routes, task manager, config, and request/result pages.
3. **Repo-wide scope**
   Run full-repo `basedpyright` and `ruff`, then fix remaining issues without masking new debt.

Principles:
1. do not change business behavior only to satisfy style rules
2. no broad suppression that hides new issues in touched files
3. prioritize zero new debt on modified code before historical full-repo cleanup

## Data Flow

### Main release path after this program
1. User creates request and selects/uploads papers
2. 6-node workflow completes per paper
3. Variant-level evidence is normalized and persisted in PostgreSQL
4. Main service emits KG event reference
5. KG consumer reads PostgreSQL rows and syncs Neo4j
6. Request monitor and document pages read stable task/result contracts
7. Export page renders a print-ready request report
8. Acceptance runner computes release gate against the fixed manifest and renders the final release report

## Failure Handling

### KG service
1. KG enqueue failure must not roll back an already-successful paper task
2. event rows remain recoverable through retry/backfill
3. consumer retries follow the expert-adjudication retry template
4. failed event processing must be traceable via logs and event status

### Fan-out
1. malformed or unpairable variant fragments must not corrupt other variants from the same paper
2. paper-level task should fail only if the existing graph/persistence contract would already fail that paper
3. partial variant parsing should degrade with warnings only when that is contract-safe

### Frontend
1. `FILE_DUPLICATE` must render as success-path reuse, not failure
2. `fulltext_unavailable` must remain visible
3. export should degrade honestly when required fields are missing instead of fabricating content

## Testing Strategy

### Phase A
1. focused regression suite for merged branch baseline
2. doc-state consistency checks

### Phase B
1. unit tests for outbox/event creation, idempotency, retry state, checkpoint resume
2. integration tests for KG consumer with fake PostgreSQL + fake Neo4j
3. script-level tests for resumable backfill

### Phase C
1. unit tests for multi-variant normalization and pairing rules
2. domain/integration tests proving one paper yields multiple persisted evidence rows
3. compatibility tests proving paper-level API shape remains stable
4. KG tests proving fan-out rows become multiple graph writes

### Phase D
1. route/page tests for monitor, document, and export pages
2. store/service tests for request status and export payload mapping
3. build + lint verification for frontend touched scope

### Phase E
1. targeted `basedpyright` / `ruff` on touched scopes after each phase
2. final full-repo `basedpyright`
3. final full-repo `ruff check`

## Risks
1. KG service and graph fan-out both touch the same data contract; sequencing mistakes can create split truth between PostgreSQL and Neo4j
2. full acceptance should not be run until Phase A-D are stable, otherwise the report becomes stale immediately
3. repo-wide lint/type cleanup can easily balloon in scope if not constrained to release-critical and hotspot passes first

## Recommended Execution Order
1. Phase A: release closeout baseline
2. Phase B: KG independent service
3. Phase C: multi-variant fan-out
4. Phase D: remaining M2 frontend surfaces
5. Phase E: repo-wide quality cleanup
6. Real 100-paper acceptance execution and final release report

## Approval Record
Validated interactively on 2026-04-06:
1. priority order `1` selected: release closure first, frontend after backend data contract
2. A-C architecture approved
3. D-E frontend and quality-cleanup design approved
