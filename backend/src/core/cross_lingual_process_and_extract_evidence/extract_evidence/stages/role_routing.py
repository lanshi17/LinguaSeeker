"""Role routing stage — separates primary evidence from phenotype/comparator/context."""
from __future__ import annotations

from loguru import logger

from ..contracts import EvidenceItem, EvidenceRole


class EvidenceRoleRouter:
    """Routes extracted items by evidence role before normalization."""

    def route(
        self,
        items: list[EvidenceItem],
    ) -> tuple[list[EvidenceItem], list[EvidenceItem], list[EvidenceItem]]:
        primary: list[EvidenceItem] = []
        phenotype: list[EvidenceItem] = []
        discarded: list[EvidenceItem] = []
        for item in items:
            if item.evidence_role == EvidenceRole.PRIMARY:
                primary.append(item)
            elif item.evidence_role == EvidenceRole.PHENOTYPE:
                phenotype.append(item)
            else:
                logger.info(
                    "Discarding non-primary evidence item: field_id={}, role={}, value={}",
                    item.field_id,
                    item.evidence_role.value,
                    item.value,
                )
                discarded.append(item)
        return primary, phenotype, discarded
