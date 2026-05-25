# standardize_entities_and_align_knowledge

> Deterministic Phase 3 entity standardization slice. It imports local biomedical terminology sources, adapts Phase 2 dual-track evidence output into typed candidates, matches those candidates to reference identifiers, and persists normalized entities plus evidence bindings into the PostgreSQL MVP schema.

## Quick Start

```python
from src.core.config import get_config
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
)
from src.core.standardize_entities_and_align_knowledge.api import (
    EntityStandardizationService,
)

cfg = get_config()
service = EntityStandardizationService(cfg=cfg, session=async_session)

result: DualEvidenceExtractionResult = ...
output = await service.run_dual_result(
    result,
    source_document_id="source-document-id",
    processing_run_id="processing-run-id",
)

assert output.match_count >= 0
```

Importing reference data uses the CLI entry point:

```bash
cd backend
uv run ../scripts/import_terminology.py \
  --version 2026-05-25 \
  --terminology-root ../database/terminology_database \
  --sources hgnc omim hpo clingen clinvar
```

## Architecture

```text
DualEvidenceExtractionResult
  -> DualResultAdapter
  -> StandardizationInput
  -> StandardizationService
     -> TerminologyMatcher
     -> StandardizationRepository
        -> terminology_entries / terminology_aliases / terminology_relationships
        -> normalized_entities / run_evidence_items / evidence_entity_bindings / canonical_evidence_items
```

The slice follows the repo’s vertical-slice layout:

- `api.py`: public facade and terminology import entry point
- `contracts.py`: typed service contracts
- `adapters.py`: Phase 2 to Phase 3 boundary adapter
- `importers.py`: local terminology file parsers
- `matchers.py`: deterministic source-priority matching
- `repositories.py`: write boundary to SQLAlchemy ORM models
- `normalizers.py`: shared text normalization and scope hashing
- `core.py`: orchestration only

## Public API

### `EntityStandardizationService`

| Method | Signature | Description |
|---|---|---|
| `__init__` | `(cfg: Any, session: Any)` | Accepts global config plus an async SQLAlchemy session or session-like test double. |
| `run_dual_result` | `(result: DualEvidenceExtractionResult, *, source_document_id: str, processing_run_id: str) -> StandardizationResult` | Adapts a dual-track extraction result, matches all candidates, and persists normalized state. |

### `import_terminology`

| Method | Signature | Description |
|---|---|---|
| `import_terminology` | `(*, cfg: Any, terminology_root: Path, version: str, sources: list[str]) -> None` | Loads requested local terminology batches, opens an async DB session, and upserts each batch. |

### `StandardizationResult`

```python
@dataclass(frozen=True)
class StandardizationResult:
    document_id: str
    match_count: int
    standardized_count: int
    ambiguous_count: int
    unmapped_count: int
    normalized_entity_ids: tuple[str, ...]
```

Returned by `StandardizationService.run()` and the facade. Counts are per candidate, not per evidence item.

## Contracts

### Core enums

- `EntityType`: `gene`, `disease`, `phenotype`, `variant`
- `BindingRole`: `subject`, `target`, `context`, `mention`
- `MatchStatus`: `standardized`, `unmapped`, `ambiguous`
- `CanonicalStatusRank`: symbolic status ordering used by canonical evidence selection

### Main dataclasses

| Type | Purpose |
|---|---|
| `StandardizationCandidate` | One entity mention extracted from a chain or phenotype field |
| `TerminologyCandidate` | One repository lookup hit from `terminology_aliases` |
| `EntityMatch` | Match decision for one candidate |
| `StandardizationInput` | Service boundary input for one processing run |
| `StandardizationResult` | Service summary output |
| `ImportEntry` / `ImportAlias` / `ImportRelationship` / `ImportBatch` | Parser staging payloads for terminology import |

## Import Flow

Reference import is split into two layers:

1. `importers.py` parses local files into immutable staging objects.
2. `repositories.py::upsert_terminology_batch()` converts those staging objects into ORM rows.

Current parsers:

| Source | Entry point | Output |
|---|---|---|
| HGNC | `parse_hgnc_rows()` | gene entries + aliases |
| OMIM | `parse_omim_rows()` | disease entries + aliases |
| HPO | `parse_hpo_rows()` | phenotype entries + aliases |
| ClinGen | `parse_clingen_rows()` | MONDO fallback disease entries + relationships |
| ClinVar | `parse_clinvar_rows()` | variant entries + aliases + scalar clinical-significance relationships |

Important implementation details:

- ClinVar rows stream through `_iter_tsv_rows()`; the parser does not load the whole file into memory.
- `is_importable_clinvar_review_status()` excludes 0-star or evidence-free ClinVar rows.
- `upsert_terminology_batch()` resolves relationship subjects and objects by either external ID or alias lookup.

## Matcher Rules

`TerminologyMatcher` is deterministic only. There is no fuzzy text matching, vector retrieval, or LLM disambiguation.

Source priority by entity type:

- gene: `HGNC`
- disease: `OMIM`, then `HPO` / `MONDO`
- phenotype: `HPO`
- variant: `ClinVar`

