# Similarity Match Module

> Phase 3 submodule — semantic terminology matching via pgvector embedding retrieval + cross-encoder reranking, with model-server integration and embedding index management.

## Quick Start

```python
from src.core.standardize_entities_and_align_knowledge.similarity_match.core import (
    SimilarityTerminologyMatcher,
    SimilarityMatchConfig,
)
from src.core.standardize_entities_and_align_knowledge.similarity_match.providers import (
    FallbackEmbeddingProvider,
    FallbackRerankProvider,
    ModelServerEmbeddingProvider,
    ModelServerRerankProvider,
)
from src.core.standardize_entities_and_align_knowledge.similarity_match.repositories import (
    PgvectorTerminologyRepository,
)

config = SimilarityMatchConfig(
    embedding_model="bge-m3",
    rerank_top_k=10,
    rerank_score_threshold=0.5,
)

# Local-first with remote fallback
local_emb = ModelServerEmbeddingProvider(base_url="http://localhost:8001", model="bge-m3")
remote_emb = ModelServerEmbeddingProvider(base_url="https://api.siliconflow.cn", model="BAAI/bge-m3")
local_rerank = ModelServerRerankProvider(base_url="http://localhost:8001", model="bge-reranker-v2-m3")
remote_rerank = ModelServerRerankProvider(base_url="https://api.siliconflow.cn", model="BAAI/bge-reranker-v2-m3")

matcher = SimilarityTerminologyMatcher(
    embedding_provider=FallbackEmbeddingProvider(local_emb, remote_emb),
    rerank_provider=FallbackRerankProvider(local_rerank, remote_rerank),
    repository=PgvectorTerminologyRepository(session),
    config=config,
)
result = await matcher.match(candidate)
```

## Architecture

```
SimilarityTerminologyMatcher [core.py]
│
├─ embed_texts()          → model-server  POST /v1/embeddings
├─ find_nearest()         → pgvector      cosine similarity search
├─ rerank()               → model-server  POST /v1/rerank
├─ _merge_rerank_scores() → sort by relevance_score desc
│
└─ Decision logic:
    top_score < threshold    → UNMAPPED
    top - second < margin    → AMBIGUOUS (too close to call)
    otherwise                → STANDARDIZED
```

### Supporting modules

| Module | Purpose |
|--------|---------|
| `providers.py` | HTTP clients for model-server embedding + rerank APIs, plus local-first remote-fallback wrappers |
| `repositories.py` | pgvector cosine similarity queries |
| `indexer.py` | Batch embedding generation for terminology entries |
| `contracts.py` | Typed dataclasses for provider responses |

## Public API

### `SimilarityTerminologyMatcher`

```python
class SimilarityTerminologyMatcher:
    def __init__(self, *, embedding_provider, rerank_provider, repository, config: SimilarityMatchConfig)
    async def match(self, candidate: StandardizationCandidate) -> EntityMatch
```

### `SimilarityMatchConfig`

```python
@dataclass(frozen=True)
class SimilarityMatchConfig:
    embedding_model: str          # model name for embeddings (e.g. "bge-m3")
    rerank_top_k: int             # max candidates to retrieve + rerank
    rerank_score_threshold: float # minimum score for STANDARDIZED
    min_rerank_margin: float = 0.05  # gap between top and second for unambiguous
```

### `ModelServerEmbeddingProvider`

```python
class ModelServerEmbeddingProvider:
    def __init__(self, *, base_url: str, model: str, client=None, timeout=60.0)
    async def embed_texts(self, texts: str | Sequence[str]) -> EmbeddingBatchResult
```

Routes through `{base_url}/v1/embeddings` (OpenAI-compatible). Auto-appends `/v1` if not present.

### `ModelServerRerankProvider`

```python
class ModelServerRerankProvider:
    def __init__(self, *, base_url: str, model: str, client=None, timeout=60.0)
    async def rerank(self, query: str, documents: str | Sequence[str], *, top_k: int | None) -> RerankBatchResult
```

Routes through `{base_url}/v1/rerank`. Returns scored, sorted results.

### `FallbackEmbeddingProvider`

```python
class FallbackEmbeddingProvider:
    def __init__(self, local: ModelServerEmbeddingProvider, remote: ModelServerEmbeddingProvider | None = None)
    async def embed_texts(self, texts: str | Sequence[str]) -> EmbeddingBatchResult
```

Local-first, remote-fallback wrapper. Tries the local provider; on any failure (connection error, timeout, HTTP error), falls back to the remote provider with a warning log. If no remote is configured, re-raises the original exception.

### `FallbackRerankProvider`

```python
class FallbackRerankProvider:
    def __init__(self, local: ModelServerRerankProvider, remote: ModelServerRerankProvider | None = None)
    async def rerank(self, query: str, documents: str | Sequence[str], *, top_k: int | None) -> RerankBatchResult
```

Same local-first, remote-fallback pattern as `FallbackEmbeddingProvider`.

### `TerminologyEmbeddingIndexer`

```python
class TerminologyEmbeddingIndexer:
    def __init__(self, session, embedding_provider)
    async def build(self, *, embedding_model: str, batch_size: int,
                    entity_types: set[EntityType] | None = None,
                    source_dbs: set[str] | None = None) -> int
```

Generates embeddings for all imported terminology entries. Deletes stale embeddings before re-generating, batches writes with flush + commit per batch.

### `build_embedding_text(entry: TerminologyEntry) -> str`

Builds deterministic embedding text from `display_name + aliases + external_id + source_db`, deduplicated.

### Data Types (contracts)

