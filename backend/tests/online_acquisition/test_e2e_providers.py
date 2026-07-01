"""End-to-end tests for new providers."""

import pytest


@pytest.mark.asyncio
async def test_scielo_search():
    """Test SciELO dispatch works. Skips if network unavailable."""
    from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import search_provider

    result = await search_provider("scielo", query="BRCA1 breast cancer", limit=5)
    if not result.success:
        warnings = " ".join(result.warnings)
        if any(k in warnings for k in ("sending request", "connect", "403", "429")):
            pytest.skip(f"SciELO unavailable: {result.warnings[0] if result.warnings else 'unknown'}")
    assert result.success


@pytest.mark.asyncio
async def test_parallel_search_multilingual():
    from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.search_service import (
        search_parallel,
        build_provider_plan,
    )

    plan = build_provider_plan(language="es")
    results = await search_parallel(query="cancer genomics", plan=plan[:3], concurrency=3)
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_health_tracking_integration():
    from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.provider_health import (
        get_health_tracker,
    )
    from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import search_provider

    await search_provider("crossref", query="test", limit=1)
    stats = get_health_tracker().get_stats("crossref")
    assert stats.success_count + stats.failure_count > 0
