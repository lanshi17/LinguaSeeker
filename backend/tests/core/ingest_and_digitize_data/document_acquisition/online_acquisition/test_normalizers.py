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
    normalize_pubmed,
    normalize_unpaywall,
)
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.search_service import (
    build_provider_plan,
)


class TestNormalizerRegistry:
    def test_all_providers_registered(self):
        expected = {
            "crossref",
            "unpaywall",
            "pmc",
            "pubmed",
            "jstage",
            "doaj",
            "openalex",
            "europepmc",
            "pubscholar",
            "cyberleninka",
            "hans_publishers",
            "firecrawl",
        }
        assert set(NORMALIZER_MAP.keys()) == expected

    def test_normalize_items_unknown_provider(self):
        assert normalize_items("unknown", [{"title": "test"}]) == []

    def test_normalize_items_empty(self):
        assert normalize_items("crossref", []) == []


class TestPubMedNormalizer:
    def test_record_without_doi_keeps_pmid_identifier(self):
        """Chinese-journal PubMed records often lack a DOI, so PMID must survive."""
        item = normalize_pubmed(
            {
                "pmid": "24750837",
                "pmcid": "",
                "doi": "",
                "title": "[Clinical features and MECP2 mutations in children with Rett syndrome].",
                "journal": "Zhongguo dang dai er ke za zhi",
                "pub_date": "2014 Apr",
            }
        )
        assert item.source == "pubmed"
        assert item.doi is None
        assert item.identifiers["pmid"] == "24750837"
        assert item.url == "https://pubmed.ncbi.nlm.nih.gov/24750837/"
        assert item.year == "2014"

    def test_pmcid_yields_pdf_link(self):
        item = normalize_pubmed({"pmid": "1", "pmcid": "PMC123", "doi": "10.1234/x"})
        assert item.identifiers["pmcid"] == "PMC123"
        assert "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123/pdf/" in item.links


class TestProviderPlan:
    def test_pubmed_is_planned_for_english_and_chinese(self):
        """PubMed (db=pubmed) covers journals the PMC provider (db=pmc) misses."""
        assert "pubmed" in [item["provider"] for item in build_provider_plan(language="en")]
        assert "pubmed" in [item["provider"] for item in build_provider_plan(language="zh")]

    def test_preferred_provider_is_unchanged(self):
        """Adding PubMed must not change which provider ranking treats as preferred."""
        assert build_provider_plan(language="en")[0]["provider"] == "pmc"
        assert build_provider_plan(language="zh")[0]["provider"] == "crossref"


def test_pubmed_service_uses_configured_network_proxy(monkeypatch) -> None:
    """PubMed Python I/O must share egress with the Rust providers."""
    from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.pubmed_service import (
        OnlineAcquisitionPubMedService,
    )

    class _Network:
        proxy = "http://127.0.0.1:7890"

    class _Config:
        network = _Network()

    monkeypatch.setattr(
        "src.core.config.get_config",
        lambda: _Config(),
    )
    assert OnlineAcquisitionPubMedService._proxy() == "http://127.0.0.1:7890"


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
