"""Format retrieved subgraphs into LLM-readable context text."""

from __future__ import annotations

from src.dao.neo4j.contracts import GraphEdge, SubgraphContext


class ContextFormatter:
    """Convert a Neo4j subgraph into a concise textual context block."""

    def __init__(self, max_nodes: int = 100, max_edges: int = 150) -> None:
        self._max_nodes = max_nodes
        self._max_edges = max_edges

    def format(self, subgraph: SubgraphContext) -> str:
        """Return a formatted context string for prompt injection."""
        if not subgraph.nodes:
            return ""

        nodes = subgraph.nodes[: self._max_nodes]
        edges = subgraph.edges[: self._max_edges]

        lines: list[str] = []
        lines.append("## Relevant biomedical knowledge graph context")
        lines.append("")
        lines.append("### Entities")
        for node in nodes:
            labels = ":".join(node.labels)
            display = node.properties.get("display_name", node.node_id)
            external_id = node.properties.get("external_id", "")
            id_part = f" ({external_id})" if external_id else ""
            lines.append(f"- [{labels}] {display}{id_part}")

        if edges:
            lines.append("")
            lines.append("### Relationships")
            for edge in edges:
                source_name = self._display_name_for(subgraph, edge.source_id)
                target_name = self._display_name_for(subgraph, edge.target_id)
                props = self._format_edge_properties(edge)
                lines.append(f"- {source_name} --[{edge.rel_type}]{props}--> {target_name}")

        if subgraph.source_evidence_ids:
            lines.append("")
            lines.append(f"### Source evidence IDs ({len(subgraph.source_evidence_ids)})")

        return "\n".join(lines)

    @staticmethod
    def _display_name_for(subgraph: SubgraphContext, node_id: str) -> str:
        for node in subgraph.nodes:
            if node.node_id == node_id:
                return str(node.properties.get("display_name", node.node_id))
        return node_id

    @staticmethod
    def _format_edge_properties(edge: GraphEdge) -> str:
        if not edge.properties:
            return ""
        items = []
        for key, value in edge.properties.items():
            if value is None:
                continue
            items.append(f"{key}={value}")
        return " {" + ", ".join(items) + "}" if items else ""
