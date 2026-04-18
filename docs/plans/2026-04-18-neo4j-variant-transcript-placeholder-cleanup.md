# Neo4j Variant Transcript Placeholder Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stop obvious placeholder transcript values such as `"0.0"`, `"null"`, and `"None"` from being persisted into PostgreSQL evidence rows and Neo4j `Variant` / `Transcript` nodes.

**Architecture:** Keep the change tightly scoped by adding a transcript-specific normalization helper inside `GraphSyncService` instead of broad string cleaning. Apply that helper only where transcript identifiers are written into PostgreSQL evidence records and Neo4j graph nodes, and verify it with focused unit coverage.

**Tech Stack:** Python, pytest, PostgreSQL, Neo4j.

---

## Execution notes

1. Work in the dedicated `neo4j-document-metadata-backfill` worktree.
2. Ignore unrelated untracked plan docs in the main repo while implementing this plan.
3. Do not broaden scope beyond transcript placeholder filtering in this pass.
4. Do not commit unless explicitly asked; commit steps below are handoff structure only.
5. Use `@test-driven-development` for each code change.
6. If a real inspection still shows historical `transcript_id="0.0"` after the forward fix, report that clearly; backfilling historical dirty rows is out of scope unless requested later.

---

### Task 1: Lock in transcript placeholder filtering with unit regression tests

**Files:**
- Modify: `apps/backend/tests/unit/test_domain_graph.py:403-478`
- Modify: `apps/backend/src/domain/graph/sync.py:935-973,1578-1610`
- Read: `apps/backend/src/infrastructure/neo4j.py:105-141,167-173`

**Step 1: Write the failing test for placeholder transcript values**

Add a unit test to `apps/backend/tests/unit/test_domain_graph.py` named:

```python
def test_graph_sync_drops_placeholder_transcript_id_from_variant_and_transcript_nodes(...):
```

The test should:
- use a fake Neo4j client that records:
  - `upsert_variant(..., transcript_id=...)`
  - `upsert_transcript(transcript_id, ...)`
  - `link_gene_transcript(gene_symbol, transcript_id)` calls
- use a fake Postgres client that captures `create_evidence_record(**kwargs)`
- call `service.sync_evidence(...)` with:

```python
'extracted_fields': {
    'gene': {'symbol': 'GENE'},
    'variant': {'hgvs_c': 'c.1A>T', 'hgvs_p': 'p.K1N'},
    'transcript_id': {'transcript_id': '0.0'},
    'disease_chpo': {'disease_name': 'D1'},
}
```

- assert:
  - PostgreSQL `transcript_id` becomes `None`
  - Neo4j `upsert_variant()` does not receive `transcript_id='0.0'`
  - `upsert_transcript()` is not called with `'0.0'`
  - `link_gene_transcript()` is not called with `'0.0'`

**Step 2: Write the failing test for valid transcript values**

Add a second unit test named:

```python
def test_graph_sync_keeps_valid_transcript_id(...):
```

Use the same harness, but pass:

```python
'transcript_id': {'transcript_id': 'NM_006017.3'}
```

Assert that:
- PostgreSQL receives `'NM_006017.3'`
- Neo4j variant/transcript writes still use `'NM_006017.3'`

**Step 3: Run the tests to verify the placeholder test fails for the right reason**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
pytest -q \
  tests/unit/test_domain_graph.py::test_graph_sync_drops_placeholder_transcript_id_from_variant_and_transcript_nodes \
  tests/unit/test_domain_graph.py::test_graph_sync_keeps_valid_transcript_id
```

Expected: the placeholder test FAILS because the current sync path treats `"0.0"` as a valid non-empty string.

**Step 4: Write the minimal implementation**

In `apps/backend/src/domain/graph/sync.py`:

1. Add a helper near `_normalize_string()`:

```python
@classmethod
def _normalize_transcript_id(cls, value: Any) -> Optional[str]:
    normalized = cls._normalize_string(value)
    if normalized is None:
        return None
    if normalized.lower() in {'0.0', 'null', 'none', 'nan', 'n/a'}:
        return None
    return normalized
```

2. Apply it only to transcript paths:
- where `transcript_id` is derived for PostgreSQL evidence rows
- where transcript values are passed into `neo.upsert_variant(...)`
- where transcript values are passed into `neo.upsert_transcript(...)`
- where transcript values are passed into `neo.link_gene_transcript(...)`

Do **not** change `_normalize_string()` itself.

**Step 5: Run the tests to verify they pass**

Run the same command again.

Expected: both tests PASS.

**Step 6: Run nearby graph sync tests**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
pytest -q tests/unit/test_domain_graph.py
```

Expected: PASS.

---

### Task 2: Verify the forward fix against real graph data

**Files:**
- Read-only verification against the live environment
- No new production files in this task

**Step 1: Inspect current dirty Variant nodes before the fix lands in runtime**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
python - <<'PY'
from src.infrastructure.neo4j import get_neo4j_client
neo = get_neo4j_client()
rows = neo.run_query(
    "MATCH (v:Variant) WHERE v.transcript_id = '0.0' RETURN properties(v) AS props LIMIT 10"
)
for row in rows:
    print(row)
PY
```

Expected: one or more Variant nodes still show `transcript_id: '0.0'` from historical writes.

**Step 2: Confirm the focused regression suite is green**

Run:

```bash
ENV_FILE="/mnt/data/Projects/02_Research/01_ACMG_Lingua/apps/backend/.env.local" \
uv run --directory apps/backend \
pytest -q \
  tests/unit/test_domain_graph.py::test_graph_sync_drops_placeholder_transcript_id_from_variant_and_transcript_nodes \
  tests/unit/test_domain_graph.py::test_graph_sync_keeps_valid_transcript_id
```

Expected: PASS.

**Step 3: Report the scope boundary**

Document that the fix prevents **new** bad transcript values from being written, but historical `Variant` / `Transcript` nodes with `transcript_id='0.0'` remain until a later backfill/cleanup pass is requested.

---

## Execution handoff

Plan complete and saved to `docs/plans/2026-04-18-neo4j-variant-transcript-placeholder-cleanup.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
