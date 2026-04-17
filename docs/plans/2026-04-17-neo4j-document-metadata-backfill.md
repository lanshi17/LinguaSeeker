# Neo4j Document Metadata Backfill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Backfill existing Neo4j `Document` nodes with PostgreSQL metadata (`title`, `file_hash`, `status`, `pmid`) and keep future graph syncs writing those fields.

**Architecture:** Keep the forward sync fix inside `GraphSyncService._sync_to_neo4j()` so all new writes pass document metadata into `neo.upsert_document(...)`. Add a lightweight document-only backfill service and CLI that read rows from PostgreSQL `documents` and upsert Neo4j `Document` node properties without replaying evidence, variants, or relationships.

**Tech Stack:** Python, pytest, PostgreSQL, Neo4j, argparse, Loguru.

---

## Execution notes

1. Ignore unrelated working tree changes under `deploy/*` while implementing this plan.
2. Do not broaden scope beyond `Document` node properties in this pass.
3. Do not commit unless explicitly asked; commit steps below are handoff structure only.
4. Use `@test-driven-development` for every code change.
5. If a real backfill command fails against Neo4j/PostgreSQL for an unexpected reason, stop and use `@systematic-debugging` before changing more code.

---

### Task 1: Lock in the forward sync behavior with a unit regression test

**Files:**
- Modify: `apps/backend/tests/unit/test_domain_graph.py:173-345`
- Modify: `apps/backend/src/domain/graph/sync.py:1501-1540`
- Read: `apps/backend/src/infrastructure/neo4j.py:159-165`
- Read: `apps/backend/src/infrastructure/postgres.py:264-293`

**Step 1: Write the failing test**

Add a unit test to `apps/backend/tests/unit/test_domain_graph.py` named:

```python
def test_graph_sync_evidence_upserts_document_metadata(...):
```

The test should:
- use a fake Neo4j client that records `upsert_document(document_id, **props)` calls
- use a fake Postgres client whose `get_document_by_id()` returns a document with:
  - `title='Example document title'`
  - `file_hash='hash-123'`
  - `status='success'`
  - `pmid='12345678'`
- call:

```python
service.sync_evidence('00000000-0000-0000-0000-000000000001', evidence_output)
```

- assert the recorded `upsert_document()` call is exactly:

```python
[
    {
        'document_id': '00000000-0000-0000-0000-000000000001',
        'title': 'Example document title',
        'file_hash': 'hash-123',
        'status': 'success',
        'pmid': '12345678',
    }
]
```

**Step 2: Run the test to verify it fails**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
pytest -q tests/unit/test_domain_graph.py::test_graph_sync_evidence_upserts_document_metadata
```

Expected: FAIL because `_sync_to_neo4j()` currently calls `neo.upsert_document(document_id)` without metadata.

**Step 3: Write the minimal implementation**

Update `apps/backend/src/domain/graph/sync.py` inside `_sync_to_neo4j()` to:
- call `self._pg.get_document_by_id(UUID(str(document_id)))` when available
- build a `document_props` dict from non-empty values only:
  - `title`
  - `file_hash`
  - `status`
  - `pmid`
- change:

```python
neo.upsert_document(str(document_id))
```

to:

```python
neo.upsert_document(str(document_id), **document_props)
```

Do not change any non-`Document` graph writes in this task.

**Step 4: Run the test to verify it passes**

Run the same command again.

Expected: PASS.

**Step 5: Run nearby graph sync tests**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
pytest -q tests/unit/test_domain_graph.py
```

Expected: PASS.

---

### Task 2: Add a document-only Neo4j metadata backfill service

**Files:**
- Create: `apps/backend/src/services/neo4j_document_backfill.py`
- Create: `apps/backend/tests/unit/test_neo4j_document_backfill.py`
- Read: `apps/backend/src/services/kg_backfill.py:37-113`
- Read: `apps/backend/src/infrastructure/postgres.py:281-293`
- Read: `apps/backend/src/infrastructure/neo4j.py:159-165`

**Step 1: Write the failing test**

Create `apps/backend/tests/unit/test_neo4j_document_backfill.py` with a test named:

```python
def test_run_document_metadata_backfill_upserts_document_props():
```

The test should:
- fake `postgres_client.list_documents(limit=..., offset=...)` to return two document-like objects
- fake `neo4j_client.upsert_document()` and capture calls
- call:

```python
report = run_document_metadata_backfill(
    limit=2,
    offset=0,
    postgres_client=fake_pg,
    neo4j_client=fake_neo,
)
```

- assert:
  - two `upsert_document()` calls were made
  - each call included only non-empty props
  - `report == {'processed': 2, 'document_ids': [...]} `

**Step 2: Run the test to verify it fails**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
pytest -q tests/unit/test_neo4j_document_backfill.py::test_run_document_metadata_backfill_upserts_document_props
```

Expected: FAIL because the service file does not exist yet.

**Step 3: Write the minimal implementation**

Create `apps/backend/src/services/neo4j_document_backfill.py` with:

```python
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.infrastructure.neo4j import Neo4jClient, get_neo4j_client
from src.infrastructure.postgres import PostgresClient, get_postgres_client


