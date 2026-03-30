from __future__ import annotations

from typing import Any, Optional, cast
from unittest.mock import MagicMock, patch

import pytest

from src.agents.reasoning.node import (
    _build_reasoning_summary,
    _extract_gene_symbol,
    _extract_protein_change,
    _extract_variant_hgvs,
    _query_knowledge_graph_sync,
    run_reasoning_node,
)
from src.state.global_state import SupervisorState


def _make_state(**overrides: Any) -> SupervisorState:
    base: dict[str, Any] = {
        "request_id": "test-req-1",
        "paper_task_id": "test-task-1",
        "document_id": "test-doc-1",
        "celery_task_id": "test-celery-1",
        "source": "upload",
        "file_paths": [],
        "urls": [],
        "pmids": [],
        "current_node": "extraction",
        "workflow_status": "extracting_evidence",
        "processing_steps": [],
        "node_trace": [],
        "retries": {},
        "warnings": [],
        "errors": [],
        "requires_human_review": False,
        "parsing_result": None,
        "parser_backend": None,
        "markdown_content": "",
        "image_paths": [],
        "image_inputs": [],
        "sentence_alignments": None,
        "translated_markdown": "",
        "image_descriptions": [],
        "evidence_output": None,
        "extracted_fields": None,
        "arbitration_confidence": None,
        "final_evidence_strength": None,
        "acmg_result": None,
        "graph_context": None,
        "evidence_sources": None,
        "output_files": None,
        "final_result": None,
        "_inner_processing_state": None,
    }
    base.update(overrides)
    return cast(SupervisorState, base)


def _make_gene_mock(symbol: str) -> MagicMock:
    gene = MagicMock()
    gene.symbol = symbol
    return gene


def _make_variant_mock(hgvs_c: Optional[str] = None, hgvs_p: Optional[str] = None) -> MagicMock:
    variant = MagicMock()
    variant.hgvs_c = hgvs_c
    variant.hgvs_p = hgvs_p
    return variant


class TestExtractGeneSymbol:
    def test_from_extracted_fields(self) -> None:
        fields = MagicMock()
        fields.gene = _make_gene_mock("BRCA1")
        state = _make_state(extracted_fields=fields)
        assert _extract_gene_symbol(state) == "BRCA1"

    def test_from_evidence_output(self) -> None:
        evidence = {"gene": {"symbol": "TP53"}}
        state = _make_state(evidence_output=evidence)
        assert _extract_gene_symbol(state) == "TP53"

    def test_none_when_missing(self) -> None:
        state = _make_state()
        assert _extract_gene_symbol(state) is None

    def test_fields_takes_precedence(self) -> None:
        fields = MagicMock()
        fields.gene = _make_gene_mock("BRCA1")
        evidence = {"gene": {"symbol": "TP53"}}
        state = _make_state(extracted_fields=fields, evidence_output=evidence)
        assert _extract_gene_symbol(state) == "BRCA1"


class TestExtractVariantHgvs:
    def test_from_extracted_fields(self) -> None:
        fields = MagicMock()
        fields.variant = _make_variant_mock(hgvs_c="c.1234A>G")
        state = _make_state(extracted_fields=fields)
        assert _extract_variant_hgvs(state) == "c.1234A>G"

    def test_from_evidence_output(self) -> None:
        evidence = {"variant": {"hgvs_c": "c.5678T>C"}}
        state = _make_state(evidence_output=evidence)
        assert _extract_variant_hgvs(state) == "c.5678T>C"


class TestExtractProteinChange:
    def test_from_extracted_fields(self) -> None:
        fields = MagicMock()
        fields.variant = _make_variant_mock(hgvs_p="p.Val600Glu")
        state = _make_state(extracted_fields=fields)
        assert _extract_protein_change(state) == "p.Val600Glu"


