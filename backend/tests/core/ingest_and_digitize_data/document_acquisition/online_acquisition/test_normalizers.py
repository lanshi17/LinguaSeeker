"""Tests for provider normalizers."""

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.normalizers import (
    NORMALIZER_MAP,
    normalize_crossref,
    normalize_doaj,
    normalize_europepmc,
    normalize_items,
    normalize_jstage,
    normalize_openalex,
    normalize_pmc,
    normalize_unpaywall,
)


class TestNormalizerRegistry:
    def test_all_providers_registered(self):
        expected = {"crossref", "unpaywall", "pmc", "jstage", "doaj", "openalex", "europepmc", "pubscholar", "cyberleninka", "hans_publishers", "firecrawl"}
        assert set(NORMALIZER_MAP.keys()) == expected

    def test_normalize_items_unknown_provider(self):
        assert normalize_items("unknown", [{"title": "test"}]) == []

    def test_normalize_items_empty(self):
        assert normalize_items("crossref", []) == []


class TestCrossrefNormalizer:
    def test_basic_item(self):
        raw = {
            "title": ["Test Paper Title"],
            "author": [{"given": "John", "family": "Doe"}],
            "container-title": ["Journal of Testing"],
            "DOI": "10.1234/test",
            "URL": "https://doi.org/10.1234/test",
            "issued": {"date-parts": [[2024]]},
        }
        item = normalize_crossref(raw)
        assert item.source == "crossref"
        assert item.title == "Test Paper Title"
        assert item.authors == ["John Doe"]
        assert item.journal == "Journal of Testing"
        assert item.doi == "10.1234/test"
        assert item.year == "2024"

    def test_minimal_item(self):
        item = normalize_crossref({})
        assert item.source == "crossref"
        assert item.title is None


class TestUnpaywallNormalizer:
    def test_with_best_oa(self):
        raw = {
            "title": "OA Paper",
            "doi": "10.1234/oa",
            "best_oa_location": {"url_for_pdf": "https://example.com/paper.pdf"},
        }
        item = normalize_unpaywall(raw)
        assert item.source == "unpaywall"
        assert item.title == "OA Paper"
        assert "https://example.com/paper.pdf" in item.links


class TestPmcNormalizer:
    def test_basic_item(self):
        raw = {
            "title": "PMC Article",
            "authors": ["Author A", "Author B"],
            "journal_title": "PMC Journal",
        }
        item = normalize_pmc(raw)
        assert item.source == "pmc"
        assert item.title == "PMC Article"


class TestJstageNormalizer:
    def test_japanese_title(self):
        raw = {
            "article_title_ja": "日本語のタイトル",
            "article_title_en": "Japanese Title",
            "material_title_en": "J-Stage Journal",
            "doi": "10.1234/jstage",
        }
        item = normalize_jstage(raw)
        assert item.source == "jstage"
        assert item.title == "Japanese Title"
        assert item.language == "ja"


class TestDoajNormalizer:
    def test_basic_item(self):
        raw = {
            "title": "DOAJ Article",
            "journal_title": "DOAJ Journal",
            "doi": "10.1234/doaj",
        }
        item = normalize_doaj(raw)
        assert item.source == "doaj"
        assert item.title == "DOAJ Article"


class TestOpenalexNormalizer:
    def test_basic_item(self):
        raw = {
            "title": "OpenAlex Paper",
            "publication_year": 2023,
            "doi": "https://doi.org/10.1234/oalex",
        }
        item = normalize_openalex(raw)
        assert item.source == "openalex"
        assert item.year == "2023"

    def test_with_authorships(self):
        raw = {
            "title": "Authored Paper",
            "authorships": [
                {"author": {"display_name": "Alice"}},
                {"author": {"display_name": "Bob"}},
            ],
        }
        item = normalize_openalex(raw)
        assert "Alice" in item.authors
        assert "Bob" in item.authors


class TestEuropepmcNormalizer:
    def test_basic_item(self):
        raw = {
            "title": "Europe PMC Paper",
            "journalTitle": "EPMC Journal",
            "pubYear": "2022",
            "doi": "10.1234/epmc",
        }
        item = normalize_europepmc(raw)
        assert item.source == "europepmc"
        assert item.year == "2022"

    def test_with_pmcid(self):
        raw = {
            "title": "PMC Article",
            "pmcid": "PMC12345",
        }
        item = normalize_europepmc(raw)
        assert item.identifiers.get("pmcid") == "PMC12345"
