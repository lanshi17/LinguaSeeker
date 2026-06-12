# Code Review: Pipeline Correctness Remediation

- **Branch**: `fix/pipeline-correctness-remediation` (vs `origin/dev`)
- **Date**: 2026-06-12
- **Reviewer**: code-review-excellence
- **Scope**: 32 files, +1202 / −187 across 11 commits
- **Plan**: `docs/plans/2026-06-11-pipeline-correctness-remediation.md`

## Summary Decision

🔄 Request changes — six Success Criteria from the plan are not met. Branch should not merge to `dev` as-is.

| Success Criterion (from plan) | Status |
|---|---|
| #1 `GET /runs/{id}/status` never mutates another worker's run | ⚠️ Partially — `get_last_state()` is read-only in `runner.py:113-129`, but `start()` does not write `owner_worker_id` / `heartbeat_at` because the ORM columns do not exist |
| #2 Startup recovery only fails stale runs (`heartbeat_at < now - timeout`) | ❌ Not implemented — no `heartbeat_at` column, no timeout filter |
| #3 Evidence patching preserves `active_payload.group_id` / `value` / `source` / `track` | ❌ Not implemented — `CanonicalEvidencePayload` model and `from_field_payload` projection are absent |
| #4 Expert review can explicitly finalize a run as `completed` | ❌ Not implemented — no `/finalize` route, no `finalize_review` method |
| #5 Phase mode runs only the requested phase and requires prior run for targets 2/3 | ❌ Not implemented — entry point is hard-coded `set_entry_point("phase_1")`; no `processing_run_id` on `PipelineRunRequest` |
| #6 Phase 3 does not set `NO_CANDIDATES` when ambiguous/unmapped entities exist | ❌ Not implemented — line `phase_3_adapter.py:124` still checks `standardized_count == 0` |
| #7 Production cannot start with empty `API_KEY` | ❌ Not implemented — `_build_nested()` has no `is_production and not api_key` guard |
| #8 Backend and frontend status/auth contracts match | ⚠️ Unverified — frontend diff not reviewed |

## Findings

### 🔴 [blocking] Database migration and ORM lease columns missing (Task 2)

**Files**: `backend/database/migrations/versions/2026-06-11_add_pipeline_run_leases.py`, `backend/src/dao/postgresql/models.py`

Plan Step 3 of Task 2 requires a new Alembic migration adding `source_key`, `owner_worker_id`, `heartbeat_at` columns and two indexes (`ix_pipeline_run_states_owner_heartbeat`, `ux_pipeline_run_states_active_source_key`).

Actual state (`ls database/migrations/versions/`): the lease migration file does not exist. `alembic heads` returns `2026_06_11_allow_standalone_chat_sessions`. `PipelineRunState` (models.py:623-664) has none of the three columns. `state_persistence.py` writes no lease fields.

Impact: Tasks 3, 4, 5 all reference `source_key` / `owner_worker_id` / `heartbeat_at`. Without the schema change, those code paths are no-ops at the database layer. The duplicate-source race guard cannot function; the stale-heartbeat recovery cannot function. The two P0 multi-worker bugs the plan claims to fix are not actually fixed.

Fix: Add `database/migrations/versions/2026-06-11_add_pipeline_run_leases.py` per plan spec; add the three columns and two indexes to `PipelineRunState`; thread `owner_worker_id` / `heartbeat_at` into `SessionBoundStatePersistence.save()`. Update `test_alembic_migration.py` head assertion.

### 🔴 [blocking] Phase 3 skip semantics unchanged (Task 7)

**File**: `backend/src/agents/phase_3_adapter.py:124`

```python
if standardization_result.standardized_count == 0:
    state.skip_phase_3_reason = SkipPhase3Reason.NO_CANDIDATES
```

Plan Task 7 requires:
```python
candidate_count = (
    standardization_result.standardized_count
    + standardization_result.ambiguous_count
    + standardization_result.unmapped_count
)
if candidate_count == 0:
    state.skip_phase_3_reason = SkipPhase3Reason.NO_CANDIDATES
```

Actual code still uses `standardized_count == 0` alone. When standardization yields 1 ambiguous or 1 unmapped entity with 0 standardized, the run is incorrectly marked `NO_CANDIDATES`. The two new tests in the plan (`test_phase_3_does_not_skip_when_ambiguous_entities_exist`, `test_phase_3_does_not_skip_when_unmapped_entities_exist`) would fail.

