from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from src.domain.graph import association_service as assoc_module
from src.domain.graph import search as search_module
from src.domain.graph import sync as sync_module


class DummyVariationService:
    def __init__(self, variation_id: Optional[int] = 101) -> None:
        self.variation_id = variation_id

    def resolve_variation(self, *_: Any, **__: Any):
        if self.variation_id is None:
            return None
        return SimpleNamespace(variation_id=self.variation_id)

    def build_variation_payload(self, variation_id: int) -> Dict[str, Any]:
        return {
            "variation": {"variation_id": variation_id, "primary_hgvs": "c.1A>T"},
            "citations": [],
            "scorecards": [],
        }

    def sync_clinvar_citations(self, *_: Any, **__: Any) -> None:
        return None

    def sync_clingen_profiles(self, *_: Any, **__: Any) -> None:
        return None

    def record_internal_citation(self, *_: Any, **__: Any) -> None:
        return None


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
    monkeypatch.setattr(
        search_module,
        "get_variation_data_service",
        lambda: DummyVariationService(),
    )
    engine = search_module.GraphSearchEngine()

    result = engine.search_by_variant("c.1A>T")
    assert result.total_evidence == 1
    assert result.document_count == 1
    assert any(node.node_type == "gene" for node in result.nodes)


def test_graph_sync_evidence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    monkeypatch.setattr(
        sync_module,
        "get_variation_data_service",
        lambda: DummyVariationService(),
    )

    monkeypatch.setattr(
        sync_module.GraphSyncService,
        "_FAILURE_ARCHIVE_PATH",
        tmp_path / "failures.jsonl",
    )
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
    assert fake_pg.kwargs["clinvar_variation_id"] == 101
    assert fake_pg.kwargs["arbitration_score"] == 88.0
    assert fake_pg.kwargs["ps3_evidence"]["annotation_schema_version"] == "1.0"
    assert fake_pg.kwargs["is_valid"] == "true"
    assert "variant" in calls
    assert "evidence" in calls


def test_graph_sync_structural_variant_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class MinimalNeo4j:
        def __init__(self) -> None:
            self.variant_props: Dict[str, Any] = {}

        def upsert_document(self, *_: Any, **__: Any) -> None:
            return None

        def upsert_gene(self, *_: Any, **__: Any) -> None:
            return None

        def upsert_variant(self, hgvs_c: Optional[str], **props: Any) -> None:
            self.variant_props = {"hgvs_c": hgvs_c, **props}

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

        def upsert_evidence(self, *_: Any, **__: Any) -> None:
            return None

        def link_variant_evidence(self, *_: Any, **__: Any) -> None:
            return None

        def link_evidence_document(self, *_: Any, **__: Any) -> None:
            return None

    neo = MinimalNeo4j()

    class CapturePostgres:
        def __init__(self) -> None:
            self.kwargs: Dict[str, Any] = {}
            self.updated: List[Dict[str, Any]] = []
            self.tasks: List[Dict[str, Any]] = []
            self.logs: List[Dict[str, Any]] = []

        def create_evidence_record(self, **kwargs: Any) -> Any:
            self.kwargs = kwargs
            return SimpleNamespace(evidence_id=42)

        def get_evidence_for_document(self, *_: Any, **__: Any) -> List[Any]:
            return []

        def update_document(self, document_id: Any, **fields: Any) -> Any:
            self.updated.append({"document_id": document_id, "fields": fields})
            return SimpleNamespace(document_id=document_id, **fields)

        def create_task(
            self,
            document_id: Any,
            task_type: str,
            status: str,
            result: Dict[str, Any],
        ) -> Any:
            payload = {
                "document_id": document_id,
                "task_type": task_type,
                "status": status,
                "result": result,
            }
            self.tasks.append(payload)
            return SimpleNamespace(task_id=len(self.tasks))

        def append_task_log(
            self,
            document_id: Any,
            status: str,
            category: str,
            payload: Dict[str, Any],
            missing_fields_detail: Dict[str, Any],
            task_id: Optional[int] = None,
        ) -> None:
            self.logs.append(
                {
                    "document_id": document_id,
                    "status": status,
                    "category": category,
                    "payload": payload,
                    "missing_fields_detail": missing_fields_detail,
                    "task_id": task_id,
                }
            )

    pg = CapturePostgres()
    monkeypatch.setattr(sync_module, "get_neo4j_client", lambda: neo)
    monkeypatch.setattr(sync_module, "get_postgres_client", lambda: pg)
    monkeypatch.setattr(
        sync_module,
        "get_variation_data_service",
        lambda: DummyVariationService(variation_id=None),
    )
    archive_path = tmp_path / "structural_failures.jsonl"
    monkeypatch.setattr(sync_module.GraphSyncService, "_FAILURE_ARCHIVE_PATH", archive_path)
    service = sync_module.GraphSyncService()
    evidence_output = {
        "origin_format_md": "Clinicians observed an exons 2-3 deletion consistent with LDLR CNV.",
        "extracted_fields": {
            "gene": {"symbol": "LDLR"},
            "variant": {"evidence_quote": "Patients show large exons 2-3 deletion."},
            "transcript_id": {"transcript_id": "NM_000527.4"},
            "disease_chpo": {"disease_name": "Familial Hypercholesterolemia"},
        },
        "ps3_evidence": {},
        "overall_confidence": 65.0,
    }
    result = service.sync_evidence("00000000-0000-0000-0000-000000000001", evidence_output)
    assert result["pg_evidence_id"] == 42
    synthetic = pg.kwargs["variant_hgvs_c"]
    assert synthetic.startswith("NM_000527.4:c.(?_?)del")
    structural_hint = pg.kwargs["extracted_fields"].get("_structural_variant")
    assert structural_hint["exon_range"] == "2-3"
    assert structural_hint["structural_type"] == "DELETION"
    assert pg.updated and pg.updated[0]["fields"].get("status") == "pending_manual_review"
    assert pg.tasks and pg.tasks[0]["status"] == "pending_manual_review"
    assert pg.logs and pg.logs[0]["status"] == "pending_manual_review"
def test_graph_sync_skips_when_core_fields_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class NoopNeo4j:
        def __getattr__(self, _: str) -> Any:
            return lambda *args, **kwargs: None

    class GuardedPostgres:
        def create_evidence_record(self, **_: Any) -> Any:
            raise AssertionError("create_evidence_record should not be called when skipping")

        def get_evidence_for_document(self, *_: Any, **__: Any) -> List[Any]:
            return []

    neo = NoopNeo4j()
    guarded_pg = GuardedPostgres()

    monkeypatch.setattr(sync_module, "get_neo4j_client", lambda: neo)
    monkeypatch.setattr(sync_module, "get_postgres_client", lambda: guarded_pg)
    monkeypatch.setattr(
        sync_module,
        "get_variation_data_service",
        lambda: DummyVariationService(),
    )

    archive_path = tmp_path / "failures.jsonl"
    monkeypatch.setattr(sync_module.GraphSyncService, "_FAILURE_ARCHIVE_PATH", archive_path)
    service = sync_module.GraphSyncService()
    result = service.sync_evidence(
        1,
        {
            "ps3_evidence": {},
            "overall_confidence": 10.0,
            "extracted_fields": {},
        },
    )

    assert result["skipped"] is True
    assert result["reason"] == "missing_core_fields"
    assert result["retryable"] is True
    assert archive_path.exists()
    assert "missing_core_fields" in archive_path.read_text()
    assert "gene_symbol" in result["missing_fields"]
