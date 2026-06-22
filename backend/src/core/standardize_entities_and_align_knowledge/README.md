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
service = EntityStandardizationService(cfg=cfg)

result: DualEvidenceExtractionResult = ...
output = await service.run_dual_result(
    session=async_session,
    result=result,
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

Building terminology embeddings for semantic matching:

```bash
cd backend
uv run ../scripts/build_terminology_embeddings.py
```

## Architecture

```text
DualEvidenceExtractionResult
  -> DualResultAdapter
  -> StandardizationInput
  -> StandardizationService
     -> HybridTerminologyMatcher
        -> PreciseTerminologyMatcher (deterministic alias lookup)
        -> SimilarityTerminologyMatcher (semantic fallback)
           -> FallbackEmbeddingProvider
              -> local:  ModelServerEmbeddingProvider -> model-server /v1/embeddings
              -> remote: ModelServerEmbeddingProvider -> remote API (fallback)
           -> PgvectorTerminologyRepository -> pgvector cosine distance
           -> FallbackRerankProvider
              -> local:  ModelServerRerankProvider -> model-server /v1/rerank
              -> remote: ModelServerRerankProvider -> remote API (fallback)
     -> AcmgReadyProjector (ACMG rules-engine facts)
     -> StandardizationRepository
        -> terminology_entries / terminology_aliases / terminology_relationships
        -> terminology_embeddings (pgvector)
        -> normalized_entities / run_evidence_items / evidence_entity_bindings / canonical_evidence_items
     -> refresh_literature_profile()
     -> refresh_search_index()
```

The slice follows the repo's vertical-slice layout:

- `api.py`: public facade (`EntityStandardizationService`) and terminology import/embedding entry points
- `contracts.py`: typed service contracts
- `adapters.py`: Phase 2 to Phase 3 boundary adapter
- `importers.py`: local terminology file parsers
- `matchers.py`: matcher facade with `HybridTerminologyMatcher`
- `precise_match/`: deterministic source-priority matching
- `similarity_match/`: semantic matching via pgvector and model-server (providers, repositories, indexer, contracts)
- `repositories.py`: write boundary to SQLAlchemy ORM models
- `normalizers.py`: shared text normalization, scope hashing, and cross-lingual disease mapping
- `acmg_projection.py`: projects standardized entities into ACMG-ready evidence facts
- `core.py`: orchestration only
- `context_pack/`: context pack assembly helpers

## Public API

### `EntityStandardizationService`

| Method | Signature | Description |
|---|---|---|
| `__init__` | `(cfg: Settings)` | Accepts global config. Session is passed per-call. |
| `run_dual_result` | `(session: AsyncSession, result: DualEvidenceExtractionResult, *, source_document_id: str, processing_run_id: str) -> StandardizationResult` | Adapts a dual-track extraction result, matches all candidates, and persists normalized state. |

### `import_terminology`

| Method | Signature | Description |
|---|---|---|
| `import_terminology` | `(*, cfg: Any, terminology_root: Path, version: str, sources: list[str]) -> None` | Loads requested local terminology batches, opens an async DB session, and upserts each batch. |

### `build_terminology_embeddings`

| Method | Signature | Description |
|---|---|---|
| `build_terminology_embeddings` | `(*, cfg: Any, entity_types: set[EntityType] \| None = None, source_dbs: set[str] \| None = None) -> int` | Builds pgvector embeddings for imported terminology entries. Returns count of embeddings written. Idempotent via upsert. Optional filters restrict to specific entity types or source databases. |

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
    matches: tuple[EntityMatch, ...] = ()
    acmg_ready: AcmgReadyEvidenceSet | None = None
```

Returned by `StandardizationService.run()` and the facade. Counts are per candidate, not per evidence item. The `matches` field carries the full `EntityMatch` tuple for downstream inspection. The `acmg_ready` field provides a projected `AcmgReadyEvidenceSet` when ACMG-eligible phenotype matches exist.

## Contracts

### Core enums

- `EntityType`: `gene`, `disease`, `phenotype`, `variant`
- `BindingRole`: `subject`, `target`, `context`, `mention`
- `MatchStatus`: `standardized`, `unmapped`, `ambiguous`
- `MatchMethod`: `precise`, `similarity`
- `CanonicalStatusRank`: symbolic status ordering used by canonical evidence selection

### Main dataclasses

| Type | Purpose |
|---|---|
| `StandardizationCandidate` | One entity mention extracted from a chain or phenotype field |
| `TerminologyCandidate` | One repository lookup hit from `terminology_aliases` |
| `SimilarityCandidate` | Semantic retrieval candidate from pgvector and rerank |
| `EntityMatch` | Match decision for one candidate |
| `StandardizationInput` | Service boundary input for one processing run |
| `StandardizationResult` | Service summary output |
| `AcmgReadyEvidenceItem` | Normalized evidence fact for ACMG scoring consumers |
| `AcmgReadyEvidenceSet` | Document-level normalized evidence projection |
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
| ClinVar | `parse_clinvar_rows()` / `iter_clinvar_batches()` | variant entries + aliases + scalar clinical-significance relationships |

Important implementation details:

- ClinVar rows stream through `_iter_tsv_rows()` and `iter_clinvar_batches()`; the parser does not load the whole file into memory.
- `is_importable_clinvar_review_status()` excludes 0-star or evidence-free ClinVar rows.
- `upsert_terminology_batch()` resolves relationship subjects and objects by either external ID or alias lookup.
- Bulk upsert uses PostgreSQL `INSERT ... ON CONFLICT` for production sessions; falls back to per-row upsert for test doubles. An optional COPY-based staging path (`_copy_upsert_*`) uses `asyncpg.copy_records_to_table` via temp tables for high-throughput scenarios.

## Matcher Rules

`HybridTerminologyMatcher` runs precise matching first, then falls back to semantic matching for unmapped candidates.

### Precise Matching

Source priority by entity type:

- gene: `HGNC`
- disease: `OMIM`, then `HPO` / `MONDO`
- phenotype: `HPO`
- variant: `ClinVar`

Alias priority within a source:

`primary > alias > previous_symbol > name > rsid`

If exactly one candidate remains after ranking, the result is `standardized`. If multiple remain, it is `ambiguous`. If none remain, it falls through to semantic matching.

### Semantic Matching

When precise matching returns `unmapped`, the system:

1. Embeds the candidate text via model-server `/v1/embeddings`
2. Retrieves nearest neighbors from `terminology_embeddings` using pgvector cosine distance
3. Reranks candidates via model-server `/v1/rerank`
4. Accepts the top candidate if rerank score exceeds threshold (default 0.7)
5. Returns `ambiguous` if top two candidates are too close (margin < 0.05)

Semantic matches are persisted with `match_method="similarity"` and include `similarity_score` and `semantic_candidates` in the raw payload for auditability.

### Graceful Degradation

Embedding and rerank providers use a local-first, remote-fallback strategy (mirroring the MinerU document parsing pattern). `FallbackEmbeddingProvider` and `FallbackRerankProvider` try the local model-server first; if it's unavailable (connection error, timeout, HTTP error), they fall back to a configured remote provider (e.g. SiliconFlow). If no remote is configured, the original error propagates. This prevents transient model-server outages from blocking the standardization pipeline.

If both local and remote providers fail (or no remote is configured and local fails), `HybridTerminologyMatcher` logs a warning and returns `unmapped` with `match_method="similarity"` and a rationale describing the failure.

## Repository Write Boundaries

`StandardizationRepository` owns all persistence:

### Terminology reference writes

- `upsert_terminology_batch()`
  - inserts or updates `TerminologyEntry`
  - inserts or updates `TerminologyAlias`
  - inserts or updates `TerminologyRelationship`
  - supports bulk upsert via `pg_insert ... ON CONFLICT DO UPDATE` for production sessions
  - optional COPY-based staging path for high-throughput scenarios

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
  - batch-loads existing canonical items in chunks of 5000 to stay under PostgreSQL's parameter limit

### Read model refresh

After persistence, the repository (called from `StandardizationService`) refreshes two read models:

- `refresh_literature_profile()` -- rebuilds `literature_profiles` via `LiteratureProfileRepository`
- `refresh_search_index()` -- rebuilds `frontend_search_index` via `SearchIndexRepository`

The repository is the only place allowed to translate Phase 3 contracts into ORM rows.

## Usage Patterns

### 1. Standardize one dual-track result

```python
service = EntityStandardizationService(cfg=cfg)
result = await service.run_dual_result(
    session=session,
    result=dual_result,
    source_document_id="source-1",
    processing_run_id="run-1",
)

print(result.standardized_count, result.ambiguous_count, result.unmapped_count)
for match in result.matches:
    print(match.candidate.raw_text, match.status.value, match.external_id)
```

### 2. Match a single candidate in isolation

```python
from src.core.standardize_entities_and_align_knowledge.precise_match import PreciseTerminologyMatcher
from src.core.standardize_entities_and_align_knowledge.repositories import StandardizationRepository

repo = StandardizationRepository(session)
matcher = PreciseTerminologyMatcher(repo)
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
- Candidate matching uses precise lookup on `terminology_aliases.normalized_alias` as the first pass. Only unmapped candidates fall through to the semantic (pgvector) path.
- `DualResultAdapter` deduplicates by `(entity_type, normalized_text, chain_id)` so duplicate original/translated chains do not double the candidate count.
- Bulk terminology upsert uses PostgreSQL `INSERT ... ON CONFLICT` for production sessions; per-row upsert for test doubles. The optional COPY staging path (`asyncpg.copy_records_to_table` via temp tables) handles high-throughput scenarios.
- Canonical evidence upserts batch-load existing items in chunks of 5000 to stay under PostgreSQL's parameter limit.

## Cross-Lingual Normalization

`normalizers.py` provides cross-lingual normalization for disease names. A built-in Chinese-to-English disease name mapping (`_CROSS_LINGUAL_DISEASE_MAP`) covers common medical genetics terms (e.g., "法布雷病" -> "fabry disease"). The `normalize_disease_lookup_text()` function applies this mapping automatically, enabling the precise matcher to resolve Chinese disease names against English terminology entries.

## Vector Similarity Search (pgvector)

Phase 3 supports optional semantic similarity search via pgvector as a fallback when deterministic matching returns no results.

### Architecture

```text
HybridTerminologyMatcher
    ├── PreciseTerminologyMatcher (deterministic alias lookup)
    └── unmapped?
        └── SimilarityTerminologyMatcher
            ├── FallbackEmbeddingProvider
            │   ├── local  -> model-server /v1/embeddings
            │   └── remote -> remote API (fallback)
            ├── PgvectorTerminologyRepository -> pgvector cosine retrieval
            └── FallbackRerankProvider
                ├── local  -> model-server /v1/rerank
                └── remote -> remote API (fallback)
```

### Enabling

1. Ensure `pgvector_enabled: true` in PostgreSQL config
2. Run the pgvector migration: `uv run alembic upgrade head`
3. Start model-server on port 8001 with embedding model loaded
4. Generate embeddings: `uv run python scripts/build_terminology_embeddings.py`

### Tables

- `terminology_embeddings`: embedding vectors indexed by HNSW for cosine similarity search

### Performance

- HNSW index with m=16, ef_construction=200 provides fast approximate nearest neighbor search
- Embedding generation is batched (configurable batch_size, default 10)
- Consider running embedding generation during off-peak hours for large terminology databases

## Unsupported Next Iteration Features

These are intentionally out of scope in the current implementation:

- fused-result input path (`FusedResultAdapter`)
- LLM/agent-driven entity reasoning
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
| `pgvector` | PostgreSQL vector similarity search for semantic matching |
| `httpx` | Async HTTP client for model-server embedding and rerank calls |
| `pytest` / `pytest-asyncio` | unit and integration-style verification |
| `ruff` | lint enforcement |

## Testing

Targeted verification used for this module:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge tests/dao/test_models.py tests/dao/test_alembic_migration.py tests/core/test_config.py -v
uv run ruff check src tests
```

Coverage areas currently present:

- ORM + Alembic parity for terminology and pgvector tables
- contract and normalizer stability
- parser behavior and helper edge cases
- deterministic matcher ranking
- semantic matcher with mock embedding/rerank providers
- hybrid matcher fallback behavior
- adapter candidate extraction and deduplication
- service orchestration
- facade integration with fake repository/session wiring
- repository staging behavior for terminology batches and evidence persistence
- embedding dimension validation
- cross-lingual disease normalization
- ACMG projection