Impact: Success Criterion #6 unmet. Ambiguous/unmapped candidates are silently lost from Phase 4 review — the exact data-loss class the plan targets.

Fix: Replace the single-counter check with the total-candidate count per plan Task 7 Step 3. Update the `summary` dict to include `ambiguous_count` and `unmapped_count` per plan.

### 🔴 [blocking] Pipeline finalize endpoint and state machine missing (Task 5, Step 5)

**Files**: `backend/src/api/v1/pipeline.py`, `backend/src/agents/runner.py`, `backend/src/agents/state_persistence.py`

Plan requires:
- `POST /api/v1/pipeline/runs/{id}/finalize` route
- `PipelineFinalizeResponse` model
- `PipelineRunner.finalize_review(processing_run_id) -> PipelineGraphState | None`
- `SessionBoundStatePersistence.finalize_review(...)`
- `AWAITING_REVIEW → COMPLETED` transition with idempotent route-level guard

`grep` against the diff shows none of these exist. `src/api/v1/pipeline.py` only exposes `/run` and `/runs/{id}/status`. `runner.py` has no `finalize_review` method.

Impact: Success Criterion #4 unmet. Reviewers have no way to mark a run as completed — the pipeline stays in `AWAITING_REVIEW` forever, blocking downstream reporting and re-run cleanup.

Fix: Implement the route, the runner method, and the persistence method per plan Task 5 Step 5. The route must reject non-`AWAITING_REVIEW` runs with 409 and treat already-`COMPLETED` runs as idempotent.

### 🔴 [blocking] Single-phase mode entry point and rerun path missing (Task 5, Steps 3+4)

**File**: `backend/src/agents/orchestrator.py:181-207`, `backend/src/api/v1/pipeline.py:37-78`

Plan requires:
- `set_conditional_entry_point(self._route_entry, ...)` or the `START` fallback so phase mode can begin at `phase_2` or `phase_3`
- `_route_after_phase_1` / `_route_after_phase_2` to return `"end"` when the target phase is complete
- `PipelineRunRequest.processing_run_id: str | None`
- API route to load existing state, return 404 if missing, build a new `initial_state` from the copy

Actual:
- `graph.set_entry_point("phase_1")` is hard-coded (line 189)
- The conditional path dict (`{"phase_2": "phase_2", "phase_3": "phase_3"}`) is not present
- `PipelineRunRequest` has no `processing_run_id` field
- The route always allocates new `processing_run_id` and `source_document_id` (lines 208-209)

Impact: Success Criterion #5 unmet. PHASE mode always re-runs Phase 1. Re-running Phase 2/3 from an existing run is not exposed.

Fix: Add `_route_entry` and `_is_target_phase_complete` per plan Step 3. Switch to `set_conditional_entry_point` (or the `START` fallback if the runtime check fails). Add `processing_run_id` to `PipelineRunRequest` and the existing-state lookup branch in the route.

### 🔴 [blocking] Production `API_KEY` guard not implemented (Task 9, Step 3)

**File**: `backend/src/core/config.py:329-406`

Plan requires at the end of `_build_nested()`:
```python
if self.is_production and not self.api_key.strip():
    raise ValueError("API_KEY must be set when ENVIRONMENT=production")
```

Actual `_build_nested()` ends at line 406 with the `network` model build and `return self`. No production guard. `tests/core/test_config.py` has no `test_production_requires_api_key` test.

Impact: Success Criterion #7 unmet. A misconfigured production deployment with empty `API_KEY` boots successfully and runs in a fail-open auth state. This is the exact "auth fail-open" issue the plan claims to fix.

Fix: Add the guard as the last statement before `return self` in `_build_nested()`. Add the two tests (`test_production_requires_api_key`, `test_production_accepts_api_key`) per plan.

### 🔴 [blocking] LLM `temperature` / `max_retries` not propagated to nested configs (Task 9, Step 3)

**File**: `backend/src/core/config.py:339-355`

Plan requires `LLMConfig(...)` and `ReasoningConfig(...)` to receive `temperature=self.fast_llm_temperature, max_retries=self.fast_llm_max_retries` (and reasoning variants).

