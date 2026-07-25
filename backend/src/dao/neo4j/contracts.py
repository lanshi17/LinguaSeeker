"""Neo4j data access contracts.

Typed contracts for graph nodes, edges, and subgraph contexts. Keeping these
as dataclasses avoids exposing raw Neo4j Record objects to business logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GraphNode:
    """A node in the knowledge graph."""

    node_id: str
    labels: tuple[str, ...]
    properties: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphEdge:
    """A relationship in the knowledge graph."""

    source_id: str
    target_id: str
    rel_type: str
    properties: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphTriplet:
    """A subject-predicate-object triplet."""

    subject: GraphNode
    predicate: GraphEdge
    object: GraphNode


@dataclass
class SubgraphContext:
    """Subgraph retrieved for LLM context augmentation."""

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    summary_text: str = ""
    source_evidence_ids: list[str] = field(default_factory=list)
