"""Tests for document processing cache service (L1 Redis + L2 PostgreSQL).

Tests cover:
  - Content hash computation (bytes, text, file, online key, scope key).
  - Cache lookup: L1 hit, L2 hit with L1 backfill, miss.
  - Cache write: L2 upsert + L1 set.
  - Graceful degradation when Redis or PostgreSQL fails.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.contracts import (
    PipelineGraphState,
    PipelineMode,
    PipelineStatus,
    SourceType,
)
from src.agents.content_hash import (
    compute_content_hash,
    compute_hash_from_bytes,
    compute_hash_from_file,
    compute_hash_from_text,
)
from src.agents.processing_cache import (
    CacheLookupResult,
    DocumentProcessingCacheService,
)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def sample_state() -> PipelineGraphState:
    """A completed pipeline state for cache testing."""
    return PipelineGraphState(
        processing_run_id="550e8400-e29b-41d4-a716-446655440000",
        source_document_id="660e8400-e29b-41d4-a716-446655440001",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        source_key="test.pdf",
        pipeline_status=PipelineStatus.COMPLETED,
        created_at="2026-06-22T10:00:00",
        started_at="2026-06-22T10:00:01",
        completed_at="2026-06-22T10:05:00",
    )


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    return redis


@pytest.fixture
def mock_session_factory():
    """Mock async session factory."""
    factory = MagicMock()
    return factory


@pytest.fixture
def cache_service(mock_redis, mock_session_factory):
    """CacheService with mocked dependencies."""
    return DocumentProcessingCacheService(
        redis_client=mock_redis,
        session_factory=mock_session_factory,
    )


# ── Content hash tests ────────────────────────────────────────────────────


class TestContentHash:
    """Tests for content hash computation utilities."""

    def test_hash_from_bytes_deterministic(self):
        """Same bytes produce the same hash."""
        h1 = compute_hash_from_bytes(b"hello world")
        h2 = compute_hash_from_bytes(b"hello world")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest

    def test_hash_from_bytes_different_content(self):
        """Different bytes produce different hashes."""
        h1 = compute_hash_from_bytes(b"hello world")
        h2 = compute_hash_from_bytes(b"goodbye world")
        assert h1 != h2

    def test_hash_from_text(self):
        """Text hash matches equivalent bytes hash."""
        text = "hello world"
        h_text = compute_hash_from_text(text)
        h_bytes = compute_hash_from_bytes(text.encode("utf-8"))
        assert h_text == h_bytes

    def test_hash_with_scope_key(self):
        """Scope key changes the hash."""
        h_no_scope = compute_hash_from_bytes(b"content")
        h_scope1 = compute_hash_from_bytes(b"content", scope_key="gene=BRCA1")
        h_scope2 = compute_hash_from_bytes(b"content", scope_key="gene=TP53")
        assert h_no_scope != h_scope1
        assert h_scope1 != h_scope2

    @pytest.mark.asyncio
    async def test_hash_from_file(self, tmp_path: Path):
        """File hash matches bytes hash for same content."""
        content = b"file content for hashing"
        file_path = tmp_path / "test.bin"
        file_path.write_bytes(content)

        h_file = await compute_hash_from_file(str(file_path))
        h_bytes = compute_hash_from_bytes(content)
        assert h_file == h_bytes

    @pytest.mark.asyncio
    async def test_hash_from_file_with_scope(self, tmp_path: Path):
        """File hash with scope key differs from without."""
        content = b"file content"
        file_path = tmp_path / "test.bin"
        file_path.write_bytes(content)

        h_no_scope = await compute_hash_from_file(str(file_path))
        h_scope = await compute_hash_from_file(str(file_path), scope_key="gene=BRCA1")
        assert h_no_scope != h_scope

    @pytest.mark.asyncio
    async def test_compute_content_hash_local_file(self, tmp_path: Path):
        """compute_content_hash hashes uploaded file for local source."""
        content = b"uploaded pdf content"
        file_path = tmp_path / "upload.pdf"
        file_path.write_bytes(content)

        state = PipelineGraphState(
            processing_run_id="run-1",
            source_document_id="doc-1",
            mode=PipelineMode.FULL,
            source_type=SourceType.LOCAL,
            upload_file_path=str(file_path),
        )
        h = await compute_content_hash(state)
        assert h is not None
        assert h == compute_hash_from_bytes(content)

    @pytest.mark.asyncio
    async def test_compute_content_hash_pre_parsed_markdown(self):
        """compute_content_hash hashes pre-parsed markdown text."""
        markdown = "# Title\n\nSome content."
        state = PipelineGraphState(
            processing_run_id="run-1",
            source_document_id="doc-1",
            mode=PipelineMode.FULL,
            source_type=SourceType.LOCAL,
            pre_parsed_markdown=markdown,
        )
        h = await compute_content_hash(state)
        assert h is not None
        assert h == compute_hash_from_text(markdown)

    @pytest.mark.asyncio
    async def test_compute_content_hash_online_identifiers(self):
        """compute_content_hash hashes identifiers for online source."""
        state = PipelineGraphState(
            processing_run_id="run-1",
            source_document_id="doc-1",
            mode=PipelineMode.FULL,
            source_type=SourceType.ONLINE,
            identifiers=["PMID:12345", "PMID:67890"],
            action="download",
        )
        h = await compute_content_hash(state)
        assert h is not None
        # Should be deterministic
        expected_key = "identifiers:pmid:12345,pmid:67890"
        assert h == compute_hash_from_text(expected_key)

    @pytest.mark.asyncio
    async def test_compute_content_hash_online_query(self):
        """compute_content_hash hashes query when no identifiers."""
        state = PipelineGraphState(
            processing_run_id="run-1",
            source_document_id="doc-1",
            mode=PipelineMode.FULL,
            source_type=SourceType.ONLINE,
            query="BRCA1 pathogenic variants",
            action="download",
        )
        h = await compute_content_hash(state)
        assert h is not None
        expected_key = "query:BRCA1 pathogenic variants"
        assert h == compute_hash_from_text(expected_key)

    @pytest.mark.asyncio
    async def test_compute_content_hash_phase_mode_returns_none(self):
        """compute_content_hash returns None for phase re-run mode."""
        state = PipelineGraphState(
            processing_run_id="run-1",
            source_document_id="doc-1",
            mode=PipelineMode.PHASE,
            source_type=SourceType.LOCAL,
            target_phase=2,
        )
        h = await compute_content_hash(state)
        assert h is None

    @pytest.mark.asyncio
    async def test_compute_content_hash_identifier_ordering(self):
        """Identifiers in different order produce the same hash."""
        state1 = PipelineGraphState(
            processing_run_id="run-1",
            source_document_id="doc-1",
            mode=PipelineMode.FULL,
            source_type=SourceType.ONLINE,
            identifiers=["PMID:67890", "PMID:12345"],
            action="download",
        )
        state2 = PipelineGraphState(
            processing_run_id="run-2",
            source_document_id="doc-2",
            mode=PipelineMode.FULL,
            source_type=SourceType.ONLINE,
            identifiers=["PMID:12345", "PMID:67890"],
            action="download",
        )
        h1 = await compute_content_hash(state1)
        h2 = await compute_content_hash(state2)
        assert h1 == h2  # Order-independent


# ── Cache service tests ──────────────────────────────────────────────────


class TestCacheServiceLookup:
    """Tests for cache lookup (L1/L2 read path)."""

    @pytest.mark.asyncio
    async def test_l1_hit_returns_state(self, cache_service, mock_redis, sample_state):
        """L1 Redis hit returns the cached state."""
        state_json = sample_state.model_dump(mode="json")
        mock_redis.get.return_value = json.dumps(state_json).encode("utf-8")

        result = await cache_service.get_cached_result("abc123")

        assert result is not None
        assert result.source == "l1_redis"
        assert result.state.processing_run_id == sample_state.processing_run_id
        mock_redis.get.assert_awaited_once_with("docproc:abc123")

    @pytest.mark.asyncio
    async def test_l1_miss_l2_hit_backfills_l1(
        self, cache_service, mock_redis, mock_session_factory, sample_state
    ):
        """L2 PostgreSQL hit returns state and backfills L1."""
        mock_redis.get.return_value = None  # L1 miss

        # Mock L2 query
        state_json = sample_state.model_dump(mode="json")
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = state_json
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session_factory.return_value = mock_session

        result = await cache_service.get_cached_result("abc123")

        assert result is not None
        assert result.source == "l2_postgres"
        assert result.state.processing_run_id == sample_state.processing_run_id
        # L1 should be backfilled
        mock_redis.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_both_miss_returns_none(self, cache_service, mock_redis, mock_session_factory):
        """Both L1 and L2 miss returns None."""
        mock_redis.get.return_value = None

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session_factory.return_value = mock_session

        result = await cache_service.get_cached_result("abc123")
        assert result is None

    @pytest.mark.asyncio
    async def test_l1_failure_falls_back_to_l2(
        self, cache_service, mock_redis, mock_session_factory, sample_state
    ):
        """L1 Redis failure gracefully falls back to L2."""
        mock_redis.get.side_effect = Exception("Redis connection lost")

        state_json = sample_state.model_dump(mode="json")
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = state_json
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session_factory.return_value = mock_session

        result = await cache_service.get_cached_result("abc123")
        assert result is not None
        assert result.source == "l2_postgres"


class TestCacheServiceWrite:
    """Tests for cache write (L1 + L2 write path)."""

    @pytest.mark.asyncio
    async def test_cache_result_writes_both_tiers(
        self, cache_service, mock_redis, mock_session_factory, sample_state
    ):
        """cache_result writes to both L2 PostgreSQL and L1 Redis."""
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session_factory.return_value = mock_session

        await cache_service.cache_result("abc123", sample_state)

        # L2 write
        mock_session.execute.assert_awaited()
        mock_session.commit.assert_awaited()
        # L1 write
        mock_redis.set.assert_awaited_once()
        args, kwargs = mock_redis.set.call_args
        assert args[0] == "docproc:abc123"
        assert kwargs.get("ex") is not None  # TTL set

    @pytest.mark.asyncio
    async def test_cache_result_l1_failure_does_not_raise(
        self, cache_service, mock_redis, mock_session_factory, sample_state
    ):
        """L1 Redis failure during cache_result does not raise."""
        mock_redis.set.side_effect = Exception("Redis down")

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session_factory.return_value = mock_session

        # Should not raise
        await cache_service.cache_result("abc123", sample_state)


class TestRunnerCacheIntegration:
    """Tests for PipelineRunner cache integration."""

    @pytest.mark.asyncio
    async def test_check_processing_cache_returns_none_when_no_cache(self, sample_state):
        """Runner with no processing_cache returns None."""
        from src.agents.runner import PipelineRunner

        runner = PipelineRunner(
            orchestrator=MagicMock(),
            semaphore=MagicMock(),
            state_persistence=MagicMock(),
            processing_cache=None,
        )
        result = await runner.check_processing_cache("abc123")
        assert result is None

    @pytest.mark.asyncio
    async def test_check_processing_cache_returns_none_for_empty_hash(self, sample_state):
        """Runner returns None for empty content hash."""
        from src.agents.runner import PipelineRunner

        mock_cache = MagicMock()
        mock_cache.get_cached_result = AsyncMock()

        runner = PipelineRunner(
            orchestrator=MagicMock(),
            semaphore=MagicMock(),
            state_persistence=MagicMock(),
            processing_cache=mock_cache,
        )
        result = await runner.check_processing_cache("")
        assert result is None
        mock_cache.get_cached_result.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_check_processing_cache_returns_state_on_hit(self, sample_state):
        """Runner returns cached state on hit."""
        from src.agents.runner import PipelineRunner

        mock_cache = MagicMock()
        mock_cache.get_cached_result = AsyncMock(
            return_value=CacheLookupResult(state=sample_state, source="l1_redis")
        )

        runner = PipelineRunner(
            orchestrator=MagicMock(),
            semaphore=MagicMock(),
            state_persistence=MagicMock(),
            processing_cache=mock_cache,
        )
        result = await runner.check_processing_cache("abc123")
        assert result is not None
        assert result.processing_run_id == sample_state.processing_run_id
