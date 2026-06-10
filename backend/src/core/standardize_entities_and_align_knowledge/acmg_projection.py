"""Project standardized entities into ACMG-ready evidence facts."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
)
from src.core.standardize_entities_and_align_knowledge.contracts import (
    AcmgReadyEvidenceItem,
    AcmgReadyEvidenceSet,
    EntityMatch,
    EntityType,
    MatchStatus,
    StandardizationInput,
)


class AcmgReadyProjector:
    """Build compact key-value evidence for downstream rules-based ACMG consumers."""

    _PROBAND_PHENOTYPE_FIELDS = frozenset({"B.hpo_terms", "B.clinical_phenotypes"})

    def project(
        self,
        input_data: StandardizationInput,
        matches: tuple[EntityMatch, ...],
    ) -> AcmgReadyEvidenceSet:
        items: list[AcmgReadyEvidenceItem] = []
        hpo_ids = self._hpo_ids(matches)
        phenotype_raw_values = self._raw_values(
            input_data.evidence_items, {"B.hpo_terms", "B.clinical_phenotypes"},
        )
        if hpo_ids:
            items.append(
                AcmgReadyEvidenceItem(
                    field_id="B.clinical_phenotypes",
                    normalized_key="hpo_terms",
                    normalized_value=hpo_ids,
                    raw_values=phenotype_raw_values,
                    source_field_ids=("B.hpo_terms", "B.clinical_phenotypes"),
                    confidence=self._max_confidence(
                        input_data.evidence_items, {"B.hpo_terms", "B.clinical_phenotypes"},
                    ),
                ),
            )
        return AcmgReadyEvidenceSet(document_id=input_data.document_id, items=tuple(items))

    def _hpo_ids(self, matches: tuple[EntityMatch, ...]) -> list[str]:
        ids: list[str] = []
        for match in matches:
            if (
                match.candidate.entity_type == EntityType.PHENOTYPE
                and match.candidate.field_id in self._PROBAND_PHENOTYPE_FIELDS
                and match.status == MatchStatus.STANDARDIZED
                and match.external_id
                and match.external_id.startswith("HP:")
                and match.external_id not in ids
            ):
                ids.append(match.external_id)
        return ids

    def _raw_values(
        self, evidence_items: tuple[object, ...], field_ids: set[str],
    ) -> tuple[str, ...]:
        values: list[str] = []
        for item in evidence_items:
            if (
                not isinstance(item, EvidenceItem)
                or item.status != EvidenceStatus.FOUND
                or item.field_id not in field_ids
            ):
                continue
            if isinstance(item.value, list):
                values.extend(str(v) for v in item.value)
            elif item.value is not None:
                values.append(str(item.value))
        return tuple(values)

    def _max_confidence(
        self, evidence_items: tuple[object, ...], field_ids: set[str],
    ) -> float:
        confidences = [
            item.confidence
            for item in evidence_items
            if isinstance(item, EvidenceItem)
            and item.status == EvidenceStatus.FOUND
            and item.field_id in field_ids
        ]
        return max(confidences, default=0.0)
