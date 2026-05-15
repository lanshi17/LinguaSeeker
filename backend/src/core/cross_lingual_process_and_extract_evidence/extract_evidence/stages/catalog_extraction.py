"""Catalog extraction stage — structured field extraction using the 10-category catalog."""
from __future__ import annotations

from ..catalog import EVIDENCE_FIELD_SPECS
from ..contracts import DocumentEvidenceMap, EvidenceItem, TrackDocument
from ..prompts import get_catalog_extraction_prompt
from ..providers import EvidenceModelTier, LangChainEvidenceProvider


class CatalogExtractionStage:
    def __init__(self, provider: LangChainEvidenceProvider):
        self._provider = provider

    def run(
        self,
        document: TrackDocument,
        evidence_map: DocumentEvidenceMap,
    ) -> list[EvidenceItem]:
        summary = self._summarize_map(evidence_map)
        prompt = get_catalog_extraction_prompt(
            document_id=document.document_id,
            track=document.track,
            text=document.formatted_text,
            catalog=EVIDENCE_FIELD_SPECS,
            evidence_map_summary=summary,
        )
        items = self._provider.invoke_structured(
            prompt=prompt,
            output_schema=list[EvidenceItem],
            tier=EvidenceModelTier.STRONG,
            stage="catalog_extraction",
        )
        return items if isinstance(items, list) else []

    @staticmethod
    def _summarize_map(emap: DocumentEvidenceMap) -> str:
        parts: list[str] = []
        if emap.disease_terms:
            parts.append(f"Diseases: {', '.join(emap.disease_terms)}")
        if emap.gene_terms:
            parts.append(f"Genes: {', '.join(emap.gene_terms)}")
        if emap.variant_terms:
            parts.append(f"Variants: {', '.join(emap.variant_terms)}")
        if emap.case_references:
            parts.append(f"Cases: {', '.join(emap.case_references)}")
        return "; ".join(parts) if parts else "No specific entities identified"
