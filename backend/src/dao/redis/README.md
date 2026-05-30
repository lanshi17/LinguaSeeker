# Redis DAO

> Async Redis cache layer for read-model acceleration. Stores JSON payloads under namespaced keys with transactional invalidation to prevent stale cache.

## Quick Start

```python
import redis.asyncio as aioredis
from src.dao.redis.cache_repo import CacheRepository

client = aioredis.from_url("redis://localhost:6379")
cache = CacheRepository(client)

# Cache a document payload
await cache.set_document("doc-123", {"title": "BRCA1 study", "status": "processed"})

# Read it back
doc = await cache.get_document("doc-123")

# Invalidate after mutation
await cache.invalidate_all(document_ids=["doc-123"])
```

## Architecture

```
src/dao/redis/
├── __init__.py       # Lazy imports via __getattr__
└── cache_repo.py     # CacheRepository — get/set/invalidate for documents, evidence, entities
```

## Public API

### `CacheRepository`

Constructed with an `redis.asyncio.Redis` client instance.

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

## Internal Design

### Transactional Invalidation

`invalidate_all()` collects all affected keys before opening one Redis `pipeline(transaction=True)`. This prevents partial invalidation if the network fails between separate delete commands.

### Lazy Imports

`__init__.py` uses `__getattr__`-based lazy imports to avoid eagerly loading `redis.asyncio` when only the models or connection helpers are needed.

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `REDIS_HOST` | `localhost` | Redis server host |
| `REDIS_PORT` | `6379` | Redis server port |
| `REDIS_PASSWORD` | `""` | Auth password |
| `REDIS_DB` | `0` | Database number |
| `REDIS_MAX_CONNECTIONS` | `20` | Connection pool size |

## Testing

```bash
cd backend
uv run pytest tests/dao/redis/ -v
```

Integration tests requiring live Redis are marked skipped by default.

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `redis.asyncio` | Async Redis client |
| `loguru` | Structured logging |
