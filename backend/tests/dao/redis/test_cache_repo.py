"""Tests for Redis cache repository helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────


def _fake_redis_client() -> MagicMock:
    """Return a MagicMock that mimics redis.asyncio.Redis pipeline behavior."""
    client = MagicMock()
    pipeline = MagicMock()

    # pipeline() returns a context-managed pipeline mock.
    pipe_ctx = MagicMock()
    pipe_ctx.__aenter__ = AsyncMock(return_value=pipeline)
    pipe_ctx.__aexit__ = AsyncMock(return_value=None)
    client.pipeline.return_value = pipe_ctx

    # Individual commands.
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.exists = AsyncMock(return_value=0)
    client.expire = AsyncMock(return_value=True)

    # Pipeline commands.
    pipeline.get = MagicMock(return_value=pipeline)
    pipeline.set = MagicMock(return_value=pipeline)
    pipeline.delete = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.exists = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[])

    return client


# ── Cache read tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_document_cache_hit() -> None:
    """Cache returns stored JSON payload for a document key."""
    from src.dao.redis.cache_repo import CacheRepository

    client = _fake_redis_client()
    client.get.return_value = b'{"title": "Test Doc"}'
    repo = CacheRepository(client)

    result = await repo.get_document("doc-123")
    assert result == {"title": "Test Doc"}
    client.get.assert_awaited_once_with("doc:doc-123")


@pytest.mark.asyncio
async def test_get_document_cache_miss() -> None:
    """Cache returns None for an unknown document key."""
    from src.dao.redis.cache_repo import CacheRepository

    client = _fake_redis_client()
    client.get.return_value = None
    repo = CacheRepository(client)

    result = await repo.get_document("doc-456")
    assert result is None


@pytest.mark.asyncio
async def test_set_document_cache() -> None:
    """set_document stores a JSON payload under the doc namespace."""
    from src.dao.redis.cache_repo import CacheRepository

    client = _fake_redis_client()
    repo = CacheRepository(client)

    await repo.set_document("doc-789", {"title": "Stored"}, ttl=300)
    client.set.assert_awaited_once_with("doc:doc-789", '{"title": "Stored"}', ex=300)


@pytest.mark.asyncio
async def test_get_canonical_evidence_cache() -> None:
    """Cache returns stored JSON for a canonical evidence key."""
    from src.dao.redis.cache_repo import CacheRepository

    client = _fake_redis_client()
    client.get.return_value = b'{"field_id": "gene_symbol"}'
    repo = CacheRepository(client)

    result = await repo.get_canonical_evidence("ce-abc")
    assert result == {"field_id": "gene_symbol"}
    client.get.assert_awaited_once_with("canonical:ce-abc")


@pytest.mark.asyncio
async def test_get_entity_cache() -> None:
    """Cache returns stored JSON for an entity key."""
    from src.dao.redis.cache_repo import CacheRepository

    client = _fake_redis_client()
    client.get.return_value = b'{"entity_type": "gene", "display_name": "BRCA1"}'
    repo = CacheRepository(client)

    result = await repo.get_entity("ent-xyz")
    assert result == {"entity_type": "gene", "display_name": "BRCA1"}
    client.get.assert_awaited_once_with("entity:ent-xyz")


# ── Cache invalidation tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalidate_document_uses_pipeline() -> None:
    """Document invalidation deletes all related keys in a single pipeline."""
    from src.dao.redis.cache_repo import CacheRepository

    client = _fake_redis_client()
    pipeline = client.pipeline.return_value.__aenter__.return_value
    repo = CacheRepository(client)

    await repo.invalidate_document("doc-1")

    # All deletes must go through the same pipeline.
    pipeline.delete.assert_any_call("doc:doc-1")
    # The plan says invalidation must batch namespace deletes together.
    pipeline.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalidate_canonical_uses_pipeline() -> None:
    """Canonical evidence invalidation uses a single pipeline for deletes."""
    from src.dao.redis.cache_repo import CacheRepository

    client = _fake_redis_client()
    pipeline = client.pipeline.return_value.__aenter__.return_value
    repo = CacheRepository(client)

    await repo.invalidate_canonical_evidence("ce-42")

    pipeline.delete.assert_any_call("canonical:ce-42")
    pipeline.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalidate_entity_uses_pipeline() -> None:
    """Entity invalidation uses a single pipeline for deletes."""
    from src.dao.redis.cache_repo import CacheRepository

    client = _fake_redis_client()
    pipeline = client.pipeline.return_value.__aenter__.return_value
    repo = CacheRepository(client)

    await repo.invalidate_entity("ent-77")

    pipeline.delete.assert_any_call("entity:ent-77")
    pipeline.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_bulk_invalidate_uses_single_pipeline() -> None:
    """Bulk invalidation of multiple namespaces uses ONE pipeline, not separate DEL calls."""
    from src.dao.redis.cache_repo import CacheRepository

    client = _fake_redis_client()
    pipeline = client.pipeline.return_value.__aenter__.return_value
    repo = CacheRepository(client)

    await repo.invalidate_all(
        document_ids=["doc-a", "doc-b"],
        entity_ids=["ent-x"],
    )

    # Pipeline must contain all deletes.
    delete_calls = [c.args[0] for c in pipeline.delete.call_args_list]
    assert "doc:doc-a" in delete_calls
    assert "doc:doc-b" in delete_calls
    assert "entity:ent-x" in delete_calls

    # Only one pipeline.execute() call.
    pipeline.execute.assert_awaited_once()

    # No standalone client.delete() calls (partial invalidation must not happen).
    client.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalidate_all_no_ids_is_noop() -> None:
    """Passing no IDs to invalidate_all is a no-op (no pipeline created)."""
    from src.dao.redis.cache_repo import CacheRepository

    client = _fake_redis_client()
    repo = CacheRepository(client)

    await repo.invalidate_all()

    # Pipeline should not be created for empty invalidation.
    client.pipeline.assert_not_called()


# ── No token/session namespace tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_repo_has_no_token_or_session_helpers() -> None:
    """CacheRepository must not expose token or session cache methods."""
    from src.dao.redis.cache_repo import CacheRepository

    public_methods = [m for m in dir(CacheRepository) if not m.startswith("_")]
    for keyword in ("token", "session", "auth"):
        assert not any(keyword in m.lower() for m in public_methods), (
            f"CacheRepository must not contain token/session methods: found {keyword}"
        )


@pytest.mark.asyncio
async def test_cache_key_prefixes_are_expected() -> None:
    """Cache key prefixes match the expected MVP namespaces."""
    from src.dao.redis.cache_repo import CACHE_PREFIX

    assert CACHE_PREFIX["document"] == "doc"
    assert CACHE_PREFIX["canonical"] == "canonical"
    assert CACHE_PREFIX["entity"] == "entity"
    assert CACHE_PREFIX["search"] == "search"


# ── Integration test (skip when Redis is unavailable) ───────────────────────


@pytest.mark.skip(reason="Requires a running Redis instance")
@pytest.mark.asyncio
async def test_real_redis_read_and_invalidate() -> None:
    """End-to-end read/write/invalidate against a real Redis instance."""
    import redis.asyncio as aioredis

    from src.core.config import Settings
    from src.dao.redis.cache_repo import CacheRepository

    settings = Settings()
    client = aioredis.Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        password=settings.redis.password or None,
        db=settings.redis.db,
    )
    repo = CacheRepository(client)

    # Write
    await repo.set_document("int-doc", {"integ": True}, ttl=60)

    # Read
    result = await repo.get_document("int-doc")
    assert result == {"integ": True}

    # Invalidate
    await repo.invalidate_document("int-doc")
    result = await repo.get_document("int-doc")
    assert result is None

    await client.aclose()
