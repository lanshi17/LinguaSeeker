"""Tests for EvidenceGraphBuilder."""

from __future__ import annotations

from src.core.evidence_extraction.contracts import EvidenceChain
from src.core.graph_rag.contracts import GraphRelationType
from src.core.graph_rag.core.builder import EvidenceGraphBuilder


def test_build_from_evidence_chains_creates_gene_disease_edge() -> None:
    builder = EvidenceGraphBuilder()
    chain = EvidenceChain(
        chain_id="chain-1",
        gene_text="GLA",
        disease_text="Fabry disease",
        variant_text="p.Ala143Pro",
    )
    batch = builder.build_from_evidence_chains(
        source_document_id="doc-1",
        processing_run_id="run-1",
        chains=[chain],
    )

    node_ids = {n.node_id for n in batch.nodes}
    assert "gene:GLA" in node_ids
    assert "disease:fabry disease" in node_ids

    edges = {
        (e.source_id, e.relation_type.value, e.target_id)
        for e in batch.edges
    }
    assert ("gene:GLA", GraphRelationType.ASSOCIATED_WITH.value, "disease:fabry disease") in edges
