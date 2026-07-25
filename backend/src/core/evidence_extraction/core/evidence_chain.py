"""Evidence chain builder for variant-centered identity chains."""

from __future__ import annotations

from ..contracts import (
    EvidenceChain,
    EvidenceItem,
    EvidenceStatus,
    SourcePrecision,
    SpecialEvidenceRecord,
)


class EvidenceChainBuilder:
    """Builds variant-centered identity chains from grounded grouped evidence."""

    def build(
        self,
        items: list[EvidenceItem],
        special_records: list[SpecialEvidenceRecord],
    ) -> list[EvidenceChain]:
        grouped_items: dict[str, list[EvidenceItem]] = {}
        for item in items:
            if not self._is_valid_grounded(item):
                continue
            group_id = item.group_id
            if not group_id:
                continue
            grouped_items.setdefault(group_id, []).append(item)

        chains: list[EvidenceChain] = []
        for group_id, group_items in grouped_items.items():
            by_field: dict[str, list[EvidenceItem]] = {}
            for item in group_items:
                by_field.setdefault(item.field_id, []).append(item)

            gene = self._first_value(by_field, "A.gene_symbol")
            disease = self._first_value(by_field, "B.disease_diagnosis")
            variant = self._first_value(by_field, "A.variant_hgvs_c") or self._first_value(by_field, "A.variant_hgvs_p")

            core_count = sum(1 for value in (gene, disease, variant) if value is not None)
            if core_count == 0:
                continue
            if core_count == 3:
                chain_level = "full"
            elif core_count == 2:
                chain_level = "partial"
            else:
                chain_level = "singleton"

            case_ids = sorted({str(item.value) for item in by_field.get("B.case_id", []) if item.value is not None})
            special_indices = [index for index, record in enumerate(special_records) if record.group_id == group_id]
            contradictions = [
                record.description
                for record in special_records
                if record.group_id == group_id and record.record_type == "contradiction"
            ]

            chains.append(
                EvidenceChain(
                    chain_id=group_id,
                    chain_level=chain_level,
                    gene_text=str(gene.value) if gene is not None and gene.value is not None else "",
                    disease_text=str(disease.value) if disease is not None and disease.value is not None else "",
                    variant_text=str(variant.value) if variant is not None and variant.value is not None else "",
                    case_ids=case_ids,
                    special_evidence_ids=[f"special-{index}" for index in special_indices],
                    evidence_field_ids=sorted({item.field_id for item in group_items}),
                    contradictions=contradictions,
                )
            )
        return sorted(chains, key=lambda chain: chain.chain_id)

    @staticmethod
    def _is_valid_grounded(item: EvidenceItem) -> bool:
        return (
            item.status == EvidenceStatus.FOUND
            and item.value is not None
            and item.source is not None
            and item.source.source_precision != SourcePrecision.AMBIGUOUS
        )

    @staticmethod
    def _first_value(by_field: dict[str, list[EvidenceItem]], field_id: str) -> EvidenceItem | None:
        values = by_field.get(field_id, [])
        return values[0] if values else None