Actual:
- The flat fields `fast_llm_temperature`, `fast_llm_max_retries`, `reasoning_llm_temperature`, `reasoning_llm_max_retries` are declared (lines 229, 232, 242, 245)
- `_build_nested()` constructs `LLMConfig` / `ReasoningConfig` without those keys — the values are silently dropped

Impact: Operators setting `FAST_LLM_TEMPERATURE` or `REASONING_LLM_MAX_RETRIES` env vars get no effect. LLM behavior diverges from the production-config contract the plan establishes. `test_llm_temperature_and_retries_are_propagated` is absent from the test file.

Fix: Add `temperature=` and `max_retries=` keyword arguments to both `LLMConfig(...)` and `ReasoningConfig(...)` constructor calls in `_build_nested()`. Add the test from plan Step 1.

### 🟡 [important] Startup advisory lock not implemented (Task 4, Step 4)

**File**: `backend/app/main.py:90-104`

Plan requires wrapping `search_index_metadata.create_all()` and `runner.recover_orphaned_runs()` in `pg_try_advisory_lock('acmg_lingua_backend_startup')` so only one worker runs startup recovery.

Actual `lifespan()` calls `search_index_metadata.create_all` and `recover_orphaned_runs()` directly with no lock. Under multi-worker uvicorn, every worker races to create the search-index metadata and recover orphans.

Impact: Multi-worker startup race. Orphan recovery runs N times in parallel; depending on the recovery semantics, the second worker either no-ops or overwrites the first worker's `completed_at` timestamps.

Fix: Add the `_try_startup_lock` helper per plan Step 4. Wrap the two calls in the lock-conditional branch. Release the lock in `finally`. Update `tests/integration/test_app_startup.py` mocks.

### 🟡 [important] `PipelineRunner.start()` does not claim ownership or run heartbeat (Task 3, Step 4)

**File**: `backend/src/agents/runner.py:46-107`

Plan requires:
- `start()` becomes `async def`, returns the task only after writing the initial state with `owner_worker_id` and `heartbeat_at`
- A heartbeat task is started before acquiring the semaphore and cancelled in `finally`
- `IntegrityError` from the first save propagates to the API route, which converts it to 409

Actual `start()` is synchronous, writes `initial_state` once with no ownership fields, and has no heartbeat task. `is_running_for_source` is still synchronous (line 187), not `async def`. The `try/except IntegrityError → 409` wrapper is absent from `src/api/v1/pipeline.py:190-278`.

Impact: The lease column absence (already flagged) compounds here — even if the ORM were migrated, the runner would not write the lease fields, so the partial unique index cannot enforce dedup. The duplicate-source race the plan targets remains a real failure mode.

Fix: Implement ownership write + heartbeat task per plan Task 3 Step 4. Add `await runner.start(initial_state)` in the route inside a `try/except IntegrityError` that returns 409.

### 🟡 [important] Field-level evidence payload preservation missing (Task 6)

**Files**: `backend/src/dao/postgresql/contracts.py`, `backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py`, `backend/src/core/visualize_evidence_with_expert_in_loop/feedback_service.py`

Plan requires:
- `CanonicalEvidencePayload` Pydantic model in `dao/postgresql/contracts.py` with `extra="allow"` (the spec is the field type, not a naked return — see the plan note about typing rules)
- `FIELD_ID_TO_CARD_FIELD` mapping and `card_field_for_field_id()` helper
- `EvidenceCardPayload.from_field_payload(...)` classmethod
- `FeedbackService.patch_evidence()` to merge the field-level payload, not replace the whole dict with `new_card.model_dump()`

Actual:
- `src/dao/postgresql/contracts.py:1-16` contains only `AsyncpgServerSettings` / `AsyncpgConnectArgs` TypedDicts — no `CanonicalEvidencePayload`
- `src/core/visualize_evidence_with_expert_in_loop/contracts.py:54-88` has `EvidenceCardPayload` but no `from_field_payload` and no `FIELD_ID_TO_CARD_FIELD`
- `feedback_service.py:80` still does `evidence.active_payload = new_payload.model_dump()` — the destructive overwrite the plan explicitly forbids

