"""Tests for enhanced ranking."""

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.search_service import rank_candidates


def test_rank_by_title_match():
    candidates = [
        {"title": "Unrelated paper", "doi": "10.1/x", "provider": "crossref"},
        {"title": "BRCA1 mutation in breast cancer", "doi": "10.1/y", "provider": "crossref"},
    ]
    ranked = rank_candidates(candidates, expected_title="BRCA1 mutation in breast cancer")
    assert ranked[0]["title"] == "BRCA1 mutation in breast cancer"


def test_rank_by_doi_presence():
    candidates = [
        {"title": "Paper A", "doi": None, "provider": "crossref"},
        {"title": "Paper B", "doi": "10.1/z", "provider": "crossref"},
    ]
    ranked = rank_candidates(candidates, expected_title=None)
    assert ranked[0]["doi"] == "10.1/z"


def test_rank_by_preferred_provider():
    candidates = [
        {"title": "Paper A", "doi": "10.1/a", "provider": "openalex"},
        {"title": "Paper B", "doi": "10.1/b", "provider": "crossref"},
    ]
    ranked = rank_candidates(candidates, preferred_provider="crossref")
    assert ranked[0]["provider"] == "crossref"


def test_rank_by_year_recency():
    candidates = [
        {"title": "Old paper", "doi": "10.1/a", "provider": "crossref", "year": "2010"},
        {"title": "New paper", "doi": "10.1/b", "provider": "crossref", "year": "2024"},
    ]
    ranked = rank_candidates(candidates, expected_title=None)
    assert ranked[0]["year"] == "2024"
