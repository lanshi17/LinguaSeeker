"""Adapters that translate Phase 2 evidence output into Phase 3 input."""

from __future__ import annotations

import re
from typing import Any, TypedDict

from src.core.evidence_extraction.contracts import (
    DualEvidenceExtractionResult,
    EvidenceExtractionResult,
    EvidenceItem,
    EvidenceStatus,
)
from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    EntityType,
    StandardizationCandidate,
    StandardizationInput,
)
from src.core.standardize_entities_and_align_knowledge.normalizers import normalize_lookup_text
from src.utils.text import parse_gene_from_group_id


ROLE_BY_ENTITY_TYPE = {
    EntityType.GENE: BindingRole.SUBJECT,
    EntityType.VARIANT: BindingRole.TARGET,
    EntityType.DISEASE: BindingRole.CONTEXT,
    EntityType.PHENOTYPE: BindingRole.CONTEXT,
}

PHENOTYPE_FIELD_IDS = {
    "B.hpo_terms",
    "B.clinical_phenotypes",
    "C.maternal_phenotype",
    "C.paternal_phenotype",
    "I.animal_model_phenotype",
    "I.cell_model_phenotype",
}

_PHENOTYPE_SPLIT_RE = re.compile(r"[、,;；]")


class TrackPayloads(TypedDict, total=False):
    """Phase 3 track payload map with optional audit-only entries."""

    original: Any
    translated: Any
    reconciled: Any
    audit_original: Any
    audit_translated: Any