| Type | Description |
|------|-------------|
| `EmbeddingBatchResult` | Model, vectors as `tuple[tuple[float, ...], ...]` |
| `RerankItem` | Index, document text, relevance_score |
| `RerankBatchResult` | Model, results as `tuple[RerankItem, ...]` |

## Internal Design

### Two-stage retrieval + rerank

1. **Retrieval**: pgvector cosine similarity returns top-K candidates
2. **Rerank**: cross-encoder (model-server) re-scores candidates against the query
3. **Decision**: score threshold + margin check for confidence

### Error handling

| Exception | Scenario | Handling |
|-----------|----------|----------|
| `NoSemanticMatchFound` | No nearest neighbors found | Returns `UNMAPPED` (normal) |
| `SemanticMatchServiceError` | Network/model-server/DB failure | Raised; hybrid matcher downgrades to precise-only |
| Generic `Exception` | Embedding/rerank infrastructure | Wrapped in `SemanticMatchServiceError` |

`FallbackEmbeddingProvider` and `FallbackRerankProvider` catch all exceptions from the local provider and transparently retry against the remote provider. Only if both fail (or no remote is configured) does the exception propagate to the hybrid matcher's degradation handler.

### Embedding index management

`TerminologyEmbeddingIndexer.build()`:
1. Queries `TerminologyEntry` filtered by `entity_types` and `source_dbs`
2. Deletes stale embeddings for those entries (batched 5000 at a time)
3. Generates embeddings via model-server in batches
4. Upserts into `TerminologyEmbedding` table
5. Commits after each batch (resumable on failure)

## Usage Patterns

### Matching with threshold tuning

```python
config = SimilarityMatchConfig(
    embedding_model="bge-m3",
    rerank_top_k=20,           # wider retrieval for higher recall
    rerank_score_threshold=0.6, # stricter threshold
    min_rerank_margin=0.1,      # wider margin for unambiguous
)
matcher = SimilarityTerminologyMatcher(
    embedding_provider=...,
    rerank_provider=...,
    repository=...,
    config=config,
)
```

### Building embeddings after terminology import

```python
from src.core.standardize_entities_and_align_knowledge.api import (
    build_terminology_embeddings,
)

count = await build_terminology_embeddings(
    cfg=config,
    entity_types={EntityType.GENE, EntityType.DISEASE},
    source_dbs={"HGNC", "OMIM"},
)
print(f"Generated {count} embeddings")
```

### Custom HTTP client (connection reuse)

```python
import httpx
async with httpx.AsyncClient(timeout=30.0) as client:
    emb = ModelServerEmbeddingProvider(
        base_url="http://localhost:8001", model="bge-m3", client=client,
    )
    rerank = ModelServerRerankProvider(
        base_url="http://localhost:8001", model="reranker", client=client,
    )
    # Both providers share the same connection pool
```

### Local-first with remote fallback

```python
from src.core.standardize_entities_and_align_knowledge.similarity_match.providers import (
    FallbackEmbeddingProvider,
    FallbackRerankProvider,
    ModelServerEmbeddingProvider,
    ModelServerRerankProvider,
)

local_emb = ModelServerEmbeddingProvider(base_url="http://localhost:8001", model="Qwen/Qwen3-Embedding-0.6B")
remote_emb = ModelServerEmbeddingProvider(base_url="https://api.siliconflow.cn", model="Qwen/Qwen3-Embedding-0.6B", api_key="sk-...")
embedding = FallbackEmbeddingProvider(local_emb, remote_emb)

# If remote is not configured, pass None — local failures propagate directly
embedding = FallbackEmbeddingProvider(local_emb, None)
```

> **Important:** The remote embedding model **must** match the local model. Persisted pgvector vectors are model-specific — a different model produces incompatible vectors and meaningless cosine similarity scores. A warning is logged at init time and a CRITICAL error at fallback time if models differ. Rerank has no such constraint (stateless scoring).

The `EntityStandardizationService` and `build_terminology_embeddings` automatically construct fallback providers from config when `embedding.remote_base_url` / `rerank.remote_base_url` are set.

## Extension Guide

### Adding a new embedding provider

Implement the interface (duck-typed):

```python
class MyEmbeddingProvider:
    async def embed_texts(self, texts: str | Sequence[str]) -> EmbeddingBatchResult:
        ...
```

### Adding a new rerank provider

Same pattern:

```python
class MyRerankProvider:
    async def rerank(self, query, documents, *, top_k) -> RerankBatchResult:
        ...
```

### Custom vector store

Implement the repository interface used by `find_nearest()`:

```python
class MyVectorRepository:
    async def find_nearest(self, *, entity_type, query_vector, embedding_model, limit) -> list[...]:
        ...
```

## Performance Notes

- Embedding generation: ~100 ms per text (GPU-dependent)
- pgvector cosine search: ~1-5 ms for 100K vectors with IVFFlat index
- Rerank scoring: ~50 ms per query (cross-encoder inference)
- Total per-candidate: ~150 ms (embeddings cached per-document)
- Embedding index build: ~10 min for 100K entries at batch_size=32
- `httpx.AsyncClient` supports connection reuse via `client=` parameter

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `httpx` | Async HTTP client for model-server |
| `sqlalchemy` | pgvector queries, embedding upsert |
| `hashlib` | Embedding text hash for idempotent upsert |
| Parent contracts (`...contracts`) | EntityMatch, StandardizationCandidate |
| `src.dao.postgresql.models` | TerminologyEntry, TerminologyEmbedding ORM |

## Testing

```bash
uv run pytest tests/ -k "similarity_match" -v
```

Tests cover: matcher decision logic, provider HTTP mocking, indexer batch operations, and embedding text construction.