class TestQueryKnowledgeGraphSync:
    def test_no_identifiers_returns_none(self) -> None:
        assert _query_knowledge_graph_sync(None, None, None) is None

    @patch("src.infrastructure.neo4j.get_neo4j_client")
    def test_happy_path(self, mock_get_client: MagicMock) -> None:
        client = MagicMock()
        client.find_variant_evidence_graph.return_value = [{"v": "var1"}]
        client.find_gene_related_variants.return_value = [{"gene": "BRCA1"}]
        client.find_multi_document_evidence.return_value = [{"doc": "d1"}]
        mock_get_client.return_value = client

        result = _query_knowledge_graph_sync("BRCA1", "c.1234A>G", "p.Val600Glu")
        assert result is not None
        assert result["gene_symbol"] == "BRCA1"
        assert len(result["variant_evidence"]) == 1
        assert len(result["gene_variants"]) == 1
        assert len(result["multi_doc_evidence"]) == 1

    @patch("src.infrastructure.neo4j.get_neo4j_client")
    def test_only_gene(self, mock_get_client: MagicMock) -> None:
        client = MagicMock()
        client.find_gene_related_variants.return_value = [{"gene": "TP53"}]
        client.find_multi_document_evidence.return_value = []
        mock_get_client.return_value = client

        result = _query_knowledge_graph_sync("TP53", None, None)
        assert result is not None
        assert result["gene_symbol"] == "TP53"
        assert result["variant_hgvs_c"] is None

    @patch("src.infrastructure.neo4j.get_neo4j_client")
    def test_only_variant(self, mock_get_client: MagicMock) -> None:
        client = MagicMock()
        client.find_variant_evidence_graph.return_value = [{"v": "data"}]
        client.find_multi_document_evidence.return_value = []
        mock_get_client.return_value = client

        result = _query_knowledge_graph_sync(None, "c.1234A>G", None)
        assert result is not None
        assert result["variant_hgvs_c"] == "c.1234A>G"

    @patch("src.infrastructure.neo4j.get_neo4j_client")
    def test_neo4j_client_unavailable(self, mock_get_client: MagicMock) -> None:
        mock_get_client.side_effect = ConnectionError("Neo4j down")
        result = _query_knowledge_graph_sync("BRCA1", "c.1234A>G", None)
        assert result is None

    @patch("src.infrastructure.neo4j.get_neo4j_client")
    def test_empty_results(self, mock_get_client: MagicMock) -> None:
        client = MagicMock()
        client.find_variant_evidence_graph.return_value = []
        client.find_gene_related_variants.return_value = []
        client.find_multi_document_evidence.return_value = []
        mock_get_client.return_value = client

        result = _query_knowledge_graph_sync("BRCA1", "c.1234A>G", None)
        assert result is None


class TestBuildReasoningSummary:
    def test_basic_summary(self) -> None:
        ctx: dict[str, Any] = {
            "gene_symbol": "BRCA1",
            "variant_hgvs_c": "c.1234A>G",
            "protein_change": None,
            "variant_evidence": [{"v": "rec1"}, {"v": "rec2"}],
            "gene_variants": [],
            "multi_doc_evidence": [{"doc": "d1"}],
        }
        summary = _build_reasoning_summary(ctx)
        assert "BRCA1" in summary
        assert "c.1234A>G" in summary
        assert "Variant Evidence (2 records)" in summary
        assert "Multi-Document Evidence (1 records)" in summary

    def test_empty_context(self) -> None:
        ctx: dict[str, Any] = {
            "gene_symbol": None,
            "variant_hgvs_c": None,
            "protein_change": None,
            "variant_evidence": [],
            "gene_variants": [],
            "multi_doc_evidence": [],
        }
        summary = _build_reasoning_summary(ctx)
        assert summary == ""

    def test_truncates_long_lists(self) -> None:
        ctx: dict[str, Any] = {
            "gene_symbol": "BRCA1",
            "variant_hgvs_c": None,
            "protein_change": None,
            "variant_evidence": [{"v": f"rec{i}"} for i in range(10)],
            "gene_variants": [],
            "multi_doc_evidence": [],
        }
        summary = _build_reasoning_summary(ctx)
        assert "... and 5 more" in summary


class TestRunReasoningNode:
    @patch("src.agents.reasoning.node._query_knowledge_graph_sync")
    def test_sets_current_node(self, mock_query: MagicMock) -> None:
        mock_query.return_value = None
        state = _make_state()
        result = run_reasoning_node(state)
        assert result["current_node"] == "reasoning"

    @patch("src.agents.reasoning.node._query_knowledge_graph_sync")
    def test_with_graph_context(self, mock_query: MagicMock) -> None:
        mock_query.return_value = {
            "gene_symbol": "BRCA1",
            "variant_evidence": [{"v": "data"}],
            "gene_variants": [],
            "multi_doc_evidence": [],
        }
        fields = MagicMock()
        fields.gene = _make_gene_mock("BRCA1")
        fields.variant = _make_variant_mock(hgvs_c="c.1234A>G", hgvs_p="p.Val600Glu")
        state = _make_state(extracted_fields=fields)
        result = run_reasoning_node(state)
        assert result["graph_context"] is not None
        assert "reasoning_summary" in result["graph_context"]

    @patch("src.agents.reasoning.node._query_knowledge_graph_sync")
    def test_no_graph_context(self, mock_query: MagicMock) -> None:
        mock_query.return_value = None
        state = _make_state()
        result = run_reasoning_node(state)
        assert result["graph_context"] is None

    @patch("src.agents.reasoning.node._query_knowledge_graph_sync")
    def test_preserves_state(self, mock_query: MagicMock) -> None:
        mock_query.return_value = None
        state = _make_state(
            markdown_content="test content",
            evidence_output={"some": "data"},
        )
        result = run_reasoning_node(state)
        assert result["markdown_content"] == "test content"
        assert result["evidence_output"] == {"some": "data"}
