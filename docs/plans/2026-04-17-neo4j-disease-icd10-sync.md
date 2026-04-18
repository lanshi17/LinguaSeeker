# Neo4j Disease ICD10 Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure Neo4j `Disease` nodes preserve `icd10_code` when PostgreSQL source data contains it, and add a disease-only backfill for existing nodes.

**Architecture:** Keep the forward sync path in `GraphSyncService._sync_to_neo4j()` responsible for passing `icd10_code` into `neo.upsert_disease(...)`. Add a lightweight disease-only backfill service and CLI that read distinct `(disease_name, icd10_code)` pairs from PostgreSQL `evidence_records` and upsert only those Neo4j `Disease` properties.

**Tech Stack:** Python, pytest, PostgreSQL, Neo4j, argparse, Loguru, SQLAlchemy text queries.

---

## Execution notes

1. Work in the dedicated `neo4j-document-metadata-backfill` worktree.
2. Ignore unrelated repo changes outside this worktree.
3. Do not broaden scope beyond `Disease.icd10_code` in this pass.
4. Do not commit unless explicitly asked; commit steps below are handoff structure only.
5. Use `@test-driven-development` for each task.
6. If the real backfill processes zero rows because PostgreSQL has no non-null ICD10 values, treat that as a valid outcome and report it honestly.

---

### Task 1: Lock in the forward Disease ICD10 sync behavior with a unit regression test

**Files:**
- Modify: `apps/backend/tests/unit/test_domain_graph.py:173-276`
- Read: `apps/backend/src/domain/graph/sync.py:1612-1620`
- Read: `apps/backend/src/infrastructure/neo4j.py:143-149`

**Step 1: Write the failing test**

Add a unit test to `apps/backend/tests/unit/test_domain_graph.py` named:

```python
def test_graph_sync_evidence_upserts_disease_icd10(...):
```

The test should:
- use a fake Neo4j client that records `upsert_disease(name, **props)` calls
- use a fake Postgres client with minimal stubs for `create_evidence_record()` and `get_evidence_for_document()`
- call `service.sync_evidence(...)` with `extracted_fields` that include:

```python
"disease_chpo": {"disease_name": "D1", "icd10_code": "Q87.8"}
```

- assert one `upsert_disease()` call was made with:

```python
{"name": "D1", "icd10_code": "Q87.8"}
```

**Step 2: Run the test to verify it fails**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
pytest -q tests/unit/test_domain_graph.py::test_graph_sync_evidence_upserts_disease_icd10
```

Expected: FAIL because the current test suite does not assert this behavior yet.

**Step 3: Write the minimal implementation if needed**

Inspect `apps/backend/src/domain/graph/sync.py` around:

```python
neo.upsert_disease(disease_name, icd10_code=icd10 or None)
```

If the forward sync path already passes the ICD10 value correctly, do not change production code in this task; only keep the regression test.

If it does not, make the smallest change required so `icd10_code` is forwarded when non-empty.

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

### Task 2: Add a disease-only ICD10 backfill service

**Files:**
- Create: `apps/backend/src/services/neo4j_disease_icd10_backfill.py`
- Create: `apps/backend/tests/unit/test_neo4j_disease_icd10_backfill.py`
- Read: `apps/backend/src/services/kg_backfill.py:37-113`
- Read: `apps/backend/src/infrastructure/neo4j.py:143-149`
- Read: `apps/backend/src/infrastructure/postgres.py:207-243`

**Step 1: Write the failing test**

Create `apps/backend/tests/unit/test_neo4j_disease_icd10_backfill.py` with a test named:

```python
def test_run_disease_icd10_backfill_upserts_distinct_nonempty_pairs() -> None:
```

The test should:
- fake a Postgres client method that returns disease rows like:
  - `('D1', 'Q87.8')`
  - `('D2', 'E11.9')`
  - plus rows with `None` / empty ICD10 that should be skipped
- fake a Neo4j client that records `upsert_disease(name, **props)` calls
- call:

```python
report = run_disease_icd10_backfill(limit=10, offset=0, postgres_client=fake_pg, neo4j_client=fake_neo)
```

- assert only valid non-empty disease/ICD10 pairs are written
- assert a report like:

```python
{
    'processed': 2,
    'diseases': ['D1', 'D2'],
}
```

**Step 2: Run the test to verify it fails**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
pytest -q tests/unit/test_neo4j_disease_icd10_backfill.py::test_run_disease_icd10_backfill_upserts_distinct_nonempty_pairs
```

Expected: FAIL because the service file does not exist yet.

**Step 3: Write the minimal implementation**

Create `apps/backend/src/services/neo4j_disease_icd10_backfill.py` with:

