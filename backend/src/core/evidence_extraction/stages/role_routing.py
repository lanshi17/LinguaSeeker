"""Role routing stage — separates primary evidence from phenotype/comparator/context."""

from __future__ import annotations

from loguru import logger

from ..contracts import EvidenceItem, EvidenceRole, ExtractionTarget


class EvidenceRoleRouter:
    """Routes extracted items by evidence role before normalization."""

    def route(
        self,
        items: list[EvidenceItem],
        extraction_target: ExtractionTarget | None = None,
    ) -> tuple[list[EvidenceItem], list[EvidenceItem], list[EvidenceItem]]:
        primary: list[EvidenceItem] = []
        phenotype: list[EvidenceItem] = []
        discarded: list[EvidenceItem] = []
        for item in items:
            if item.evidence_role == EvidenceRole.PRIMARY:
                primary.append(item)
            elif item.evidence_role == EvidenceRole.PHENOTYPE:
                phenotype.append(item)
            elif self._is_target_identity(item, extraction_target):
                primary.append(item.model_copy(update={"evidence_role": EvidenceRole.PRIMARY}))
            else:
                logger.info(
                    "Discarding non-primary evidence item: field_id={}, role={}, value={}",
                    item.field_id,
                    item.evidence_role.value,
                    item.value,
                )
                discarded.append(item)
        return primary, phenotype, discarded

    @staticmethod
    def _is_target_identity(
        item: EvidenceItem,
        extraction_target: ExtractionTarget | None,
    ) -> bool:
        if extraction_target is None or item.evidence_role != EvidenceRole.CONTEXT:
            return False
        value = str(item.value or "").strip()
        if not value:
            return False
        if item.field_id == "A.gene_symbol":
            return value.upper() == extraction_target.gene_symbol
        if item.field_id == "B.disease_diagnosis":
            disease = extraction_target.disease_name.casefold()
            candidate = value.casefold()
            return bool(candidate and (candidate in disease or disease in candidate))
        return False
