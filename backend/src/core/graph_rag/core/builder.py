"""Build knowledge-graph nodes and edges from extraction/standardization results."""

from __future__ import annotations

from typing import Any

from src.core.evidence_extraction.contracts import (
    EvidenceChain,
    EvidenceStatus,
    SpecialEvidenceRecord,
)
from src.core.graph_rag.contracts import (
    GraphEntityType,
    GraphRelationType,
    LiteratureGraphBatch,
)
from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    EntityMatch,
    EntityType,
    MatchStatus,
    StandardizationInput,
)


class EvidenceGraphBuilder:
    """Convert one standardization input + matches into a graph batch."""

    def __init__(self) -> None:
        self._batch = LiteratureGraphBatch()

    def build_from_standardization(
        self,
        input_data: StandardizationInput,
        matches: tuple[EntityMatch, ...],
    ) -> LiteratureGraphBatch:
        """Build a graph batch from standardized entities and evidence items."""
        self._batch = LiteratureGraphBatch()

        document_id = input_data.source_document_id
        processing_run_id = input_data.processing_run_id

        # Document and processing run nodes
        self._batch.add_node(
            node_id=document_id,
            entity_type=GraphEntityType.DOCUMENT,
            display_name=document_id,
            properties={"document_id": document_id},
        )
        self._batch.add_node(
            node_id=processing_run_id,
            entity_type=GraphEntityType.PROCESSING_RUN,
            display_name=processing_run_id,
            properties={"processing_run_id": processing_run_id},
        )

        # Extract target nodes (always add as context)
        if input_data.extraction_target is not None:
            target = input_data.extraction_target
            if target.gene_symbol:
                self._add_entity_node(
                    node_id=self._gene_node_id(target.gene_symbol),
                    entity_type=GraphEntityType.GENE,
                    display_name=target.gene_symbol,
                    external_id=None,
                )
            if target.disease_name:
                self._add_entity_node(
                    node_id=self._disease_node_id(target.disease_name),
                    entity_type=GraphEntityType.DISEASE,
                    display_name=target.disease_name,
                    external_id=None,
                )
            if target.variant_hgvs_p:
                self._add_entity_node(
                    node_id=self._variant_node_id(target.variant_hgvs_p),
                    entity_type=GraphEntityType.VARIANT,
                    display_name=target.variant_hgvs_p,
                    external_id=None,
                )

        # Standardized entity nodes from matches
        match_by_candidate_id: dict[str, EntityMatch] = {}
        for match in matches:
            match_by_candidate_id[match.candidate.candidate_id] = match
            if match.status != MatchStatus.STANDARDIZED or not match.external_id:
                continue
            entity_type = self._map_entity_type(match.candidate.entity_type)
            node_id = self._entity_node_id(match.candidate.entity_type, match.external_id)
            self._add_entity_node(
                node_id=node_id,
                entity_type=entity_type,
                display_name=match.display_name or match.candidate.raw_text,
                external_id=match.external_id,
                raw_text=match.candidate.raw_text,
            )

        # Evidence item nodes and edges to entities
        for item in input_data.evidence_items:
            evidence_node_id = self._evidence_node_id(document_id, processing_run_id, item)
            value_preview = self._preview_value(item.value)
            self._batch.add_node(
                node_id=evidence_node_id,
                entity_type=GraphEntityType.EVIDENCE,
                display_name=f"{item.field_id}: {value_preview}",
                properties={
                    "field_id": item.field_id,
                    "status": item.status.value if isinstance(item.status, EvidenceStatus) else str(item.status),
                    "confidence": item.confidence,
                    "track": getattr(item, "track", ""),
                    "group_id": getattr(item, "group_id", ""),
                },
            )
            self._batch.add_edge(
                source_id=evidence_node_id,
                target_id=document_id,
                relation_type=GraphRelationType.FROM_DOCUMENT,
            )
            self._batch.add_edge(
                source_id=evidence_node_id,
                target_id=processing_run_id,
                relation_type=GraphRelationType.FROM_RUN,
            )

            # Link evidence to standardized entities via candidate bindings
            for candidate in input_data.candidates:
                if candidate.field_id != item.field_id:
                    continue
                match = match_by_candidate_id.get(candidate.candidate_id)
                if match is None or match.status != MatchStatus.STANDARDIZED or not match.external_id:
                    continue
                entity_node_id = self._entity_node_id(candidate.entity_type, match.external_id)
                relation_type = (
                    GraphRelationType.SUPPORTS
                    if candidate.role == BindingRole.SUBJECT
                    else GraphRelationType.MENTIONS
                )
                self._batch.add_edge(
                    source_id=evidence_node_id,
                    target_id=entity_node_id,
                    relation_type=relation_type,
                    properties={"role": candidate.role.value},
                )

        return self._batch

    def build_from_evidence_chains(
        self,
        source_document_id: str,
        processing_run_id: str,
        chains: list[EvidenceChain],
    ) -> LiteratureGraphBatch:
        """Build additional gene-disease-variant-phenotype edges from evidence chains."""
        self._batch = LiteratureGraphBatch()

        self._batch.add_node(
            node_id=source_document_id,
            entity_type=GraphEntityType.DOCUMENT,
            display_name=source_document_id,
        )
        self._batch.add_node(
            node_id=processing_run_id,
            entity_type=GraphEntityType.PROCESSING_RUN,
            display_name=processing_run_id,
        )

        for chain in chains:
            gene_id = chain.gene_text or chain.gene_id or ""
            disease_id = chain.disease_text or chain.disease_id or ""
            variant_id = chain.variant_text or chain.variant_id or ""

            if gene_id:
                self._add_entity_node(
                    node_id=self._gene_node_id(gene_id),
                    entity_type=GraphEntityType.GENE,
                    display_name=gene_id,
                    external_id=chain.gene_id,
                )
            if disease_id:
                self._add_entity_node(
                    node_id=self._disease_node_id(disease_id),
                    entity_type=GraphEntityType.DISEASE,
                    display_name=disease_id,
                    external_id=chain.disease_id,
                )
            if variant_id:
                self._add_entity_node(
                    node_id=self._variant_node_id(variant_id),
                    entity_type=GraphEntityType.VARIANT,
                    display_name=variant_id,
                    external_id=chain.variant_id,
                )

            if gene_id and disease_id:
                self._batch.add_edge(
                    source_id=self._gene_node_id(gene_id),
                    target_id=self._disease_node_id(disease_id),
                    relation_type=GraphRelationType.ASSOCIATED_WITH,
                    properties={"chain_level": chain.chain_level},
                )
            if variant_id and disease_id:
                self._batch.add_edge(
                    source_id=self._variant_node_id(variant_id),
                    target_id=self._disease_node_id(disease_id),
                    relation_type=GraphRelationType.ASSOCIATED_WITH,
                    properties={"chain_level": chain.chain_level},
                )

        return self._batch

    def build_from_special_evidence(
        self,
        source_document_id: str,
        processing_run_id: str,
        records: list[SpecialEvidenceRecord],
    ) -> LiteratureGraphBatch:
        """Build contradiction/authority edges from special evidence records."""
        self._batch = LiteratureGraphBatch()

        for idx, record in enumerate(records):
            node_id = f"evidence:{source_document_id}:{processing_run_id}:special:{idx}"
            self._batch.add_node(
                node_id=node_id,
                entity_type=GraphEntityType.EVIDENCE,
                display_name=record.description[:120],
                properties={
                    "record_type": record.record_type,
                    "group_id": record.group_id,
                    "confidence": record.confidence,
                },
            )
            self._batch.add_edge(
                source_id=node_id,
                target_id=source_document_id,
                relation_type=GraphRelationType.FROM_DOCUMENT,
            )
            self._batch.add_edge(
                source_id=node_id,
                target_id=processing_run_id,
                relation_type=GraphRelationType.FROM_RUN,
            )

        return self._batch

    def _add_entity_node(
        self,
        node_id: str,
        entity_type: GraphEntityType,
        display_name: str,
        external_id: str | None = None,
        raw_text: str | None = None,
    ) -> None:
        props: dict[str, object] = {}
        if external_id:
            props["external_id"] = external_id
        if raw_text:
            props["raw_text"] = raw_text
        self._batch.add_node(
            node_id=node_id,
            entity_type=entity_type,
            display_name=display_name,
            properties=props,
        )

    @staticmethod
    def _map_entity_type(entity_type: EntityType) -> GraphEntityType:
        mapping = {
            EntityType.GENE: GraphEntityType.GENE,
            EntityType.VARIANT: GraphEntityType.VARIANT,
            EntityType.DISEASE: GraphEntityType.DISEASE,
            EntityType.PHENOTYPE: GraphEntityType.PHENOTYPE,
        }
        return mapping.get(entity_type, GraphEntityType.EVIDENCE)

    @staticmethod
    def _entity_node_id(entity_type: EntityType, external_id: str) -> str:
        return f"{entity_type.value}:{external_id}"

    @staticmethod
    def _gene_node_id(gene_symbol: str) -> str:
        return f"gene:{gene_symbol.upper()}"

    @staticmethod
    def _disease_node_id(disease_name: str) -> str:
        return f"disease:{disease_name.casefold()}"

    @staticmethod
    def _variant_node_id(variant_hgvs: str) -> str:
        return f"variant:{variant_hgvs.strip()}"

    @staticmethod
    def _evidence_node_id(document_id: str, processing_run_id: str, item: Any) -> str:
        position_hash = getattr(item, "position_hash", "")
        text_hash = getattr(item, "text_hash", "")
        return f"evidence:{document_id}:{processing_run_id}:{item.field_id}:{position_hash}:{text_hash}"

    @staticmethod
    def _preview_value(value: Any, max_length: int = 80) -> str:
        if value is None:
            return ""
        text = str(value)
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text
