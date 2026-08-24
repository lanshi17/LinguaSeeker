"""Project standardized entities into ACMG-ready evidence facts."""

from __future__ import annotations

from src.core.evidence_extraction.contracts import (
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
from src.core.standardize_entities_and_align_knowledge.hgvs_normalizer import expand_hgvs_aliases


class AcmgReadyProjector:
    """Build compact key-value evidence for downstream rules-based ACMG consumers."""

    _PROBAND_PHENOTYPE_FIELDS = frozenset({"B.hpo_terms", "B.clinical_phenotypes"})
    # Closed subset of catalog fields consumed by field-bridge / rules. Do not
    # grant ACMG codes here; only project FOUND extractor values.
    _GATE_FIELDS = (
        "A.variant_hgvs_c",
        "A.variant_hgvs_p",
        "A.variant_type",
        "A.functional_domain_or_hotspot",
        "B.disease_diagnosis",
        "C.de_novo_status",
        "C.maternal_genotype",
        "C.paternal_genotype",
        "C.parentage_confirmed",
    )
    _HGVS_FIELDS = frozenset({"A.variant_hgvs_c", "A.variant_hgvs_p", "A.variant_hgvs_g"})

    def project(
        self,
        input_data: StandardizationInput,
        matches: tuple[EntityMatch, ...],
    ) -> AcmgReadyEvidenceSet:
        items: list[AcmgReadyEvidenceItem] = []
        hpo_ids = self._hpo_ids(matches)
        phenotype_raw_values = self._raw_values(
            input_data.evidence_items,
            {"B.hpo_terms", "B.clinical_phenotypes"},
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
                        input_data.evidence_items,
                        {"B.hpo_terms", "B.clinical_phenotypes"},
                    ),
                ),
            )
        items.extend(self._project_gate_fields(input_data.evidence_items))
        return AcmgReadyEvidenceSet(document_id=input_data.document_id, items=tuple(items))

    def _project_gate_fields(self, evidence_items: tuple[object, ...]) -> list[AcmgReadyEvidenceItem]:
        """Project FOUND field-bridge gates without assigning ACMG codes."""
        projected: list[AcmgReadyEvidenceItem] = []
        for field_id in self._GATE_FIELDS:
            raw_values = self._raw_values(evidence_items, {field_id})
            if not raw_values:
                continue
            projected.append(
                AcmgReadyEvidenceItem(
                    field_id=field_id,
                    normalized_key=field_id.split(".", 1)[-1],
                    normalized_value=self._normalized_gate_value(field_id, raw_values),
                    raw_values=raw_values,
                    source_field_ids=(field_id,),
                    confidence=self._max_confidence(evidence_items, {field_id}),
                ),
            )
        return projected

    def _normalized_gate_value(self, field_id: str, raw_values: tuple[str, ...]) -> str:
        first = raw_values[0]
        if field_id in self._HGVS_FIELDS:
            aliases = expand_hgvs_aliases(first)
            return aliases[0] if aliases else first
        return first

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
        self,
        evidence_items: tuple[object, ...],
        field_ids: set[str],
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
        self,
        evidence_items: tuple[object, ...],
        field_ids: set[str],
    ) -> float:
        confidences = [
            item.confidence
            for item in evidence_items
            if isinstance(item, EvidenceItem) and item.status == EvidenceStatus.FOUND and item.field_id in field_ids
        ]
        return max(confidences, default=0.0)
