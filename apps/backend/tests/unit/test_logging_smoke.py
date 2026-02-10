import types
from typing import Any, Dict, List, cast

import pytest

from src.domain.agent.workflow import EvidenceAgent
from src.domain.evidence import classifier as classifier_module
from src.domain.evidence import tools as tools_module
from src.domain.evidence import aggregator as aggregator_module
from src.domain.graph import association_service as assoc_module
from src.domain.graph import search as search_module
from src.domain.graph import sync as sync_module
from src.presentation import graph_api as graph_api_module


class DummyRag:
    def get_qdrant_manager(self) -> Any:
        return object()

    def get_embedding_client(self) -> Any:
        return object()


def test_workflow_helpers_smoke() -> None:
    agent = EvidenceAgent(rag_component=cast(Any, DummyRag()))
    assert agent._normalize_anthropic_base_url("") == ""
    assert agent._normalize_anthropic_base_url("https://example.com/v1") == "https://example.com"
    assert agent._estimate_tokens("hello") > 0
    chunks = agent._split_paragraph("hello world")
    assert len(chunks) == 1
    segments = agent._segment_text_for_translation("para1\n\npara2")
    assert len(segments) >= 1


def test_classifier_smoke() -> None:
    ps3_evidence = {
        "ps3_step_1": {"score": 25, "evidence_refs": []},
        "ps3_step_2": {"score": 20, "evidence_refs": []},
        "ps3_step_3": {"score": 30, "evidence_refs": []},
        "ps3_step_4": {"score": 25, "final_evidence_strength": "PS3", "evidence_refs": []},
    }
    result = classifier_module.EvidenceClassifier.classify(ps3_evidence)
    assert result.overall_score >= 0


def test_tools_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    assert tools_module.OddsPath_Calculator.invoke({"P1": 0.2, "P2": 0.4}) > 0
    assert tools_module.determine_evidence_strength_from_oddspath.invoke({"oddspath": 0.1})
    assert tools_module.determine_max_evidence_from_controls.invoke({"control_variants_count": 3})
    assert tools_module.validate_ps3_step1.invoke({"disease_mechanism_clarity": "clear"})["can_proceed"]
    assert tools_module.validate_ps3_step2.invoke({"assay_suitable": "yes"})["can_proceed"]

    class FakeSearchResponse:
        def __init__(self) -> None:
            self.results: List[Any] = []

    class FakeQdrant:
        score_threshold = 0.0

        async def search(self, **_: Any) -> FakeSearchResponse:
            return FakeSearchResponse()

    class FakeEmbedding:
        def embed_query(self, _: str) -> List[float]:
            return [0.0]

    class FakeRag:
        def get_qdrant_manager(self) -> FakeQdrant:
            return FakeQdrant()

        def get_embedding_client(self) -> FakeEmbedding:
            return FakeEmbedding()

    monkeypatch.setattr(tools_module, "RAGComponent", FakeRag)


@pytest.mark.asyncio
async def test_search_knowledge_base_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSearchResponse:
        def __init__(self) -> None:
            self.results: List[Any] = []

    class FakeQdrant:
        score_threshold = 0.0

        async def search(self, **_: Any) -> FakeSearchResponse:
            return FakeSearchResponse()

    class FakeEmbedding:
        def embed_query(self, _: str) -> List[float]:
            return [0.0]

    class FakeRag:
        def get_qdrant_manager(self) -> FakeQdrant:
            return FakeQdrant()

        def get_embedding_client(self) -> FakeEmbedding:
            return FakeEmbedding()

    monkeypatch.setattr(tools_module, "RAGComponent", FakeRag)
    result = await tools_module.search_knowledge_base.ainvoke({"query": "test", "top_k": 1})
    assert isinstance(result, list)


def test_aggregator_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    record = types.SimpleNamespace(
        gene_symbol="GENE",
        variant_hgvs_c="c.1A>T",
        variant_hgvs_p="p.X",
        protein_change="p.X",
        evidence_strength="PS3",
        evidence_classification="Pathogenic",
        document_id=1,
        overall_confidence=90.0,
        arbitration_score=1.0,
        is_valid="true",
    )

    class FakePostgres:
        def search_evidence_by_gene(self, *_: Any, **__: Any) -> List[Any]:
            return [record]

        def search_evidence_by_variant(self, *_: Any, **__: Any) -> List[Any]:
            return [record]

        def search_evidence_multi(self, *_: Any, **__: Any) -> List[Any]:
            return [record]

    monkeypatch.setattr(aggregator_module, "get_postgres_client", lambda: FakePostgres())
    engine = aggregator_module.EvidenceAggregationEngine()
    assert engine.aggregate_by_gene("GENE").variants
    assert engine.aggregate_by_variant("c.1A>T").variants
    assert engine.aggregate_multi(gene_symbol="GENE").variants
    overview = engine.quality_overview("GENE")
    assert overview["total_evidence"] == 1