```python
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import text

from src.infrastructure.neo4j import Neo4jClient, get_neo4j_client
from src.infrastructure.postgres import PostgresClient, get_postgres_client


def _list_disease_rows(postgres: Any, *, limit: int, offset: int) -> List[Dict[str, str]]:
    if isinstance(postgres, PostgresClient):
        with postgres.session_scope() as session:
            rows = session.execute(
                text(
                    """
                    SELECT DISTINCT disease_name, icd10_code
                    FROM evidence_records
                    WHERE disease_name IS NOT NULL
                      AND icd10_code IS NOT NULL
                    ORDER BY disease_name
                    OFFSET :offset LIMIT :limit
                    """
                ),
                {"offset": max(int(offset), 0), "limit": max(int(limit), 0)},
            ).fetchall()
        return [
            {"disease_name": row.disease_name, "icd10_code": row.icd10_code}
            for row in rows
        ]
    explicit = getattr(postgres, "list_distinct_disease_icd10_pairs", None)
    if callable(explicit):
        return list(explicit(limit=limit, offset=offset))
    raise TypeError("Unsupported postgres client for disease ICD10 backfill")


def run_disease_icd10_backfill(
    *,
    limit: int,
    offset: int = 0,
    postgres_client: Optional[PostgresClient] = None,
    neo4j_client: Optional[Neo4jClient] = None,
) -> Dict[str, Any]:
    postgres = postgres_client or get_postgres_client()
    neo = neo4j_client or get_neo4j_client()
    rows = _list_disease_rows(postgres, limit=limit, offset=offset)

    diseases: List[str] = []
    for row in rows:
        disease_name = str(row.get("disease_name") or "").strip()
        icd10_code = str(row.get("icd10_code") or "").strip()
        if not disease_name or not icd10_code:
            continue
        neo.upsert_disease(disease_name, icd10_code=icd10_code)
        diseases.append(disease_name)

    return {"processed": len(diseases), "diseases": diseases}
```

Do not add normalization beyond stripping empty values.

**Step 4: Run the test to verify it passes**

Run the same single-test command again.

Expected: PASS.

**Step 5: Run the unit test file**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
pytest -q tests/unit/test_neo4j_disease_icd10_backfill.py
```

Expected: PASS.

---

### Task 3: Add a CLI entrypoint for the disease ICD10 backfill

**Files:**
- Create: `apps/backend/src/services/neo4j_disease_icd10_backfill_cli.py`
- Modify: `apps/backend/tests/unit/test_neo4j_disease_icd10_backfill.py`
- Read: `apps/backend/src/services/kg_backfill_cli.py:11-40`

**Step 1: Write the failing test**

Extend `apps/backend/tests/unit/test_neo4j_disease_icd10_backfill.py` with:

```python
def test_disease_icd10_backfill_cli_invokes_service(monkeypatch):
```

The test should:
- monkeypatch `run_disease_icd10_backfill`
- call `main(['--limit', '5', '--offset', '10'])`
- assert the service was called with `limit=5`, `offset=10`
- assert `main(...) == 0`

**Step 2: Run the test to verify it fails**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
pytest -q tests/unit/test_neo4j_disease_icd10_backfill.py::test_disease_icd10_backfill_cli_invokes_service
```

Expected: FAIL because the CLI file does not exist yet.

**Step 3: Write the minimal implementation**

Create `apps/backend/src/services/neo4j_disease_icd10_backfill_cli.py` mirroring the style of `kg_backfill_cli.py`:

```python
from __future__ import annotations

import argparse
from typing import Sequence

from loguru import logger

from src.services.neo4j_disease_icd10_backfill import run_disease_icd10_backfill


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Backfill Neo4j Disease node ICD10 metadata from PostgreSQL evidence records.',
    )
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--offset', type=int, default=0)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    report = run_disease_icd10_backfill(limit=args.limit, offset=args.offset)
    logger.info('Neo4j disease ICD10 backfill processed {} disease row(s)', report['processed'])
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
pytest -q tests/unit/test_neo4j_disease_icd10_backfill.py
```

Expected: PASS.

---

### Task 4: Run the real disease ICD10 backfill and verify one node

**Files:**
- Use: `apps/backend/src/services/neo4j_disease_icd10_backfill_cli.py`
- Use: `apps/backend/src/services/neo4j_disease_icd10_backfill.py`

**Step 1: Inspect whether useful source rows exist**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
python - <<'PY'
from src.infrastructure.postgres import get_postgres_client
from sqlalchemy import text
pg = get_postgres_client()
with pg.session_scope() as session:
    rows = session.execute(text("""
        SELECT disease_name, icd10_code, count(*) AS n
        FROM evidence_records
        WHERE disease_name IS NOT NULL
        GROUP BY disease_name, icd10_code
        ORDER BY n DESC
        LIMIT 15
    """)).fetchall()
for row in rows:
    print(dict(row._mapping))
PY
```

Expected: likely many rows with `icd10_code = None`; if all are null, that is still valid evidence.

**Step 2: Run the backfill command**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
python -m src.services.neo4j_disease_icd10_backfill_cli --limit 1000 --offset 0
```

Expected:
- if there are non-null rows: processed count > 0
- if not: processed count = 0

Both outcomes are acceptable if they match the source data.

**Step 3: Verify one Disease node**

If a non-null ICD10 row exists, pick one `disease_name` and run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
python - <<'PY'
from src.infrastructure.neo4j import get_neo4j_client
neo = get_neo4j_client()
rows = neo.run_query(
    "MATCH (d:Disease {name: $name}) RETURN properties(d) AS props",
    {"name": "<disease-name-from-step-1>"},
)
print(rows)
PY
```

Expected: `props` includes `name` and `icd10_code`.

If no PostgreSQL rows have non-null ICD10 values, explicitly report that the backfill correctly had nothing to apply.

**Step 4: Run the focused regression suite**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
pytest -q \
  tests/unit/test_domain_graph.py::test_graph_sync_evidence_upserts_disease_icd10 \
  tests/unit/test_neo4j_disease_icd10_backfill.py
```

Expected: PASS.

---

## Execution handoff

Plan complete and saved to `docs/plans/2026-04-17-neo4j-disease-icd10-sync.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
