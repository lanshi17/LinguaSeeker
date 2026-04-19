import pytest

from src.domain.literature.unified.search_service import (
    build_provider_plan,
    dedupe_candidates,
)


def test_build_provider_plan_for_japanese_prefers_jstage() -> None:
    plan = build_provider_plan(language="ja")

    assert plan[0] == {"route": "api", "provider": "jstage"}
    assert {item["provider"] for item in plan} >= {"jstage", "crossref", "unpaywall"}


def test_dedupe_candidates_by_doi_url_and_normalized_title() -> None:
    candidates = [
        {
            "candidate_id": "cand-1",
            "provider": "crossref",
            "route": "api",
            "title": "Fabry Disease Case Report",
            "doi": "10.1000/example",
            "url": "https://example.org/paper-1",
        },
        {
            "candidate_id": "cand-2",
            "provider": "unpaywall",
            "route": "api",
            "title": "Another title",
            "doi": "10.1000/example",
            "url": "https://different.example/paper",
        },
        {
            "candidate_id": "cand-3",
            "provider": "pubscholar",
            "route": "web",
            "title": "Unique title",
            "url": "https://example.org/shared-url",
        },
        {
            "candidate_id": "cand-4",
            "provider": "hans_publishers",
            "route": "web",
            "title": "Different title",
            "url": "https://example.org/shared-url",
        },
        {
            "candidate_id": "cand-5",
            "provider": "pmc",
            "route": "api",
            "title": "GLA gene: case report!!!",
        },
        {
            "candidate_id": "cand-6",
            "provider": "doaj",
            "route": "api",
            "title": "gla gene case report",
        },
    ]

    deduped = dedupe_candidates(candidates)

    assert [item["candidate_id"] for item in deduped] == ["cand-1", "cand-3", "cand-5"]
