"""Tests for the cross-lingual disease name resolver."""

from __future__ import annotations

import pytest

from src.core.standardize_entities_and_align_knowledge.cross_lingual_disease import (
    CrossLingualDiseaseResolver,
)


class _FakeResult:
    """Minimal result stub returning mapping rows."""

    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    """Async session stub returning a fixed set of mapping rows per execute."""

    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self._rows = rows or []
        self.statements: list[object] = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _FakeResult(self._rows)


@pytest.mark.asyncio
async def test_resolver_returns_none_for_empty_input() -> None:
    """Empty input yields no tokens and therefore no match."""
    resolver = CrossLingualDiseaseResolver(_FakeSession())
    assert await resolver.resolve("") is None


@pytest.mark.asyncio
async def test_resolver_returns_none_for_no_match() -> None:
    """Random text with no matching aliases returns None."""
    resolver = CrossLingualDiseaseResolver(_FakeSession(rows=[]))
    assert await resolver.resolve("zzzqqqxxxyz") is None


@pytest.mark.asyncio
async def test_resolver_finds_disease_by_partial_token_match() -> None:
    """Token-based ILIKE matching resolves a partial disease name."""
    rows = [
        {
            "display_name": "CHARCOT-MARIE-TOOTH DISEASE, AXONAL TYPE 2N",
            "normalized_alias": "charcot-marie-tooth disease, axonal type 2n",
        },
    ]
    resolver = CrossLingualDiseaseResolver(_FakeSession(rows=rows))
    result = await resolver.resolve("charcot-marie-tooth disease axonal type 2n")
    assert result == "CHARCOT-MARIE-TOOTH DISEASE, AXONAL TYPE 2N"


@pytest.mark.asyncio
async def test_resolver_picks_highest_token_overlap() -> None:
    """When multiple aliases match, the highest Jaccard overlap wins."""
    rows = [
        {
            "display_name": "Fabry-Anderson Disease",
            "normalized_alias": "fabry anderson disease",
        },
        {
            "display_name": "Fabry Disease",
            "normalized_alias": "fabry disease",
        },
    ]
    resolver = CrossLingualDiseaseResolver(_FakeSession(rows=rows))
    result = await resolver.resolve("fabry disease")
    assert result == "Fabry Disease"


@pytest.mark.asyncio
async def test_resolver_strips_stopwords_from_query() -> None:
    """Stopwords are excluded from the ILIKE query tokens."""
    session = _FakeSession(rows=[])
    resolver = CrossLingualDiseaseResolver(session)
    await resolver.resolve("fabry disease syndrome type")

    assert session.statements, "resolver should issue one ILIKE query"
    compiled = str(
        session.statements[0].compile(compile_kwargs={"literal_binds": True}),
    )
    assert "%fabry%" in compiled
    assert "%disease%" not in compiled
    assert "%syndrome%" not in compiled
    assert "%type%" not in compiled
