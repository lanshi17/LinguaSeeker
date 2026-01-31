"""Graph Repository interface.

Defines the contract for knowledge graph operations in Neo4j.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import UUID


class GraphRepository(ABC):
    """Abstract repository for Neo4j graph operations.

    Handles variant, phenotype, and evidence relationships
    for cross-document knowledge aggregation.
    """

    @abstractmethod
    async def create_document_node(
        self, document_id: UUID, properties: Dict[str, Any]
    ) -> bool:
        """Create a document node in the graph.

        Args:
            document_id: Document UUID
            properties: Node properties (title, pmid, doi, etc.)

        Returns:
            True if created successfully
        """
        pass

    @abstractmethod
    async def create_variant_node(
        self, variant_id: UUID, properties: Dict[str, Any]
    ) -> bool:
        """Create a variant node in the graph.

        Args:
            variant_id: Variant UUID
            properties: Node properties (hgvs_notation, gene, etc.)

        Returns:
            True if created successfully
        """
        pass

    @abstractmethod
    async def create_evidence_node(
        self, evidence_id: UUID, properties: Dict[str, Any]
    ) -> bool:
        """Create an evidence node in the graph.

        Args:
            evidence_id: Evidence UUID
            properties: Node properties (acmg_code, confidence, etc.)

        Returns:
            True if created successfully
        """
        pass

    @abstractmethod
    async def create_phenotype_node(
        self, phenotype_id: UUID, properties: Dict[str, Any]
    ) -> bool:
        """Create a phenotype node in the graph.

        Args:
            phenotype_id: Phenotype UUID
            properties: Node properties (hpo_code, description, etc.)

        Returns:
            True if created successfully
        """
        pass

    @abstractmethod
    async def link_document_mentions_variant(
        self, document_id: UUID, variant_id: UUID, properties: Dict[str, Any]
    ) -> bool:
        """Create MENTIONS relationship between document and variant.

        Args:
            document_id: Document UUID
            variant_id: Variant UUID
            properties: Relationship properties (first_page, mention_count)

        Returns:
            True if relationship created
        """
        pass

    @abstractmethod
    async def link_evidence_supports_variant(
        self, evidence_id: UUID, variant_id: UUID, weight: float
    ) -> bool:
        """Create SUPPORTS relationship between evidence and variant.

        Args:
            evidence_id: Evidence UUID
            variant_id: Variant UUID
            weight: Support weight/strength

        Returns:
            True if relationship created
        """
        pass

    @abstractmethod
    async def link_variant_associated_with_phenotype(
        self, variant_id: UUID, phenotype_id: UUID, strength: str
    ) -> bool:
        """Create ASSOCIATED_WITH relationship between variant and phenotype.

        Args:
            variant_id: Variant UUID
            phenotype_id: Phenotype UUID
            strength: Association strength (STRONG, MODERATE, WEAK)

        Returns:
            True if relationship created
        """
        pass

    @abstractmethod
    async def find_variants_for_gene(
        self, gene: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Find all variants for a specific gene.

        Args:
            gene: Gene symbol
            limit: Maximum number of variants to return

        Returns:
            List of variant nodes with properties
        """
        pass

    @abstractmethod
    async def find_evidence_for_variant(
        self, variant_id: UUID
    ) -> List[Dict[str, Any]]:
        """Find all evidence supporting a variant.

        Args:
            variant_id: Variant UUID

        Returns:
            List of evidence nodes with properties
        """
        pass

    @abstractmethod
    async def find_documents_mentioning_variant(
        self, variant_id: UUID
    ) -> List[Dict[str, Any]]:
        """Find all documents mentioning a variant.

        Args:
            variant_id: Variant UUID

        Returns:
            List of document nodes with properties
        """
        pass

    @abstractmethod
    async def find_phenotypes_for_variant(
        self, variant_id: UUID
    ) -> List[Dict[str, Any]]:
        """Find all phenotypes associated with a variant.

        Args:
            variant_id: Variant UUID

        Returns:
            List of phenotype nodes with properties
        """
        pass

    @abstractmethod
    async def traverse_evidence_stacking(
        self, variant_id: UUID, max_hops: int = 2
    ) -> Dict[str, Any]:
        """Traverse graph to find evidence stacking opportunities.

        Performs 2-hop traversal to find cross-document evidence
        that can elevate variant classification.

        Args:
            variant_id: Variant UUID
            max_hops: Maximum traversal depth

        Returns:
            Dictionary with stacked evidence analysis
        """
        pass

    @abstractmethod
    async def find_related_variants(
        self, variant_id: UUID, relationship_type: str = "ASSOCIATED_WITH"
    ) -> List[Dict[str, Any]]:
        """Find variants related through phenotypes or evidence.

        Args:
            variant_id: Variant UUID
            relationship_type: Type of relationship to traverse

        Returns:
            List of related variant nodes
        """
        pass

    @abstractmethod
    async def sync_from_postgres(
        self, entity_type: str, entity_id: UUID, properties: Dict[str, Any]
    ) -> bool:
        """Sync entity from PostgreSQL to Neo4j.

        Args:
            entity_type: Type of entity (document, variant, evidence, phenotype)
            entity_id: Entity UUID
            properties: Entity properties to sync

        Returns:
            True if synced successfully
        """
        pass

    @abstractmethod
    async def delete_node(self, entity_type: str, entity_id: UUID) -> bool:
        """Delete a node from the graph.

        Args:
            entity_type: Type of entity
            entity_id: Entity UUID

        Returns:
            True if deleted
        """
        pass

    @abstractmethod
    async def execute_cypher(
        self, query: str, parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute raw Cypher query.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            Query results
        """
        pass
