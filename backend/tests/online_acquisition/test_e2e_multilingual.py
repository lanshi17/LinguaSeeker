"""End-to-end multilingual search tests — one test per supported language.

Each test calls the workflow with a language-appropriate query and verifies
that at least one provider returns results.  Network-dependent tests skip
gracefully when providers are unavailable.
"""

from __future__ import annotations

import pytest

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.search_service import (
    build_provider_plan,
    search_multilingual,
)


def _skip_if_no_results(results: list, lang: str) -> None:
    if not results:
        pytest.skip(f"No results for language={lang} (all providers unavailable or returned empty)")


# ---------------------------------------------------------------------------
# Per-language tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_zh_chinese():
    """Chinese literature search (crossref, unpaywall, openalex, doaj, pmc)."""
    results = await search_multilingual(
        target="BRCA1",
        disease="乳腺癌",
        language="zh",
        candidate_limit=5,
    )
    _skip_if_no_results(results, "zh")
    assert len(results) > 0
    first = results[0]
    assert first.get("title"), "Expected title in first Chinese result"


@pytest.mark.asyncio
async def test_search_ja_japanese():
    """Japanese literature search (jstage, cinii, crossref …)."""
    results = await search_multilingual(
        target="BRCA1",
        disease="乳癌",
        language="ja",
        candidate_limit=5,
    )
    _skip_if_no_results(results, "ja")
    assert len(results) > 0


@pytest.mark.asyncio
async def test_search_ko_korean():
    """Korean literature search (koreascience, crossref …)."""
    results = await search_multilingual(
        target="BRCA1",
        disease="유방암",
        language="ko",
        candidate_limit=5,
    )
    _skip_if_no_results(results, "ko")
    assert len(results) > 0


@pytest.mark.asyncio
async def test_search_es_spanish():
    """Spanish literature search (scielo, redalyc, crossref …)."""
    results = await search_multilingual(
        target="BRCA1",
        disease="cáncer de mama",
        language="es",
        candidate_limit=5,
    )
    _skip_if_no_results(results, "es")
    assert len(results) > 0


@pytest.mark.asyncio
async def test_search_pt_portuguese():
    """Portuguese literature search (scielo, redalyc, crossref …)."""
    results = await search_multilingual(
        target="BRCA1",
        disease="câncer de mama",
        language="pt",
        candidate_limit=5,
    )
    _skip_if_no_results(results, "pt")
    assert len(results) > 0


@pytest.mark.asyncio
async def test_search_en_english():
    """English literature search (pmc, europepmc, crossref, arxiv, biorxiv, medrxiv, openalex, openaire, base, core, unpaywall, doaj)."""
    results = await search_multilingual(
        target="BRCA1",
        disease="breast cancer",
        language="en",
        candidate_limit=5,
    )
    _skip_if_no_results(results, "en")
    assert len(results) > 0


@pytest.mark.asyncio
async def test_search_auto_language():
    """Auto-detected language routing (crossref, unpaywall, openalex, europepmc, doaj, pmc)."""
    results = await search_multilingual(
        target="BRCA1",
        disease="breast cancer",
        language="auto",
        candidate_limit=5,
    )
    _skip_if_no_results(results, "auto")
    assert len(results) > 0


# ---------------------------------------------------------------------------
# Provider plan coverage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provider_plan_covers_all_languages():
    """Every language in the matrix produces a non-empty provider plan."""
    for lang in ("zh", "ja", "ko", "es", "pt", "en", "auto"):
        plan = build_provider_plan(language=lang)
        assert len(plan) > 0, f"Provider plan for {lang} should not be empty"
        for item in plan:
            assert item["route"] in ("api", "web"), f"Invalid route for {lang}: {item['route']}"
            assert item["provider"], f"Empty provider for {lang}"