def test_association_service_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeNeo4j:
        def find_gene_related_variants(self, *_: Any, **__: Any) -> List[Dict[str, Any]]:
            return [{"variant": "c.1A>T", "document_id": 1}]

        def run_query(self, query: str, *_: Any, **__: Any) -> List[Dict[str, Any]]:
            if "HAS_VARIANT" in query:
                return [{"variant": "c.1A>T", "doc_ids": [1]}]
            return [{"disease": "d", "doc_ids": [1]}]

        def find_variant_evidence_graph(self, *_: Any, **__: Any) -> List[Dict[str, Any]]:
            return [{"g": {"symbol": "GENE"}, "p": {"description": "ph"}, "doc": {"document_id": 1}}]

    class FakePostgres:
        def search_evidence_by_gene(self, *_: Any, **__: Any) -> List[Any]:
            return []

        def search_evidence_by_variant(self, *_: Any, **__: Any) -> List[Any]:
            return []

    monkeypatch.setattr(assoc_module, "get_neo4j_client", lambda: FakeNeo4j())
    monkeypatch.setattr(assoc_module, "get_postgres_client", lambda: FakePostgres())
    analyzer = assoc_module.EntityAssociationAnalyzer()
    assert analyzer.analyze_gene_associations("GENE").links
    assert analyzer.analyze_variant_associations("c.1A>T").links
    assert analyzer.build_co_occurrence_matrix("GENE")
    assert analyzer.find_evidence_chains("GENE", min_documents=1)


def test_graph_search_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeNeo4j:
        def find_variant_evidence_graph(self, *_: Any, **__: Any) -> List[Dict[str, Any]]:
            return [
                {
                    "v": {"hgvs_c": "c.1A>T"},
                    "g": {"symbol": "GENE"},
                    "p": {"description": "ph"},
                    "e": {"evidence_id": "1"},
                    "doc": {"document_id": 1},
                }
            ]

        def find_gene_related_variants(self, *_: Any, **__: Any) -> List[Dict[str, Any]]:
            return [{"gene": "GENE", "variant": "c.1A>T", "document_id": 1, "doc_title": "doc"}]

        def find_multi_document_evidence(self, *_: Any, **__: Any) -> List[Dict[str, Any]]:
            return [{"gene": "GENE", "variant": "c.1A>T", "document_id": 1}]

    class FakePostgres:
        def search_evidence_by_variant(self, *_: Any, **__: Any) -> List[Any]:
            return []

        def search_evidence_by_gene(self, *_: Any, **__: Any) -> List[Any]:
            return []

        def search_evidence_multi(self, *_: Any, **__: Any) -> List[Any]:
            return []

        def get_evidence_for_document(self, *_: Any, **__: Any) -> List[Any]:
            return []

    monkeypatch.setattr(search_module, "get_neo4j_client", lambda: FakeNeo4j())
    monkeypatch.setattr(search_module, "get_postgres_client", lambda: FakePostgres())
    engine = search_module.GraphSearchEngine()
    assert engine.search_by_variant("c.1A>T").nodes
    assert engine.search_by_gene("GENE").nodes
    assert engine.search_multi(gene_symbol="GENE").nodes
    assert engine.get_document_evidence(1).document_count == 0


def test_graph_sync_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeNeo4j:
        def upsert_document(self, *_: Any, **__: Any) -> None:
            return None

        def upsert_gene(self, *_: Any, **__: Any) -> None:
            return None

        def upsert_variant(self, *_: Any, **__: Any) -> None:
            return None

        def link_gene_variant(self, *_: Any, **__: Any) -> None:
            return None

        def link_document_entity(self, *_: Any, **__: Any) -> None:
            return None

        def upsert_transcript(self, *_: Any, **__: Any) -> None:
            return None

        def link_gene_transcript(self, *_: Any, **__: Any) -> None:
            return None

        def upsert_disease(self, *_: Any, **__: Any) -> None:
            return None

        def link_disease_gene(self, *_: Any, **__: Any) -> None:
            return None

        def upsert_phenotype(self, *_: Any, **__: Any) -> None:
            return None

        def link_variant_phenotype(self, *_: Any, **__: Any) -> None:
            return None

        def upsert_species(self, *_: Any, **__: Any) -> None:
            return None

        def upsert_evidence(self, *_: Any, **__: Any) -> None:
            return None

        def link_variant_evidence(self, *_: Any, **__: Any) -> None:
            return None

        def link_evidence_document(self, *_: Any, **__: Any) -> None:
            return None

    class FakePostgres:
        def create_evidence_record(self, *_: Any, **__: Any) -> Any:
            return types.SimpleNamespace(evidence_id=1)

    monkeypatch.setattr(sync_module, "get_neo4j_client", lambda: FakeNeo4j())
    monkeypatch.setattr(sync_module, "get_postgres_client", lambda: FakePostgres())
    svc = sync_module.GraphSyncService()
    result = svc.sync_evidence(1, {"ps3_evidence": {}, "arbitration_score": 0.0})
    assert result["pg_evidence_id"] == 1


