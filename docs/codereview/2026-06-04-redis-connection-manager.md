# Code Review: Redis Connection Manager Implementation Plan

- **Document**: `docs/plans/2026-06-04-redis-connection-manager.md`
- **Date**: 2026-06-04
- **Reviewer**: AI Agent
- **Scope**: Plan review — implementation plan for `backend/src/dao/redis/connection.py` + wiring lifecycle. 8 tasks, ~10 files changed/created.

## Summary Decision

🔄 Request changes — 2 blocking issues, 3 important issues.

---

## Findings

### 🔴 [blocking] Task 6 is a no-op — `.env.example` already has Redis vars

**File**: Task 6 in plan (line 466–499), `database/config/.env.example`

The plan's "Current State" table claims the file "Needs REDIS_* vars" (line 24), and Task 6 proposes adding a Redis section. However, `database/config/.env.example:15-20` already contains:

```bash
# ── Redis ─────────────────────────────────────────────────────────────
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0
REDIS_MAX_CONNECTIONS=20
```

**Impact**: Task 6 would either produce a duplicate section or waste effort on an already-completed item.

**Recommendation**: Drop Task 6 entirely. Optionally, update the plan's "Current State" table row 24 from "Needs REDIS_* vars" to "Done" so the state tracking is accurate.

---

### 🔴 [blocking] Task 1 tests are vacuous — `test_build_redis_client_passwordless` and `test_build_redis_client_custom_db` don't verify the behavior they claim

**File**: Task 1 Step 1 test code (plan lines 79–111)

Both tests only assert `client is not None`, which provides zero confidence that `password` was set to `None` or that `db=3` was actually passed to `redis.asyncio.Redis`. A `build_redis_client()` that hardcodes `password="secret"` and `db=0` would pass these tests.

**Recommendation**: Verify the actual connection parameters. For example:

```python
def test_build_redis_client_passwordless() -> None:
    fake_cfg = MagicMock()
    fake_cfg.redis.host = "localhost"
    fake_cfg.redis.port = 6379
    fake_cfg.redis.password = ""
    fake_cfg.redis.db = 0
    fake_cfg.redis.max_connections = 20

    with patch("src.dao.redis.connection.get_config", return_value=fake_cfg):
        with patch("src.dao.redis.connection.aioredis.Redis") as mock_redis_cls:
            build_redis_client()

    mock_redis_cls.assert_called_once_with(
        host="localhost", port=6379,
        password=None, db=0, max_connections=20,
        decode_responses=False,
    )
```

The same pattern should apply to `test_build_redis_client_custom_db`. The first test (`test_build_redis_client_returns_client`) is acceptable as a smoke test, but add `assert isinstance(...)` there too and verify the key connection parameters.

---

### 🟡 [important] Missing import for `Redis` type alias in `wiring.py` — plan references `AsyncRedis` but actual import line is ambiguous

**File**: Task 2 (plan lines 213–215), `backend/src/api/wiring.py`

The plan says to add `from redis.asyncio import Redis as AsyncRedis` at the top of `wiring.py`. However:

1. The current `wiring.py` imports `AsyncEngine` and `AsyncSession` from SQLAlchemy — naming the Redis import `AsyncRedis` is a reasonable convention but shouldn't be confused with SQLAlchemy's types.
2. The plan's `wire_dependencies()` change (line 241) does `from src.dao.redis.connection import build_redis_client` lazily inside the function, not at module level. This is inconsistent with how the PG engine builder is imported at module level (line 7 of `wiring.py`).

**Recommendation**: Move the Redis import to module level alongside the PG imports for consistency:

```python
from redis.asyncio import Redis as AsyncRedis
from src.dao.redis.connection import build_redis_client
```

Then `wire_dependencies()` can call `build_redis_client(cfg)` without a lazy import. Follow the existing PG pattern exactly.

---

### 🟡 [important] Shutdown order: `dispose_redis()` should be after `dispose_engine()`, not before

**File**: Task 3 (plan lines 307–314), `backend/app/main.py`

The plan places `await dispose_redis()` before `await dispose_engine()` in the `finally` block. In the current code, Phase4Factory (which may use Redis via cache_repo) is closed in the `try` block before `finally`. If any future code uses Redis during Phase4Factory disposal, disposing Redis first would break that.

More importantly, the PostgreSQL engine is disposed last — which follows the common pattern of disposing resources in reverse initialization order. Since Redis is initialized during `wire_dependencies()` (Task 2) at the same time as PG, and the PG engine was conceptually initialized first (line 83 before the Redis addition), Redis should be disposed *before* PG — so the plan's order is actually correct for LIFO.

