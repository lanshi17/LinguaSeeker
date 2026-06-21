"""Tests for flattened search index repository."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import Table


# ── Helpers ────────────────────────────────────────────────────────────────


def _fake_session() -> MagicMock:
    """Return a MagicMock that mimics an async SQLAlchemy session."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


# ── Table definition tests ─────────────────────────────────────────────────


def test_search_index_table_exists() -> None:
    """search_index_repo exports a frontend_search_index Table."""
    from src.dao.postgresql.search_index_repo import frontend_search_index

    assert isinstance(frontend_search_index, Table)
    assert frontend_search_index.name == "frontend_search_index"


def test_search_index_table_has_required_columns() -> None:
    """The search index table contains all MVP frontend-query columns."""
    from src.dao.postgresql.search_index_repo import frontend_search_index

    columns = {c.name for c in frontend_search_index.columns}

    required = {
        "canonical_evidence_id",
        "pmid",
        "doi",
        "gene_ids",
        "variant_ids",
        "entity_ids",
        "field_id",
        "review_status",
        "current_best_confidence",
        "search_text",
        "active_payload",
    }
    assert required <= columns, f"Missing columns: {required - columns}"


def test_search_index_table_has_created_at_column() -> None:
    """The frontend_search_index table must expose a created_at column."""
    from src.dao.postgresql.search_index_repo import frontend_search_index

    col_names = [c.name for c in frontend_search_index.columns]
    assert "created_at" in col_names


def test_search_index_table_has_unique_index_on_canonical_id() -> None:
    """The table has a unique index on canonical_evidence_id for CONCURRENTLY refresh."""
    from src.dao.postgresql.search_index_repo import frontend_search_index

    index_names = {idx.name for idx in frontend_search_index.indexes}
    assert "ix_frontend_search_index_canonical_evidence_id" in index_names


# ── Repository query tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_by_gene_returns_rows() -> None:
    """Search by gene returns matching rows from the index."""
    from src.dao.postgresql.search_index_repo import SearchIndexRepository

    session = _fake_session()
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {"canonical_evidence_id": "c1", "gene_ids": ["BRCA1"], "field_id": "gene_symbol"},
    ]
    session.execute.return_value = mock_result
    repo = SearchIndexRepository(session)

    rows = await repo.search(gene_ids=["BRCA1"])
    assert len(rows) == 1
    assert rows[0]["gene_ids"] == ["BRCA1"]
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_by_variant_returns_rows() -> None:
    """Search by variant returns matching rows."""
    from src.dao.postgresql.search_index_repo import SearchIndexRepository

    session = _fake_session()
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {"canonical_evidence_id": "c2", "variant_ids": ["rs80357906"], "field_id": "variant_hgvs"},
    ]
    session.execute.return_value = mock_result
    repo = SearchIndexRepository(session)

    rows = await repo.search(variant_ids=["rs80357906"])
    assert len(rows) == 1
    assert rows[0]["variant_ids"] == ["rs80357906"]


@pytest.mark.asyncio
async def test_search_by_doi_returns_rows() -> None:
    """Search by DOI returns matching rows."""
    from src.dao.postgresql.search_index_repo import SearchIndexRepository

    session = _fake_session()
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {"canonical_evidence_id": "c3", "doi": "10.1000/test", "field_id": "variant_interpretation"},
    ]
    session.execute.return_value = mock_result
    repo = SearchIndexRepository(session)

    rows = await repo.search(doi="10.1000/test")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_search_by_pmid_returns_rows() -> None:
    """Search by PMID returns matching rows."""
    from src.dao.postgresql.search_index_repo import SearchIndexRepository

    session = _fake_session()
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {"canonical_evidence_id": "c4", "pmid": "12345", "field_id": "disease_association"},
    ]
    session.execute.return_value = mock_result
    repo = SearchIndexRepository(session)

    rows = await repo.search(pmid="12345")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_search_no_filters_returns_default_list_view() -> None:
    """Search with no filters returns the default list view."""
    from src.dao.postgresql.search_index_repo import SearchIndexRepository

    session = _fake_session()
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [
        {"canonical_evidence_id": "c1", "field_id": "gene_symbol"},
    ]
    session.execute.return_value = mock_result
    repo = SearchIndexRepository(session)

    rows = await repo.search()
    assert len(rows) == 1
    session.execute.assert_awaited_once()


# ── Repository refresh tests ───────────────────────────────────────────────