@pytest.mark.asyncio
async def test_graph_api_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResult:
        def __init__(self) -> None:
            self.total_evidence = 0
            self.variants = []

        def to_dict(self) -> Dict[str, Any]:
            return {"ok": True}

    class FakeEngine:
        def search_multi(self, **_: Any) -> FakeResult:
            return FakeResult()

        def search_by_gene(self, *_: Any, **__: Any) -> FakeResult:
            return FakeResult()

        def search_by_variant(self, *_: Any, **__: Any) -> FakeResult:
            return FakeResult()

        def get_document_evidence(self, *_: Any, **__: Any) -> FakeResult:
            return FakeResult()

    class FakeAnalyzer:
        def analyze_gene_associations(self, *_: Any, **__: Any) -> Any:
            return types.SimpleNamespace(links=[], to_dict=lambda: {"ok": True})

        def analyze_variant_associations(self, *_: Any, **__: Any) -> Any:
            return types.SimpleNamespace(links=[], to_dict=lambda: {"ok": True})

        def build_co_occurrence_matrix(self, *_: Any, **__: Any) -> Dict[str, Any]:
            return {}

        def find_evidence_chains(self, *_: Any, **__: Any) -> List[Any]:
            return []

    class FakeAggregation:
        def aggregate_multi(self, **_: Any) -> Any:
            return types.SimpleNamespace(variants=[], to_dict=lambda: {"ok": True})

        def aggregate_by_gene(self, *_: Any, **__: Any) -> Any:
            return types.SimpleNamespace(variants=[], to_dict=lambda: {"ok": True})

        def aggregate_by_variant(self, *_: Any, **__: Any) -> Any:
            return types.SimpleNamespace(variants=[], to_dict=lambda: {"ok": True})

        def quality_overview(self, *_: Any, **__: Any) -> Dict[str, Any]:
            return {"total_evidence": 0}

    class FakeSync:
        def resync_document(self, *_: Any, **__: Any) -> Dict[str, Any]:
            return {"total": 0, "synced": 0, "failed": 0}

    class FakeNeo4j:
        def get_graph_statistics(self) -> Dict[str, Any]:
            return {}

    monkeypatch.setattr(graph_api_module, "get_graph_search_engine", lambda: FakeEngine())
    monkeypatch.setattr(graph_api_module, "get_entity_association_analyzer", lambda: FakeAnalyzer())
    monkeypatch.setattr(graph_api_module, "get_evidence_aggregation_engine", lambda: FakeAggregation())
    monkeypatch.setattr(graph_api_module, "get_graph_sync_service", lambda: FakeSync())
    monkeypatch.setattr(graph_api_module, "get_neo4j_client", lambda: FakeNeo4j())

    req = graph_api_module.EvidenceSearchRequest(
        gene_symbol="GENE",
        variant=None,
        protein_change=None,
        disease_name=None,
        min_confidence=None,
        only_valid=False,
    )
    assert (await graph_api_module.search_evidence(req)).code == 0
    assert (await graph_api_module.search_by_gene("GENE")).code == 0
    assert (await graph_api_module.search_by_variant("c.1A>T")).code == 0
    assert (await graph_api_module.get_document_evidence(1)).code == 0
    assert (await graph_api_module.analyze_gene_associations("GENE")).code == 0
    assert (await graph_api_module.analyze_variant_associations("c.1A>T")).code == 0
    assert (await graph_api_module.get_co_occurrence_matrix("GENE")).code == 0
    assert (await graph_api_module.get_evidence_chains("GENE", min_documents=1)).code == 0
    assert (await graph_api_module.aggregate_evidence(req)).code == 0
    assert (await graph_api_module.aggregate_by_gene("GENE")).code == 0
    assert (await graph_api_module.aggregate_by_variant(variant="c.1A>T")).code == 0
    assert (await graph_api_module.quality_overview(gene_symbol=None)).code == 0
    assert (await graph_api_module.graph_statistics()).code == 0
    assert (await graph_api_module.resync_document(1)).code == 0