Impact: Success Criterion #3 unmet. Patching a card drops `group_id`, `track`, `entity_id`, and the `source` span dict. The exact evidence data-loss class the plan targets persists.

Fix: Implement `CanonicalEvidencePayload`, `FIELD_ID_TO_CARD_FIELD`, `card_field_for_field_id()`, and `from_field_payload()` per plan. Change `patch_evidence()` to project old + new cards, compute deltas, and only write the affected fields into `active_payload`.

### 🟢 [nit] `DirectStatePersistence.save` missing `await` (pre-existing)

**File**: `backend/src/agents/state_persistence.py:67`

`existing = await self._session.get(...)` — this line does not appear. The `self._session.get(...)` call is missing `await`. The plan does not touch this file, but the file appears in the diff (`git diff --stat` shows `state_persistence.py | 157 +++++++  ...`).

Severity: Pre-existing or introduced during the lease refactor. Either way, `DirectStatePersistence.save` will raise `TypeError: object coroutine is not subscriptable` or similar at the first `existing.X` access. Likely silent because `DirectStatePersistence` is documented as "unit tests only" — but the plan's own Task 3 test changes exercise it.

Fix: Add `await` before `self._session.get(...)`. Confirm with a single targeted test that the path runs end-to-end.

## Verification

| Check | Command | Result |
|---|---|---|
| Plan-to-commit coverage | `git log --format='%H %s' origin/dev..fix/pipeline-correctness-remediation` | 11 commits present; commit messages match plan Task 1–10 sequence ✅ |
| Migration file present | `ls database/migrations/versions/2026-06-11_add_pipeline_run_leases.py` | File not found ❌ |
| Alembic head points to lease migration | `uv run alembic -c ../database/alembic.ini heads` | Head: `2026_06_11_allow_standalone_chat_sessions` ❌ |
| ORM lease columns present | `grep -n "source_key\|owner_worker_id\|heartbeat_at" backend/src/dao/postgresql/models.py` | No matches ❌ |
| Phase 3 ambiguous fix | `grep -n "ambiguous_count" backend/src/agents/phase_3_adapter.py` | Reads the field; still gates on `standardized_count == 0` ❌ |
| Finalize endpoint | `grep -n "finalize" backend/src/api/v1/pipeline.py backend/src/agents/runner.py` | No matches ❌ |
| Production API key guard | `grep -n "is_production and not self.api_key" backend/src/core/config.py` | No match ❌ |
| Conditional entry point | `grep -n "set_conditional_entry_point\|START" backend/src/agents/orchestrator.py` | No match ❌ |
| CanonicalEvidencePayload | `grep -rn "CanonicalEvidencePayload" backend/src/` | No match ❌ |
| LLMConfig temperature | `grep -n "temperature=" backend/src/core/config.py` | No match in `_build_nested` ❌ |
| URL streaming typo | `grep -n "aiter_bytes\|ait_bytes" backend/src/core/ingest_and_digitize_data/parse_document/orchestrator.py` | `aiter_bytes` ✅ |
| Frontend status enum | (frontend diff not reviewed in this pass) | n/a |

## Recommended Next Steps

1. **Blocking** — Implement Tasks 2, 5, 7, 9 in full (see Findings 1, 3, 4, 5, 6). These are the four P0 success criteria.
2. **Important** — Implement Tasks 3 (start ownership + heartbeat + 409), 4 (advisory lock), 6 (field-level payload). These close the remaining criteria.
3. **Split or rename** — If a quick-merge is needed, extract the stable subset (`aiter_bytes` fix, `recover_orphaned_runs` filter on heartbeat if ORM were present) into a smaller `fix/parser-streaming-orphaned-recovery` branch and merge that. Keep the remainder in the current branch until complete.
4. **Doc housekeeping** — After merge, archive this plan to `docs/archive/plans/` and this review to `docs/archive/codereview/`. Update `docs/README.md` index. Add a `lesson.md` entry explaining why 6 of 8 success criteria were missed in the first pass (suspected: Tasks were marked done by commit count rather than by plan-criterion coverage).

## References

- Plan: `docs/plans/2026-06-11-pipeline-correctness-remediation.md`
- Branch: `fix/pipeline-correctness-remediation` (11 commits, +1202 / −187)
- Reviewer skills: `code-review-excellence`
