# Redis Connection Manager Implementation Plan

**Status:** completed
**Created:** 2026-06-04
**Completed:** 2026-06-04

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a centralized async Redis client singleton to `backend/src/dao/redis/`, matching the PostgreSQL `connection.py` + `wiring.py` lifecycle pattern, so that health checks, cache repo, and future consumers share one managed connection pool with proper startup/shutdown.

**Architecture:** Follow the existing PostgreSQL DAO pattern — `connection.py` builds the client, `wiring.py` holds the singleton, `main.py` lifespan disposes on shutdown. The health check reuses the singleton client instead of creating throwaway connections. The rate limiter keeps its own sync client (slowapi requirement).

**Tech Stack:** Python 3.12+, `redis>=5.0.0` (`redis.asyncio`), FastAPI lifespan, pydantic-settings, pytest + pytest-asyncio

---

## Current State

| Component | File | Status |
|-----------|------|--------|
| Config model | `backend/src/core/config.py:129-136, 327-332, 516-522` | Done |
| Cache repository | `backend/src/dao/redis/cache_repo.py` | Done (accepts client via DI) |
| Lazy init | `backend/src/dao/redis/__init__.py` | Done |
| Health check | `backend/src/utils/health.py:74-95` | **Creates throwaway client** |
| Rate limiter | `backend/src/api/rate_limit.py:51-58` | **Creates throwaway sync client** |
| Startup/shutdown | `backend/app/main.py:62-105` | **No Redis teardown** |
| Wiring singleton | `backend/src/api/wiring.py` | **No Redis client** |
| DB config env | `database/config/.env.example:15-20` | Done (Redis vars present) |
| Tests | `backend/tests/dao/redis/test_cache_repo.py` | Done |
| Dependency | `backend/pyproject.toml` | `redis>=5.0.0` present |

## What Changes

1. New file `backend/src/dao/redis/connection.py` — builds async Redis client (mirrors `postgresql/connection.py`)
2. Update `backend/src/api/wiring.py` — hold Redis singleton, expose `get_redis_client()` / `dispose_redis()`
3. Update `backend/app/main.py` — call `dispose_redis()` in lifespan shutdown
4. Update `backend/src/utils/health.py` — reuse singleton client via `get_redis_client()`
5. Update `backend/src/dao/redis/__init__.py` — export new connection helpers
6. New test `backend/tests/dao/redis/test_connection.py`
7. Update existing health test to match new behavior

---

### Task 1: Create `backend/src/dao/redis/connection.py`

**Files:**
- Create: `backend/src/dao/redis/connection.py`
- Ref: `backend/src/dao/postgresql/connection.py` (pattern to follow)

**Step 1: Write the failing test**

Create `backend/tests/dao/redis/test_connection.py`:

```python
"""Tests for Redis connection helpers."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_build_redis_client_passes_config_params() -> None:
    """build_redis_client forwards all config values to redis.asyncio.Redis."""
    from src.dao.redis.connection import build_redis_client

    fake_cfg = MagicMock()
    fake_cfg.redis.host = "127.0.0.1"
    fake_cfg.redis.port = 6380
    fake_cfg.redis.password = "s3cret"
    fake_cfg.redis.db = 2
    fake_cfg.redis.max_connections = 10

    with (
        patch("src.dao.redis.connection.get_config", return_value=fake_cfg),
        patch("src.dao.redis.connection.aioredis.Redis") as mock_cls,
    ):
        build_redis_client()

    mock_cls.assert_called_once_with(
        host="127.0.0.1",
        port=6380,
        password="s3cret",
        db=2,
        max_connections=10,
        decode_responses=False,
    )


def test_build_redis_client_passwordless() -> None:
    """build_redis_client converts empty password string to None."""
    from src.dao.redis.connection import build_redis_client

    fake_cfg = MagicMock()
    fake_cfg.redis.host = "localhost"
    fake_cfg.redis.port = 6379
    fake_cfg.redis.password = ""
    fake_cfg.redis.db = 0
    fake_cfg.redis.max_connections = 20

    with (
        patch("src.dao.redis.connection.get_config", return_value=fake_cfg),
        patch("src.dao.redis.connection.aioredis.Redis") as mock_cls,
    ):
        build_redis_client()

    mock_cls.assert_called_once_with(
        host="localhost",
        port=6379,
        password=None,  # empty string coerced to None
        db=0,
        max_connections=20,
        decode_responses=False,
    )


def test_build_redis_client_custom_db() -> None:
    """build_redis_client passes custom db number to Redis constructor."""
    from src.dao.redis.connection import build_redis_client

    fake_cfg = MagicMock()
    fake_cfg.redis.host = "redis.example.com"
    fake_cfg.redis.port = 6379
    fake_cfg.redis.password = "pw"
    fake_cfg.redis.db = 3
    fake_cfg.redis.max_connections = 5

    with (
        patch("src.dao.redis.connection.get_config", return_value=fake_cfg),
        patch("src.dao.redis.connection.aioredis.Redis") as mock_cls,
    ):
        build_redis_client()

    _, kwargs = mock_cls.call_args
    assert kwargs["db"] == 3
    assert kwargs["host"] == "redis.example.com"
    assert kwargs["max_connections"] == 5


def test_build_redis_client_uses_settings_param() -> None:
    """build_redis_client accepts explicit Settings, skipping get_config()."""
    from src.dao.redis.connection import build_redis_client

    fake_cfg = MagicMock()
    fake_cfg.redis.host = "custom-host"
    fake_cfg.redis.port = 6379
    fake_cfg.redis.password = ""
    fake_cfg.redis.db = 0
    fake_cfg.redis.max_connections = 10

    with patch("src.dao.redis.connection.aioredis.Redis") as mock_cls:
        build_redis_client(settings=fake_cfg)

    _, kwargs = mock_cls.call_args
    assert kwargs["host"] == "custom-host"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/dao/redis/test_connection.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.dao.redis.connection'`