Alias priority within a source:

`primary > alias > previous_symbol > name > rsid`

If exactly one candidate remains after ranking, the result is `standardized`. If multiple remain, it is `ambiguous`. If none remain, it is `unmapped`.

## Repository Write Boundaries

`StandardizationRepository` owns all persistence:

### Terminology reference writes

- `upsert_terminology_batch()`
  - inserts or updates `TerminologyEntry`
  - inserts or updates `TerminologyAlias`
  - inserts or updates `TerminologyRelationship`

### Run persistence

- `upsert_normalized_entity()`
  - writes `NormalizedEntity`
  - preserves `raw_payload` rationale and terminology candidate IDs

- `insert_run_evidence_items()`
  - writes `RunEvidenceItem`
  - prefers real `track_payloads["*/evidence_items"]` when available
  - falls back to candidate-derived records when only match data exists

- `insert_entity_bindings()`
  - writes `EvidenceEntityBinding`
  - maps roles from candidate roles already assigned by the adapter

- `upsert_canonical_evidence()`
  - writes or updates `CanonicalEvidenceItem`
  - uses status priority `found > source_invalid > ocr_gap > table_ungrounded > not_found`
  - does not create canonical rows for ordinary `not_found`

The repository is the only place allowed to translate Phase 3 contracts into ORM rows.

## Usage Patterns

### 1. Standardize one dual-track result

```python
service = EntityStandardizationService(cfg=cfg, session=session)
result = await service.run_dual_result(
    dual_result,
    source_document_id="source-1",
    processing_run_id="run-1",
)

print(result.standardized_count, result.ambiguous_count, result.unmapped_count)
```

### 2. Match a single candidate in isolation

```python
from src.core.standardize_entities_and_align_knowledge.matchers import TerminologyMatcher
from src.core.standardize_entities_and_align_knowledge.repositories import StandardizationRepository

repo = StandardizationRepository(session)
matcher = TerminologyMatcher(repo)
match = await matcher.match(candidate)
```

### 3. Load terminology data without running the full pipeline

```python
from pathlib import Path

from src.core.standardize_entities_and_align_knowledge.importers import parse_clinvar_rows

batch = parse_clinvar_rows(
    Path("database/terminology_database/clinvar/variant_summary.txt"),
    version="clinvar_20260525",
)
await repository.upsert_terminology_batch(batch)
```

## Extension Guide

### Add a new terminology source

1. Add a parser in `importers.py` returning `ImportBatch`.
2. Extend `_load_import_batches()` in `api.py`.
3. Add parser tests with tiny fixtures.
4. Keep normalization in `normalizers.py` so import-time and query-time behavior stay aligned.

### Add a new entity type

1. Extend `EntityType` and `ROLE_BY_ENTITY_TYPE`.
2. Decide source priority in `matchers.py`.
3. Update repository normalization rules in `_normalize_entity_text()`.
4. Add adapter extraction logic if the entity originates from Phase 2 fields.

### Change canonical selection rules

The canonical decision logic is isolated in:

- `CANONICAL_STATUS_PRIORITY`
- `CANONICAL_ELIGIBLE_STATUSES`
- `upsert_canonical_evidence()`

Change those together and add a repository/service test before modifying production behavior.

## Performance Notes

- ClinVar import is streamed row-by-row. Avoid any helper that materializes the full TSV.
- Candidate matching is exact lookup on `terminology_aliases.normalized_alias`; no expensive similarity search exists in MVP.
- `DualResultAdapter` deduplicates by `(entity_type, normalized_text, chain_id)` so duplicate original/translated chains do not double the candidate count.
- Repository helpers currently run per-entity/per-relationship lookups. This is correct for MVP but not optimized for large batch import throughput.

## Unsupported Next Iteration Features

These are intentionally out of scope in the current implementation:

- fused-result input path (`FusedResultAdapter`)
- semantic retrieval or vector disambiguation
- LLM/agent-driven entity arbitration
- full dbSNP import
- review queue UI
- full MONDO graph import
- production-grade bulk upsert optimization for multi-million-row terminology refreshes

## Dependencies

| Dependency | Purpose |
|---|---|
| `pydantic` | Phase 2 extraction contracts consumed by the adapter |
| `sqlalchemy` | ORM-backed persistence to the MVP schema |
| `asyncpg` | PostgreSQL async driver used by `dao.connection` |
| `alembic` | migration management for terminology reference tables |
| `pytest` / `pytest-asyncio` | unit and integration-style verification |
| `ruff` | lint enforcement |

## Testing

Targeted verification used for this module:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge tests/dao/test_models.py tests/dao/test_alembic_migration.py -v
uv run --extra dev ruff check src/core/standardize_entities_and_align_knowledge src/dao tests/core/standardize_entities_and_align_knowledge tests/dao
```

Coverage areas currently present:

- ORM + Alembic parity for terminology tables
- contract and normalizer stability
- parser behavior and helper edge cases
- deterministic matcher ranking
- adapter candidate extraction and deduplication
- service orchestration
- facade integration with fake repository/session wiring
- repository staging behavior for terminology batches and evidence persistence