**Verdict**: The order is correct (LIFO: Redis is initialized after PG in `wire_dependencies()`, so disposed before). However, the plan should document this rationale.

---

### 🟡 [important] Integration test uses brittle `app.router.lifespan_context()` API

**File**: Task 3 Step 1 test (plan lines 269–291)

The test uses `async with app.router.lifespan_context(app):` which is Starlette-internal and not part of the public API. The existing integration test (`test_app_startup.py`) uses `AsyncClient` with `ASGITransport`, which triggers lifespan properly through the public interface.

**Recommendation**: Follow the existing test pattern. Use `AsyncClient` with `ASGITransport`, mock `dispose_redis` at the module level, and verify it's called. Alternatively, if the internal API is acceptable for this test (it's already testing internals), at minimum add a comment noting the API is Starlette-internal.

---

### 💬 [comment] Rate limiter still creates throwaway sync clients — worth noting why

**File**: `backend/src/api/rate_limit.py:51-58`

The plan explicitly excludes `rate_limit.py` (line 564: "separate concern, works independently"). This is defensible — the rate limiter uses a sync `redis.Redis` client (slowapi `RedisStorage` requires sync), and the new singleton is async `redis.asyncio.Redis`. However, the current code creates a throwaway sync client on *every* rate-limited request to test connectivity (lines 51-58), then immediately closes it.

**Recommendation**: Add a one-sentence note in the plan's "Not changed (intentionally)" section explaining the sync/async incompatibility prevents reuse, and that the throwaway client is acceptable for now (Redis is local/fast, and rate-limited endpoints are infrequent).

---

### 💬 [comment] `decode_responses=False` should be documented with rationale

**File**: Task 1 `connection.py` (plan line 153)

Setting `decode_responses=False` means all values returned from Redis are `bytes`, not `str`. The `cache_repo.py` uses `json.loads`/`json.dumps` which work with bytes, so this is correct. But a future developer adding a new Redis consumer might expect string responses and get `bytes` back.

**Recommendation**: Add a comment in `connection.py` explaining the choice:

```python
# decode_responses=False: cache_repo stores JSON as bytes;
# consumers that need str responses should decode explicitly.
```

---

### 💬 [comment] Plan references absolute path `backend/tests/...` but commands use relative `cd backend`

**File**: Throughout plan (e.g., lines 116, 159, 206, 247, 296, 389, 408, 448, 454, 529, 534)

All test commands start with `cd backend && uv run pytest ...`. This is correct given the monorepo structure.

---

### 💬 [comment] Task 5 `__init__.py` update: `TypedDict` import is missing in plan example but present in actual file

**File**: Task 5 (plan lines 413–445), `backend/src/dao/redis/__init__.py`

The plan's proposed `__init__.py` drops `TYPED_CHECKING` block additions without showing the full file. The actual file at line 5 already has `from typing import TYPE_CHECKING`. The plan correctly adds `build_redis_client` to the `TYPE_CHECKING` block and `_LAZY_IMPORTS` dict. No issue — just noting the plan correctly handles the lazy-import pattern.

---

## Verification

Manual verification of claims against actual code:

| Plan Claim | File | Actual State | Match? |
|---|---|---|---|
| Config model "Done" | `config.py:129-136` | `RedisConfig` class exists with all 5 fields | ✅ |
| `.env.example` "Needs REDIS_* vars" | `.env.example:15-20` | Already has Redis vars | ❌ (see 🔴 above) |
| `wiring.py` "No Redis client" | `wiring.py:1-10` | Only PG singletons, no Redis | ✅ |
| `health.py` "Creates throwaway client" | `health.py:74-95` | Creates + closes `aioredis.Redis` inline | ✅ |
| `cache_repo.py` "Done (DI)" | `cache_repo.py:32-166` | Accepts `aioredis.Redis` in constructor | ✅ |
| `redis>=5.0.0` in deps | `pyproject.toml` | Present | ✅ (confirmed in plan) |

---

## Summary of Required Changes

1. **Drop Task 6** (`database/config/.env.example` is already done).
2. **Rewrite Task 1 tests** to verify actual connection parameters passed to `redis.asyncio.Redis`, not just `client is not None`.
3. **Move Redis import to module level** in `wiring.py` for consistency with PG imports (Task 2).
4. **Use public lifespan API** in the integration test, or document the Starlette-internal API usage (Task 3).
5. **Add rationale comment** for `decode_responses=False` (Task 1) and for rate limiter exclusion (plan summary).