**Step 3: Write minimal implementation**

Create `backend/src/dao/redis/connection.py`:

```python
"""Async Redis client builder.

Mirrors the PostgreSQL ``connection.py`` pattern: a pure builder function
that creates a ``redis.asyncio.Redis`` client from application config.
The singleton lifecycle is managed by ``src.api.wiring``.
"""
from __future__ import annotations

import redis.asyncio as aioredis

from src.core.config import Settings, get_config


def build_redis_client(settings: Settings | None = None) -> aioredis.Redis:
    """Build an async Redis client from application settings.

    Args:
        settings: Optional settings override. Uses ``get_config()`` when None.

    Returns:
        A ``redis.asyncio.Redis`` client configured with connection pooling.
    """
    cfg = settings or get_config()
    # decode_responses=False: cache_repo stores/retrieves JSON as raw bytes
    # via json.dumps/json.loads.  Consumers that need str should decode
    # explicitly — keep the default safe for binary payloads.
    return aioredis.Redis(
        host=cfg.redis.host,
        port=cfg.redis.port,
        password=cfg.redis.password or None,
        db=cfg.redis.db,
        max_connections=cfg.redis.max_connections,
        decode_responses=False,
    )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/dao/redis/test_connection.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add backend/src/dao/redis/connection.py backend/tests/dao/redis/test_connection.py
git commit -m "feat(redis): add connection.py builder for async Redis client"
```

---

### Task 2: Wire Redis singleton into `wiring.py`

**Files:**
- Modify: `backend/src/api/wiring.py`
- Ref: Same file's `_engine` / `_session_factory` / `dispose_engine()` pattern

**Step 1: Write the failing test**

Add to `backend/tests/dao/redis/test_connection.py`:

```python
def test_get_redis_client_returns_none_before_init() -> None:
    """get_redis_client returns None before wire_dependencies runs."""
    import src.api.wiring as wiring

    # Force-reset the module singleton
    wiring._redis_client = None
    assert wiring.get_redis_client() is None


@pytest.mark.asyncio
async def test_dispose_redis_closes_client() -> None:
    """dispose_redis closes the client and resets the singleton."""
    import src.api.wiring as wiring

    mock_client = AsyncMock()
    wiring._redis_client = mock_client

    await wiring.dispose_redis()
    mock_client.aclose.assert_awaited_once()
    assert wiring._redis_client is None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/dao/redis/test_connection.py -v`
Expected: FAIL — `AttributeError: module 'src.api.wiring' has no attribute '_redis_client'`

**Step 3: Implement the wiring changes**

In `backend/src/api/wiring.py`, add the Redis import at module level (alongside the PG imports on line 7):

```python
from redis.asyncio import Redis as AsyncRedis
from src.dao.redis.connection import build_redis_client
```

Add new singleton + accessor/disposal functions after the existing `_engine` / `_session_factory` block:

```python
_redis_client: AsyncRedis | None = None


def get_redis_client() -> AsyncRedis | None:
    """Return the singleton async Redis client (or None if not yet initialized)."""
    return _redis_client


async def dispose_redis() -> None:
    """Teardown the Redis client (called from lifespan shutdown)."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
```