def test_refresh_insert_sql_includes_created_at():
    """The refresh() INSERT statement must select created_at from canonical_evidence_items."""
    import inspect

    from src.dao.postgresql.search_index_repo import SearchIndexRepository

    source = inspect.getsource(SearchIndexRepository.refresh)

    # Find the INSERT block and verify created_at appears in both the
    # column list (INSERT INTO ... (..., created_at)) and the SELECT
    # clause (SELECT ..., cei.created_at).
    insert_start = source.index("INSERT INTO frontend_search_index")
    insert_block = source[insert_start:]

    # Extract column list: between the first ( and the closing ) before SELECT
    col_list_end = insert_block.index(")")
    col_list = insert_block[:col_list_end]
    assert "created_at" in col_list, "created_at missing from INSERT column list"

    # Extract SELECT clause: from SELECT to the closing triple-quote
    select_start = insert_block.index("SELECT")
    select_block = insert_block[select_start:]
    assert "cei.created_at" in select_block, "cei.created_at missing from SELECT clause"


@pytest.mark.asyncio
async def test_refresh_sql_propagates_variant_ids_from_active_payload() -> None:
    """refresh() maps active_payload->'variant_ids' into the variant_ids column.

    Pins the write-side contract: a canonical evidence row whose
    active_payload carries ``variant_ids`` flows into
    ``frontend_search_index.variant_ids`` (COALESCE'd to an empty array).
    """
    from src.dao.postgresql.search_index_repo import (
        VARIANT_IDS_PAYLOAD_KEY,
        SearchIndexRepository,
    )

    session = _fake_session()
    repo = SearchIndexRepository(session)
    await repo.refresh()

    # Capture the runtime INSERT SQL emitted by refresh().
    execute_calls = [str(c.args[0]) for c in session.execute.call_args_list]
    insert_call = next(t for t in execute_calls if "INSERT INTO frontend_search_index" in t)
    assert f"cei.active_payload -> '{VARIANT_IDS_PAYLOAD_KEY}'" in insert_call
    assert "AS variant_ids" in insert_call
    assert "'[]'::jsonb" in insert_call


def test_search_variant_ids_uses_jsonb_overlap_operator() -> None:
    """search(variant_ids=...) filters via the JSONB ?| overlap operator.

    Pins the read-side contract: variant_ids filtering matches rows whose
    variant_ids array overlaps the supplied list.
    """
    import inspect

    from src.dao.postgresql.search_index_repo import SearchIndexRepository

    source = inspect.getsource(SearchIndexRepository.search)
    assert "variant_ids" in source
    assert '.op("?|")' in source


@pytest.mark.asyncio
async def test_refresh_truncates_and_rebuilds() -> None:
    """Refresh truncates the search index and rebuilds from canonical evidence."""
    from src.dao.postgresql.search_index_repo import SearchIndexRepository

    session = _fake_session()
    repo = SearchIndexRepository(session)

    await repo.refresh()

    # Must issue DELETE first.
    execute_calls = [c.args[0] for c in session.execute.call_args_list]
    delete_texts = [str(c) for c in execute_calls if "DELETE" in str(c).upper()]
    assert len(delete_texts) >= 1, "refresh must delete the search index"

    # Must flush after rebuild (caller owns commit/rollback).
    session.flush.assert_awaited_once()


# ── Integration test (skip when PostgreSQL is unavailable) ───────────────────


@pytest.mark.skip(reason="Requires a running PostgreSQL instance")
@pytest.mark.asyncio
async def test_refresh_and_search_integration() -> None:
    """End-to-end refresh and search against a real PostgreSQL instance."""
    from sqlalchemy import text

    from src.core.config import Settings
    from src.dao.postgresql.connection import async_session_factory, build_async_engine
    from src.dao.postgresql.search_index_repo import SearchIndexRepository

    settings = Settings()
    engine = build_async_engine(settings)
    session_factory = async_session_factory(engine)

    # Create search index table (it may already exist from migration)
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS frontend_search_index (
                canonical_evidence_id UUID PRIMARY KEY,
                pmid TEXT,
                doi TEXT,
                gene_ids JSONB DEFAULT '[]'::jsonb,
                variant_ids JSONB DEFAULT '[]'::jsonb,
                entity_ids JSONB DEFAULT '[]'::jsonb,
                field_id TEXT NOT NULL,
                review_status TEXT NOT NULL,
                current_best_confidence NUMERIC(5,4),
                search_text TEXT NOT NULL DEFAULT '',
                active_payload JSONB DEFAULT '{}'::jsonb
            )
        """))

    async with session_factory() as session:
        repo = SearchIndexRepository(session)
        await repo.refresh()
        rows = await repo.search()
        assert isinstance(rows, list)

    await engine.dispose()
