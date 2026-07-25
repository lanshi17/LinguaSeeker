"""Business-level GraphRAG contracts.

These contracts are intentionally separate from ``src.dao.neo4j.contracts``:
- ``dao.neo4j.contracts`` describes the generic graph store representation.
- ``core.graph_rag.contracts`` describes the biomedical/literature domain
  concepts (genes, variants, diseases, evidence) before persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field


class GraphEntityType(str, Enum):
    """Node labels used in the LinguaSeeker knowledge graph."""

    GENE = "Gene"
    VARIANT = "Variant"
    DISEASE = "Disease"
    PHENOTYPE = "Phenotype"
    EVIDENCE = "Evidence"
    DOCUMENT = "Document"
    PROCESSING_RUN = "ProcessingRun"


class GraphRelationType(str, Enum):
    """Relationship types used in the LinguaSeeker knowledge graph."""

    # Terminology-derived relations
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    HAS_DOSAGE_SENSITIVITY = "HAS_DOSAGE_SENSITIVITY"
    HAS_CLINICAL_SIGNIFICANCE = "HAS_CLINICAL_SIGNIFICANCE"
    IS_A = "IS_A"

    # Literature-derived relations
    HAS_PHENOTYPE = "HAS_PHENOTYPE"
    MENTIONS = "MENTIONS"
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    FROM_DOCUMENT = "FROM_DOCUMENT"
    FROM_RUN = "FROM_RUN"


@dataclass(frozen=True)
class LiteratureGraphNode:
    """A domain node to be persisted in the knowledge graph."""

    node_id: str
    entity_type: GraphEntityType
    display_name: str
    properties: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class LiteratureGraphEdge:
    """A domain edge to be persisted in the knowledge graph."""

    source_id: str
    target_id: str
    relation_type: GraphRelationType
    properties: dict[str, object] = field(default_factory=dict)


@dataclass
class LiteratureGraphBatch:
    """A batch of nodes and edges ready for graph persistence."""

    nodes: list[LiteratureGraphNode] = field(default_factory=list)
    edges: list[LiteratureGraphEdge] = field(default_factory=list)

    def add_node(
        self,
        node_id: str,
        entity_type: GraphEntityType,
        display_name: str,
        properties: dict[str, object] | None = None,
    ) -> None:
        """Add a node if it is not already present (by node_id)."""
        for existing in self.nodes:
            if existing.node_id == node_id:
                return
        self.nodes.append(
            LiteratureGraphNode(
                node_id=node_id,
                entity_type=entity_type,
                display_name=display_name,
                properties=properties or {},
            )
        )

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation_type: GraphRelationType,
        properties: dict[str, object] | None = None,
    ) -> None:
        """Add an edge if it is not already present."""
        for existing in self.edges:
            if (
                existing.source_id == source_id
                and existing.target_id == target_id
                and existing.relation_type == relation_type
            ):
                return
        self.edges.append(
            LiteratureGraphEdge(
                source_id=source_id,
                target_id=target_id,
                relation_type=relation_type,
                properties=properties or {},
            )
        )


# ── API Contracts ─────────────────────────────────────────────────────────


class GraphNodeResponse(BaseModel):
    """A graph node serialized for the frontend."""

    node_id: str
    labels: list[str]
    display_name: str
    properties: dict[str, object] = Field(default_factory=dict)


class GraphEdgeResponse(BaseModel):
    """A graph edge serialized for the frontend."""

    source_id: str
    target_id: str
    rel_type: str
    properties: dict[str, object] = Field(default_factory=dict)


class GraphSubgraphResponse(BaseModel):
    """Subgraph payload returned by the graph query endpoint."""

    nodes: list[GraphNodeResponse] = Field(default_factory=list)
    edges: list[GraphEdgeResponse] = Field(default_factory=list)


class GraphRagQueryRequest(BaseModel):
    """Natural-language question against the knowledge graph."""

    question: str = Field(..., min_length=1, description="Natural-language question")
    hops: int = Field(default=2, ge=1, le=4, description="Subgraph expansion hops")
    mode: str = Field(default="full", description="terminology_only or full")


class CitationResponse(BaseModel):
    """Citation to an evidence node and its source document."""

    evidence_node_id: str
    document_id: str | None = None
    pmid: str | None = None
    quote: str | None = None


class GraphRagQueryResponse(BaseModel):
    """Answer generated from the knowledge graph plus supporting subgraph."""

    question: str
    answer: str
    subgraph: GraphSubgraphResponse
    source_evidence_ids: list[str] = Field(default_factory=list)
    citations: list[CitationResponse] = Field(default_factory=list)