In `wire_dependencies()`, add Redis client initialization right after `cfg = get_config()` (line 82):

```python
    # ── Redis client singleton ───────────────────────────────────────
    global _redis_client
    _redis_client = build_redis_client(cfg)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/dao/redis/test_connection.py -v`
Expected: 6 passed

**Step 5: Commit**

```bash
git add backend/src/api/wiring.py backend/tests/dao/redis/test_connection.py
git commit -m "feat(redis): wire Redis client singleton into application lifecycle"
```

---

### Task 3: Add Redis teardown to lifespan shutdown

**Files:**
- Modify: `backend/app/main.py:94-105`

**Step 1: Write the failing test**

In `backend/tests/integration/test_app_startup.py`, add a test following the existing `AsyncClient` + `ASGITransport` pattern (no Starlette-internal APIs):

```python
@pytest.mark.asyncio
async def test_lifespan_disposes_redis_on_shutdown() -> None:
    """Lifespan shutdown disposes both the Redis client and the PG engine."""
    from unittest.mock import AsyncMock, patch

    with (
        patch("src.api.wiring.wire_dependencies"),
        patch("src.api.wiring.dispose_engine", new_callable=AsyncMock) as mock_dispose_pg,
        patch("src.api.wiring.dispose_redis", new_callable=AsyncMock) as mock_dispose_redis,
        patch(
            "src.utils.health.check_all_connections",
            new_callable=AsyncMock,
            return_value=HealthResult(postgres=True, redis=True),
        ),
        patch("src.api.rate_limit.init_limiter"),
        patch("src.core.config.get_config") as mock_cfg,
    ):
        from src.core.config import Settings
        mock_cfg.return_value = Settings()

        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test"):
            pass  # exiting context manager triggers lifespan shutdown

    mock_dispose_pg.assert_awaited_once()
    mock_dispose_redis.assert_awaited_once()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/integration/test_app_startup.py::test_lifespan_disposes_redis_on_shutdown -v`
Expected: FAIL — `dispose_redis` not called

**Step 3: Implement lifespan change**

In `backend/app/main.py`, modify the shutdown section (lines 96-105). Add `dispose_redis` import alongside `dispose_engine` on line 77:

```python
    from src.api.wiring import wire_dependencies, dispose_engine, dispose_redis
```

Add `await dispose_redis()` before `await dispose_engine()` in the shutdown `finally` block:

```python
    finally:
        await dispose_redis()
        await dispose_engine()
        logger.info("Lingua Seekerbackend stopped")
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/integration/test_app_startup.py -v`
Expected: all passed

**Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/integration/test_app_startup.py
git commit -m "feat(redis): add dispose_redis to lifespan shutdown"
```

---

### Task 4: Refactor health check to reuse singleton client

**Files:**
- Modify: `backend/src/utils/health.py:74-95`
- Modify: `backend/tests/utils/test_health.py`

**Step 1: Write the failing test**

Update `backend/tests/utils/test_health.py` to verify the health check uses the wiring singleton instead of creating a new client. Review the existing test file first, then adjust the Redis mock to target `src.api.wiring.get_redis_client`.

```python
@pytest.mark.asyncio
async def test_check_redis_uses_wiring_singleton() -> None:
    """Health check reuses the wiring Redis singleton, not a throwaway client."""
    from unittest.mock import AsyncMock, patch

    mock_client = AsyncMock()
    mock_client.ping.return_value = True

    with patch("src.api.wiring.get_redis_client", return_value=mock_client):
        from src.utils.health import _check_redis
        result = await _check_redis()

    assert result is True
    mock_client.ping.assert_awaited_once()
    # Must NOT close the singleton client
    mock_client.aclose.assert_not_awaited()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/utils/test_health.py -v`
Expected: FAIL — current `_check_redis` creates its own client, doesn't call `get_redis_client`

**Step 3: Refactor `_check_redis`**

Replace the entire `_check_redis` function in `backend/src/utils/health.py`:

```python
@_register("redis")
async def _check_redis() -> bool:
    """Ping Redis using the wiring singleton client."""
    logger = get_logger()
    try:
        from src.api.wiring import get_redis_client

        client = get_redis_client()
        if client is None:
            logger.warning("Redis health check skipped: client not initialized")
            return False
        pong = await client.ping()
        return bool(pong)
    except Exception as exc:
        logger.warning("Redis health check failed: {}", exc)
        return False
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/utils/test_health.py -v`
Expected: all passed

**Step 5: Commit**

```bash
git add backend/src/utils/health.py backend/tests/utils/test_health.py
git commit -m "refactor(redis): reuse wiring singleton in health check"
```

---

### Task 5: Update `__init__.py` exports

**Files:**
- Modify: `backend/src/dao/redis/__init__.py`

**Step 1: Verify current exports work**

Run: `cd backend && uv run pytest tests/dao/redis/test_cache_repo.py -v`
Expected: all passed (baseline)

**Step 2: Add connection helpers to lazy imports**

Update `backend/src/dao/redis/__init__.py` to export `build_redis_client`:

```python
"""Redis data access layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.dao.redis.cache_repo import CACHE_PREFIX, CacheRepository
    from src.dao.redis.connection import build_redis_client

__all__ = ["CACHE_PREFIX", "CacheRepository", "build_redis_client"]

# Module-level mapping for lazy imports to avoid recreating dict on every access
_LAZY_IMPORTS: dict[str, str] = {
    "CACHE_PREFIX": "src.dao.redis.cache_repo",
    "CacheRepository": "src.dao.redis.cache_repo",
    "build_redis_client": "src.dao.redis.connection",
}


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    """Lazy-load exports to avoid eager redis.asyncio dependency."""
    import importlib

    if name in _LAZY_IMPORTS:
        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

**Step 3: Run all Redis tests**

Run: `cd backend && uv run pytest tests/dao/redis/ -v`
Expected: all passed

**Step 4: Run linter**

Run: `cd backend && uv run ruff check src/dao/redis/ tests/dao/redis/`
Expected: no violations

**Step 5: Commit**

```bash
git add backend/src/dao/redis/__init__.py
git commit -m "feat(redis): export build_redis_client from dao.redis"
```

---

### Task 6: Update Redis DAO README

**Files:**
- Modify: `backend/src/dao/redis/README.md`

**Step 1: Update architecture section and add connection management docs**

Update the README to document the new `connection.py` and the wiring singleton pattern. Key changes:

- Add `connection.py` to the architecture tree
- Document `build_redis_client()` in the Public API section
- Add a "Connection Lifecycle" section explaining the wiring singleton pattern
- Update the Quick Start to prefer the wiring singleton over manual client creation

**Step 2: Commit**

```bash
git add backend/src/dao/redis/README.md
git commit -m "docs(redis): update README with connection manager docs"
```

---

### Task 7: Run full test suite and lint

**Step 1: Run all backend tests**

Run: `cd backend && uv run pytest -v`
Expected: all passed

**Step 2: Run linter on all changed files**

Run: `cd backend && uv run ruff check src/dao/redis/ src/api/wiring.py src/utils/health.py app/main.py tests/dao/redis/ tests/utils/test_health.py tests/integration/test_app_startup.py`
Expected: no violations

**Step 3: Fix any lint violations if found**

**Step 4: Final commit if any fixes needed**

```bash
git add -u
git commit -m "fix(redis): resolve lint violations in connection manager"
```

---

## Summary of Changes

| File | Action | Lines (approx) |
|------|--------|----------------|
| `backend/src/dao/redis/connection.py` | **Create** | ~30 |
| `backend/src/dao/redis/__init__.py` | Modify | +3 exports |
| `backend/src/api/wiring.py` | Modify | +20 (singleton + dispose) |
| `backend/app/main.py` | Modify | +3 (import + dispose call) |
| `backend/src/utils/health.py` | Modify | ~15 (reuse singleton) |
| `backend/src/dao/redis/README.md` | Modify | docs update |
| `backend/tests/dao/redis/test_connection.py` | **Create** | ~80 |
| `backend/tests/utils/test_health.py` | Modify | +1 test |
| `backend/tests/integration/test_app_startup.py` | Modify | +1 test |

**Not changed (intentionally):**
- `backend/src/api/rate_limit.py` — uses sync `redis.Redis()` for slowapi `RedisStorage` (sync API required by slowapi; cannot reuse the async singleton). The throwaway sync client on `init_limiter()` is acceptable: Redis is local and the test runs once at startup, not per-request.
- `backend/src/core/config.py` — already complete
- `backend/src/dao/redis/cache_repo.py` — already uses DI, no changes needed
- `backend/pyproject.toml` — `redis>=5.0.0` already declared
- `database/config/.env.example` — already has `REDIS_*` vars at lines 15-20
