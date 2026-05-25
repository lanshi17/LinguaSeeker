"""Adapters that translate Phase 2 evidence output into Phase 3 input."""
from __future__ import annotations

from typing import Any

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
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
        seen: set[tuple[EntityType, str, str]] = set()

        for track_result in (result.original_result, result.translated_result):
            self._add_chain_candidates(track_result, candidates, seen)
            self._add_phenotype_candidates(track_result, candidates, seen)

        return StandardizationInput(
            document_id=result.document_id,
            source_document_id=source_document_id,
            processing_run_id=processing_run_id,
            candidates=tuple(candidates),
            evidence_items=tuple([*result.original_result.evidence_items, *result.translated_result.evidence_items]),
            track_payloads={
                "original": result.original_result.model_dump(mode="json"),
                "translated": result.translated_result.model_dump(mode="json"),
            },
        )

    def _add_chain_candidates(
        self,
        result: EvidenceExtractionResult,
        candidates: list[StandardizationCandidate],
        seen: set[tuple[EntityType, str, str]],
    ) -> None:
        """Extract gene, disease, and variant candidates from evidence chains."""
        for chain in result.evidence_chains:
            self._append_candidate(
                candidates,
                seen,
                entity_type=EntityType.GENE,
                raw_text=chain.gene_text,
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
            )

    def _add_phenotype_candidates(
        self,
        result: EvidenceExtractionResult,
        candidates: list[StandardizationCandidate],
        seen: set[tuple[EntityType, str, str]],
    ) -> None:
        """Extract phenotype candidates from supported phenotype evidence fields."""
        for item in result.evidence_items:
            if item.status != EvidenceStatus.FOUND or item.field_id not in PHENOTYPE_FIELD_IDS:
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
            ),
        )

    def _extract_field_values(self, item: EvidenceItem) -> list[str]:
        """Flatten supported evidence item value shapes into text candidates."""
        value: Any = item.value
        if isinstance(value, list):
            return [str(entry).strip() for entry in value if str(entry).strip()]
        if value is None:
            return []
        text = str(value).strip()
        return [text] if text else []
