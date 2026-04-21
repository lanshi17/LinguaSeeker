import pytest

from src.domain.literature.unified.search_service import (
    build_provider_plan,
    dedupe_candidates,
    rank_candidates,
    _normalize_candidate,
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


def test_normalize_candidate_handles_empty_links_list() -> None:
    item = {
        "title": "Example paper",
        "links": [],
        "identifiers": {"doi": "10.1000/example"},
    }

    candidate = _normalize_candidate(item, {"provider": "unpaywall", "route": "api"})

    assert candidate["detail_link"] is None
    assert candidate["doi"] == "10.1000/example"


def test_rank_candidates_prefers_exact_normalized_title_match() -> None:
    candidates = [
        {
            "candidate_id": "cand-1",
            "provider": "crossref",
            "route": "api",
            "title": "Different title",
        },
        {
            "candidate_id": "cand-2",
            "provider": "jstage",
            "route": "api",
            "title": "An <i>ATP2A2</i> Missense Mutation in a Japanese Family with Darier Disease: A Case Report and Review of the Japanese Darier Disease Patients with <i>ATP2A2</i> Mutations",
        },
    ]

    ranked = rank_candidates(
        candidates,
        expected_title="An ATP2A2 Missense Mutation in a Japanese Family with Darier Disease: A Case Report and Review of the Japanese Darier Disease Patients with ATP2A2 Mutations",
        preferred_provider="jstage",
    )

    assert ranked[0]["candidate_id"] == "cand-2"
