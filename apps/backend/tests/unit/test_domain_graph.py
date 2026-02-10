from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from src.domain.graph import association_service as assoc_module
from src.domain.graph import search as search_module
from src.domain.graph import sync as sync_module


class FakeNeo4jAssociation:
    def find_gene_related_variants(self, *_: Any, **__: Any) -> List[Dict[str, Any]]:
        return [
            {"variant": "c.1A>T", "document_id": 1},
            {"variant": "c.1A>T", "document_id": 2},
        ]

    def run_query(self, query: str, *_: Any, **__: Any) -> List[Dict[str, Any]]:
        if "HAS_VARIANT" in query:
            return [
                {"variant": "c.1A>T", "doc_ids": [1, 2]},
                {"variant": "c.2G>C", "doc_ids": [2]},
            ]
        return [{"disease": "D1", "doc_ids": [1]}]

    def find_variant_evidence_graph(self, *_: Any, **__: Any) -> List[Dict[str, Any]]:
        return [{"g": {"symbol": "GENE"}, "p": {"description": "ph"}, "doc": {"document_id": 1}}]


class FakePostgresAssociation:
    def search_evidence_by_gene(self, *_: Any, **__: Any) -> List[Any]:
        return [SimpleNamespace(variant_hgvs_c="c.1A>T")]

    def search_evidence_by_variant(self, *_: Any, **__: Any) -> List[Any]:
        return []


def test_analyze_gene_associations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(assoc_module, "get_neo4j_client", lambda: FakeNeo4jAssociation())
    monkeypatch.setattr(assoc_module, "get_postgres_client", lambda: FakePostgresAssociation())
    analyzer = assoc_module.EntityAssociationAnalyzer()

    report = analyzer.analyze_gene_associations("GENE")
    assert report.summary["total_variants"] == 1
    assert report.summary["total_documents"] == 2
    assert report.summary["total_evidence_records"] == 1
    assert any(link.relationship == "HAS_VARIANT" for link in report.links)
    assert any(link.relationship == "ASSOCIATED_GENE" for link in report.links)


def test_build_co_occurrence_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(assoc_module, "get_neo4j_client", lambda: FakeNeo4jAssociation())
    monkeypatch.setattr(assoc_module, "get_postgres_client", lambda: FakePostgresAssociation())
    analyzer = assoc_module.EntityAssociationAnalyzer()

    matrix = analyzer.build_co_occurrence_matrix("GENE")
    assert matrix["c.1A>T"]["c.1A>T"] == 2
    assert matrix["c.1A>T"]["c.2G>C"] == 1


def test_analyze_variant_associations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(assoc_module, "get_neo4j_client", lambda: FakeNeo4jAssociation())
    monkeypatch.setattr(assoc_module, "get_postgres_client", lambda: FakePostgresAssociation())
    analyzer = assoc_module.EntityAssociationAnalyzer()

    report = analyzer.analyze_variant_associations("c.1A>T")
    assert "GENE" in report.summary["related_genes"]
    assert "ph" in report.summary["related_phenotypes"]
    assert report.summary["document_count"] == 1
    assert any(link.relationship == "BELONGS_TO_GENE" for link in report.links)
    assert any(link.relationship == "HAS_PHENOTYPE" for link in report.links)


def test_find_evidence_chains(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeNeo4jChains(FakeNeo4jAssociation):
        def run_query(self, *_: Any, **__: Any) -> List[Dict[str, Any]]:
            return [
                {
                    "gene": "GENE",
                    "variant": "c.1A>T",
                    "protein_change": "p.K1N",
                    "disease": "D1",
                    "doc_ids": [1, 2],
                    "strengths": ["PS3"],
                }
            ]

    monkeypatch.setattr(assoc_module, "get_neo4j_client", lambda: FakeNeo4jChains())
    monkeypatch.setattr(assoc_module, "get_postgres_client", lambda: FakePostgresAssociation())
    analyzer = assoc_module.EntityAssociationAnalyzer()

    chains = analyzer.find_evidence_chains("GENE", min_documents=1)
    assert len(chains) == 1
    assert chains[0]["document_count"] == 2


class FakeNeo4jSearch:
    def find_variant_evidence_graph(self, *_: Any, **__: Any) -> List[Dict[str, Any]]:
        return [
            {
                "v": {"hgvs_c": "c.1A>T"},
                "g": {"symbol": "GENE"},
                "p": {"description": "ph"},
                "e": {"evidence_id": "e1"},
                "doc": {"document_id": 1},
            }
        ]

    def find_gene_related_variants(self, *_: Any, **__: Any) -> List[Dict[str, Any]]:
        return [{"gene": "GENE", "variant": "c.1A>T", "document_id": 1, "doc_title": "doc"}]

    def find_multi_document_evidence(self, *_: Any, **__: Any) -> List[Dict[str, Any]]:
        return [{"gene": "GENE", "variant": "c.1A>T", "document_id": 1}]


class FakePostgresSearch:
    def search_evidence_by_variant(self, *_: Any, **__: Any) -> List[Any]:
        return [SimpleNamespace(document_id=1, evidence_id=1)]

    def search_evidence_by_gene(self, *_: Any, **__: Any) -> List[Any]:
        return []

    def search_evidence_multi(self, *_: Any, **__: Any) -> List[Any]:
        return []

    def get_evidence_for_document(self, *_: Any, **__: Any) -> List[Any]:
        return []


def test_graph_search_by_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_module, "get_neo4j_client", lambda: FakeNeo4jSearch())
    monkeypatch.setattr(search_module, "get_postgres_client", lambda: FakePostgresSearch())
    engine = search_module.GraphSearchEngine()

    result = engine.search_by_variant("c.1A>T")
    assert result.total_evidence == 1
    assert result.document_count == 1
    assert any(node.node_type == "gene" for node in result.nodes)


