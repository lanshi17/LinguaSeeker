## Task 2.2: Sync Blocking in Async FastAPI - Documentation Complete

**Status**: ✅ Complete (Documentation-only)

**What was done**:
- Added TODO(P1) comments to `src/api/routes/core.py::upload_pdf()` (line 157)
- Added TODO(P1) comments to `src/api/routes/task.py::create_task_request_by_upload()` (line 786)

**Why this approach**:
This task is DOCUMENTATION-ONLY per P0 plan. The actual blocking issue (sync PostgresClient calls in async handlers) requires architecture refactoring that belongs in Phase 2 or later, not P0.

The TODO comments:
1. **Identify the problem**: "mixes sync PostgresClient calls with async MinIO calls"
2. **Explain the impact**: "blocks the event loop during postgres operations under concurrent load"
3. **Propose solutions**: Two alternatives (wrap with anyio.to_thread or migrate to AsyncSession)
4. **Reference context**: Links to architecture refactor plan

**Key decision**: We document (P0) but don't fix the blocking issue now. Full fix requires:
- Either: Wrap all postgres calls with `await anyio.to_thread.run_sync()`
- Or: Migrate PostgresClient from sync to AsyncSession
Both changes are substantial and belong in architecture refactor, not P0 minimal fixes.

**Verification**:
- LSP diagnostics: ✅ Zero errors in both files
- No logic changes: ✅ Comments only
- Comments are concise and actionable: ✅ Yes
