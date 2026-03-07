# Issues - ACMG Agent Refactor

## Session: ses_33cdadbf8ffef2nE52qpvy8S5B

### Known Issues (from Metis review)
- Graph sync may not be idempotent (create_evidence_record may duplicate on retry) — document in tests, do NOT fix
- asyncio.run() multi-call pattern in current tasks.py — Supervisor will fix with single context
- Translation duplication between tasks.py and workflow.py — Supervisor will deduplicate

## create_evidence_record Idempotency
- **File**: `src/database/postgre_client.py`
- **Behavior**: `create_evidence_record` constructs `EvidenceRecord(...)`, calls `session.add(record)`, then `session.flush()` without checking for an existing row or using any upsert/merge path.
- **Risk during refactor**: retry paths can create duplicate evidence rows for the same document if graph sync is re-entered.
- **Decision**: Document only, do NOT fix in this sprint.