class DualResultAdapter:
    """Convert dual-track evidence extraction output into typed standardization input."""

    def to_standardization_input(
        self,
        result: DualEvidenceExtractionResult,
        *,
        source_document_id: str,
        processing_run_id: str,
    ) -> StandardizationInput:
        """Project a dual extraction result into Phase 3 candidate input."""
        candidates: list[StandardizationCandidate] = []
        evidence_items: list[EvidenceItem] = []
        seen: set[tuple[EntityType, str, str]] = set()
        primary_results = self._primary_results(result)

        for track_result in primary_results:
            gene_values_by_group = self._gene_values_by_group(track_result)
            gene_linked_group_ids = set(gene_values_by_group)
            self._add_chain_candidates(track_result, candidates, seen, gene_values_by_group)
            self._add_phenotype_candidates(track_result, candidates, seen, gene_linked_group_ids)
            self._add_phenotype_evidence_candidates(track_result, candidates, seen, gene_linked_group_ids)
            evidence_items.extend(
                self._filter_gene_linked_evidence_items(track_result.evidence_items, gene_linked_group_ids)
            )

        extraction_target = (
            primary_results[0].extraction_target
            or result.original_result.extraction_target
            or result.translated_result.extraction_target
        )

        return StandardizationInput(
            document_id=result.document_id,
            source_document_id=source_document_id,
            processing_run_id=processing_run_id,
            candidates=tuple(candidates),
            evidence_items=tuple(evidence_items),
            track_payloads=self._track_payloads(result),
            extraction_target=extraction_target,
        )

    def _primary_results(self, result: DualEvidenceExtractionResult) -> tuple[EvidenceExtractionResult, ...]:
        """Return the default extraction results consumed by Phase 3."""
        if result.reconciled_result is not None:
            return (result.reconciled_result,)
        return (result.original_result, result.translated_result)

    def _track_payloads(self, result: DualEvidenceExtractionResult) -> TrackPayloads:
        """Build persistence payloads while retaining original tracks for audit."""
        if result.reconciled_result is not None:
            return {
                "reconciled": result.reconciled_result.model_dump(mode="json"),
                "audit_original": {
                    "audit_only": True,
                    **result.original_result.model_dump(mode="json"),
                },
                "audit_translated": {
                    "audit_only": True,
                    **result.translated_result.model_dump(mode="json"),
                },
            }
        return {
            "original": result.original_result.model_dump(mode="json"),
            "translated": result.translated_result.model_dump(mode="json"),
        }

    def _add_chain_candidates(
        self,
        result: EvidenceExtractionResult,
        candidates: list[StandardizationCandidate],
        seen: set[tuple[EntityType, str, str]],
        gene_values_by_group: dict[str, str],
    ) -> None:
        """Extract gene, disease, and variant candidates from evidence chains."""
        for chain in result.evidence_chains:
            gene_text = gene_values_by_group.get(chain.chain_id, chain.gene_text).strip()
            if not gene_text:
                continue
            self._append_candidate(
                candidates,
                seen,
                entity_type=EntityType.GENE,
                raw_text=gene_text,
                chain_id=chain.chain_id,
                track=result.track.value,
            )
            self._append_candidate(
                candidates,
                seen,
                entity_type=EntityType.DISEASE,
                raw_text=chain.disease_text,
                chain_id=chain.chain_id,
                track=result.track.value,
            )
            self._append_candidate(
                candidates,
                seen,
                entity_type=EntityType.VARIANT,
                raw_text=chain.variant_text,
                chain_id=chain.chain_id,
                track=result.track.value,
                metadata={"gene_symbol": gene_text},
            )

    def _add_phenotype_candidates(
        self,
        result: EvidenceExtractionResult,
        candidates: list[StandardizationCandidate],
        seen: set[tuple[EntityType, str, str]],
        gene_linked_group_ids: set[str],
    ) -> None:
        """Extract phenotype candidates from supported phenotype evidence fields."""
        for item in result.evidence_items:
            if (
                item.status != EvidenceStatus.FOUND
                or item.field_id not in PHENOTYPE_FIELD_IDS
                or not self._is_gene_linked_item(item, gene_linked_group_ids)
            ):
                continue
            for raw_text in self._extract_field_values(item):
                self._append_candidate(
                    candidates,
                    seen,
                    entity_type=EntityType.PHENOTYPE,
                    raw_text=raw_text,
                    chain_id=item.group_id or item.field_id,
                    track=result.track.value,
                    field_id=item.field_id,
                )

    def _add_phenotype_evidence_candidates(
        self,
        result: EvidenceExtractionResult,
        candidates: list[StandardizationCandidate],
        seen: set[tuple[EntityType, str, str]],
        gene_linked_group_ids: set[str],
    ) -> None:
        """Extract phenotype candidates from explicit phenotype_evidence items."""
        for item in result.phenotype_evidence:
            if item.status != EvidenceStatus.FOUND or not self._is_gene_linked_item(item, gene_linked_group_ids):
                continue
            for raw_text in self._extract_field_values(item):
                self._append_candidate(
                    candidates,
                    seen,
                    entity_type=EntityType.PHENOTYPE,
                    raw_text=raw_text,
                    chain_id=item.group_id or item.field_id,
                    track=result.track.value,
                    field_id=item.field_id,
                )

    def _append_candidate(
        self,
        candidates: list[StandardizationCandidate],
        seen: set[tuple[EntityType, str, str]],
        *,
        entity_type: EntityType,
        raw_text: str,
        chain_id: str,
        track: str,
        field_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Append one deduplicated candidate when the text is non-empty."""
        text = raw_text.strip()
        if not text:
            return
        key = (entity_type, normalize_lookup_text(text), chain_id)
        if key in seen:
            return
        seen.add(key)
        candidates.append(
            StandardizationCandidate(
                candidate_id=f"{chain_id}:{entity_type.value}:{len(candidates)}",
                entity_type=entity_type,
                role=ROLE_BY_ENTITY_TYPE[entity_type],
                raw_text=text,
                chain_id=chain_id,
                track=track,
                field_id=field_id,
                metadata=dict(metadata or {}),
            ),
        )

    def _gene_values_by_group(self, result: EvidenceExtractionResult) -> dict[str, str]:
        """Collect one non-empty gene value for each group visible to Phase 3."""
        values_by_group: dict[str, str] = {}
        for chain in result.evidence_chains:
            gene_text = chain.gene_text.strip()
            if gene_text and chain.chain_id:
                values_by_group[chain.chain_id] = gene_text
        for item in result.evidence_items:
            if item.status != EvidenceStatus.FOUND or item.field_id != "A.gene_symbol" or not item.group_id:
                continue
            gene_values = self._extract_field_values(item)
            if gene_values and item.group_id not in values_by_group:
                values_by_group[item.group_id] = gene_values[0]
        for item in [*result.evidence_items, *result.phenotype_evidence]:
            if not item.group_id or item.group_id in values_by_group:
                continue
            gene_text = parse_gene_from_group_id(item.group_id)
            if gene_text:
                values_by_group[item.group_id] = gene_text
        return values_by_group

    def _filter_gene_linked_evidence_items(
        self,
        items: list[EvidenceItem],
        gene_linked_group_ids: set[str],
    ) -> list[EvidenceItem]:
        """Keep ungrouped items and grouped items that belong to a non-empty gene chain."""
        return [item for item in items if self._is_gene_linked_item(item, gene_linked_group_ids)]

    def _is_gene_linked_item(
        self,
        item: EvidenceItem,
        gene_linked_group_ids: set[str],
    ) -> bool:
        """Return whether an evidence item belongs to a gene-linked group."""
        return not item.group_id or item.group_id in gene_linked_group_ids

    def _extract_field_values(self, item: EvidenceItem) -> list[str]:
        """Flatten supported evidence item value shapes into text candidates."""
        value: Any = item.value
        if isinstance(value, list):
            return [str(entry).strip() for entry in value if str(entry).strip()]
        if value is None:
            return []
        text = str(value).strip()
        if not text:
            return []
        if item.field_id in PHENOTYPE_FIELD_IDS and _PHENOTYPE_SPLIT_RE.search(text):
            return [part.strip() for part in _PHENOTYPE_SPLIT_RE.split(text) if part.strip()]
        return [text]
