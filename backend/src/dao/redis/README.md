# Redis DAO

> Async Redis cache layer for read-model acceleration. Stores JSON payloads under namespaced keys with transactional invalidation to prevent stale cache.

## Quick Start

```python
from src.api.wiring import get_redis_client
from src.dao.redis.cache_repo import CacheRepository

# Use the wiring singleton -- already configured from application settings
client = get_redis_client()
cache = CacheRepository(client)

# Cache a document payload
await cache.set_document("doc-123", {"title": "BRCA1 study", "status": "processed"})

# Read it back
doc = await cache.get_document("doc-123")

# Invalidate after mutation
await cache.invalidate_all(document_ids=["doc-123"])
```

> **Tip:** Only create a client manually (via `build_redis_client()`) in standalone scripts or tests that do not go through the FastAPI lifespan. In application code always prefer the wiring singleton.

## Architecture

```
src/dao/redis/
├── __init__.py       # Lazy imports via __getattr__
├── connection.py     # build_redis_client() -- pure builder, no singleton state
└── cache_repo.py     # CacheRepository -- get/set/invalidate for documents, evidence, entities
```

## Public API

### `build_redis_client(settings=None)`

Located in `connection.py`. Builds a `redis.asyncio.Redis` client from application config. Returns a connection-pooled client with `decode_responses=False` (JSON payloads stored/retrieved as raw bytes).

```python
from src.dao.redis.connection import build_redis_client

# Uses get_config() when no settings provided
client = build_redis_client()
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `settings` | `Settings \| None` | `None` | Optional config override; falls back to `get_config()` |

### `CacheRepository`

Constructed with a `redis.asyncio.Redis` client instance.

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_document` | `async (document_id: str) -> dict \| None` | Read cached document payload |
| `set_document` | `async (document_id, value, ttl=3600) -> None` | Cache document under `doc:<id>` |
| `get_canonical_evidence` | `async (id: str) -> dict \| None` | Read cached evidence payload |
| `set_canonical_evidence` | `async (id, value, ttl=3600) -> None` | Cache evidence under `canonical:<id>` |
| `get_entity` | `async (entity_id: str) -> dict \| None` | Read cached entity payload |
| `set_entity` | `async (entity_id, value, ttl=3600) -> None` | Cache entity under `entity:<id>` |
| `invalidate_document` | `async (document_id) -> None` | Remove cached document |
| `invalidate_canonical_evidence` | `async (id) -> None` | Remove cached evidence |
| `invalidate_entity` | `async (entity_id) -> None` | Remove cached entity |
| `invalidate_all` | `async (document_ids?, evidence_ids?, entity_ids?) -> None` | Transactional bulk invalidation |

### Key Namespaces

| Prefix | Key Format | Content |
|--------|-----------|---------|
| `doc` | `doc:<document_id>` | Document cache payload |
| `canonical` | `canonical:<evidence_id>` | Canonical evidence payload |
| `entity` | `entity:<entity_id>` | Entity cache payload |

## Connection Lifecycle

```
connection.py          wiring.py                   main.py lifespan
─────────────         ──────────                   ────────────────
build_redis_client() → get_redis_client() singleton → dispose_redis() on shutdown
```

1. **`connection.py`** -- Pure builder. `build_redis_client(settings)` reads config and returns a new `redis.asyncio.Redis` instance. Holds no state.
2. **`src/api/wiring.py`** -- Holds the module-level `_redis_client` singleton. `wire_dependencies()` calls `build_redis_client()` once during startup. `get_redis_client()` returns the singleton (or `None` before wiring). `dispose_redis()` calls `aclose()` and clears the reference.
3. **`app/main.py` lifespan** -- Calls `wire_dependencies()` on startup. On shutdown, calls `dispose_redis()` (and `dispose_engine()`) to release resources.
4. **Health checks** -- `src/utils/health.py` imports `get_redis_client` from wiring and runs a `PING` against the existing singleton. No second client is created.

## Internal Design

### Transactional Invalidation

`invalidate_all()` collects all affected keys before opening one Redis `pipeline(transaction=True)`. This prevents partial invalidation if the network fails between separate delete commands.

### Lazy Imports

`__init__.py` uses `__getattr__`-based lazy imports to avoid eagerly loading `redis.asyncio` when only the connection helpers or cache repository are needed.

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `redis.asyncio` | Async Redis client |

## Testing

```bash
cd backend
uv run pytest tests/dao/redis/ -v
```

Integration tests requiring live Redis are marked skipped by default.