def test_graph_sync_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[str] = []

    class FakeNeo4j:
        def upsert_document(self, *_: Any, **__: Any) -> None:
            calls.append("doc")

        def upsert_gene(self, *_: Any, **__: Any) -> None:
            calls.append("gene")

        def upsert_variant(self, *_: Any, **__: Any) -> None:
            calls.append("variant")

        def link_gene_variant(self, *_: Any, **__: Any) -> None:
            calls.append("link_gene_variant")

        def link_document_entity(self, *_: Any, **__: Any) -> None:
            calls.append("link_document_entity")

        def upsert_transcript(self, *_: Any, **__: Any) -> None:
            calls.append("transcript")

        def link_gene_transcript(self, *_: Any, **__: Any) -> None:
            calls.append("link_gene_transcript")

        def upsert_disease(self, *_: Any, **__: Any) -> None:
            calls.append("disease")

        def link_disease_gene(self, *_: Any, **__: Any) -> None:
            calls.append("link_disease_gene")

        def upsert_phenotype(self, *_: Any, **__: Any) -> None:
            calls.append("phenotype")

        def link_variant_phenotype(self, *_: Any, **__: Any) -> None:
            calls.append("link_variant_phenotype")

        def upsert_species(self, *_: Any, **__: Any) -> None:
            calls.append("species")

        def upsert_evidence(self, *_: Any, **__: Any) -> None:
            calls.append("evidence")

        def link_variant_evidence(self, *_: Any, **__: Any) -> None:
            calls.append("link_variant_evidence")

        def link_evidence_document(self, *_: Any, **__: Any) -> None:
            calls.append("link_evidence_document")

    class FakePostgres:
        def __init__(self) -> None:
            self.kwargs: Dict[str, Any] = {}

        def create_evidence_record(self, **kwargs: Any) -> Any:
            self.kwargs = kwargs
            return SimpleNamespace(evidence_id=123)

        def get_evidence_for_document(self, *_: Any, **__: Any) -> List[Any]:
            return []

    fake_pg = FakePostgres()
    monkeypatch.setattr(sync_module, "get_neo4j_client", lambda: FakeNeo4j())
    monkeypatch.setattr(sync_module, "get_postgres_client", lambda: fake_pg)

    service = sync_module.GraphSyncService()
    evidence_output = {
        "extracted_fields": {
            "gene": {"symbol": "GENE"},
            "variant": {"hgvs_c": "c.1A>T", "hgvs_p": "p.K1N"},
            "transcript_id": {"transcript_id": "NM_1"},
            "reference_genome_version": {"version": "GRCh38"},
            "disease_chpo": {"disease_name": "D1", "icd10_code": "D1"},
            "species": {"species_name": "human"},
            "phenotype": {"phenotype_description": "ph"},
        },
        "ps3_evidence": {},
        "evidence_classification": "Pathogenic",
        "overall_confidence": 90.0,
        "acmg_evidence_levels": ["PS3"],
        "final_evidence_strength": "PS3",
        "arbitration_score": 88.0,
    }
    result = service.sync_evidence(1, evidence_output)

    assert result["pg_evidence_id"] == 123
    assert result["neo4j_synced"] is True
    assert fake_pg.kwargs["gene_symbol"] == "GENE"
    assert "variant" in calls
    assert "evidence" in calls