def _document_props(document: Any) -> Dict[str, Any]:
    props: Dict[str, Any] = {}
    for field in ("title", "file_hash", "status", "pmid"):
        value = getattr(document, field, None)
        if value:
            props[field] = value
    return props


def run_document_metadata_backfill(
    *,
    limit: int,
    offset: int = 0,
    postgres_client: Optional[PostgresClient] = None,
    neo4j_client: Optional[Neo4jClient] = None,
) -> Dict[str, Any]:
    postgres = postgres_client or get_postgres_client()
    neo = neo4j_client or get_neo4j_client()
    documents = postgres.list_documents(limit=max(int(limit), 0), offset=max(int(offset), 0))

    document_ids: List[str] = []
    for document in documents:
        document_id = str(document.document_id)
        neo.upsert_document(document_id, **_document_props(document))
        document_ids.append(document_id)

    return {
        "processed": len(document_ids),
        "document_ids": document_ids,
    }
```

Do not add batching beyond `limit`/`offset`. Do not touch evidence/variant sync here.

**Step 4: Run the test to verify it passes**

Run the same single-test command again.

Expected: PASS.

**Step 5: Run the new unit test file**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
pytest -q tests/unit/test_neo4j_document_backfill.py
```

Expected: PASS.

---

### Task 3: Add a CLI entrypoint for the document metadata backfill

**Files:**
- Create: `apps/backend/src/services/neo4j_document_backfill_cli.py`
- Modify: `apps/backend/tests/unit/test_neo4j_document_backfill.py`
- Read: `apps/backend/src/services/kg_backfill_cli.py:11-40`

**Step 1: Write the failing test**

Extend `apps/backend/tests/unit/test_neo4j_document_backfill.py` with:

```python
def test_document_backfill_cli_invokes_service(monkeypatch):
```

The test should:
- monkeypatch `run_document_metadata_backfill`
- call `main(['--limit', '5', '--offset', '10'])`
- assert the service was called with `limit=5`, `offset=10`
- assert `main(...) == 0`

**Step 2: Run the test to verify it fails**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
pytest -q tests/unit/test_neo4j_document_backfill.py::test_document_backfill_cli_invokes_service
```

Expected: FAIL because the CLI file does not exist yet.

**Step 3: Write the minimal implementation**

Create `apps/backend/src/services/neo4j_document_backfill_cli.py` mirroring the style of `kg_backfill_cli.py`:

```python
from __future__ import annotations

import argparse
from typing import Sequence

from loguru import logger

from src.services.neo4j_document_backfill import run_document_metadata_backfill


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Backfill Neo4j Document node metadata from PostgreSQL documents.',
    )
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--offset', type=int, default=0)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    report = run_document_metadata_backfill(limit=args.limit, offset=args.offset)
    logger.info('Neo4j document metadata backfill processed {} document(s)', report['processed'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

**Step 4: Run the CLI test to verify it passes**

Run the same single-test command again.

Expected: PASS.

**Step 5: Run the unit test file again**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
pytest -q tests/unit/test_neo4j_document_backfill.py
```

Expected: PASS.

---

### Task 4: Run the real backfill and verify a sample document node

**Files:**
- Use: `apps/backend/src/services/neo4j_document_backfill_cli.py`
- Read: `apps/backend/src/services/neo4j_document_backfill.py`
- Verify against current data using one known document: `f9dd61ca-3ad6-453c-b844-1dcfa98899ea`

**Step 1: Run the backfill command**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
python -m src.services.neo4j_document_backfill_cli --limit 1000 --offset 0
```

Expected: INFO log with processed document count.

**Step 2: Verify one sample document in Neo4j**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
python - <<'PY'
from src.infrastructure.neo4j import get_neo4j_client
neo = get_neo4j_client()
rows = neo.run_query(
    "MATCH (d:Document {document_id: $id}) RETURN properties(d) AS props",
    {"id": "f9dd61ca-3ad6-453c-b844-1dcfa98899ea"},
)
print(rows)
PY
```

Expected: returned `props` includes at least:
- `document_id`
- `title`
- `file_hash`
- `status`

`pmid` may be absent for web-only documents.

**Step 3: Run the focused regression suite**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
pytest -q \
  tests/unit/test_domain_graph.py::test_graph_sync_evidence_upserts_document_metadata \
  tests/unit/test_neo4j_document_backfill.py
```

Expected: PASS.

---

### Task 5: Inspect and report other likely unsynced Neo4j node fields

**Files:**
- Read-only inspection using current runtime data
- No production code changes in this task

**Step 1: Query sample properties by label**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
python - <<'PY'
from src.infrastructure.neo4j import get_neo4j_client
neo = get_neo4j_client()
for label in ['Gene', 'Variant', 'Evidence', 'Disease', 'Phenotype', 'Transcript']:
    rows = neo.run_query(f"MATCH (n:{label}) RETURN properties(n) AS props LIMIT 3")
    print(f'=== {label} ===')
    print(rows)
PY
```

**Step 2: Summarize findings**

Report which labels appear to be missing important fields beyond their identity keys.

Do not fix them in this plan.

---

## Execution handoff

Plan complete and saved to `docs/plans/2026-04-17-neo4j-document-metadata-backfill.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
