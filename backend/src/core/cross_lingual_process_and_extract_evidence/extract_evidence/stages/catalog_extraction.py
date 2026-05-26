"""Catalog extraction stage — structured field extraction using the 10-category catalog."""
from __future__ import annotations

from ..catalog import EVIDENCE_FIELD_SPECS
from ..chunking import (
    DEFAULT_INPUT_BUDGET_TOKENS,
    build_block_prompt_chunks,
    merge_sparse_evidence_items,
)
from ..contracts import DocumentEvidenceMap, EvidenceItem, TrackDocument
from ..core import RawSourceNormalizer
from ..prompts import get_catalog_extraction_prompt
from ..providers import EvidenceModelTier, LangChainEvidenceProvider
from ...cross_lingual.format.segmenter import estimate_tokens


class CatalogExtractionStage:
    def __init__(
        self,
        provider: LangChainEvidenceProvider,
        input_budget_tokens: int = DEFAULT_INPUT_BUDGET_TOKENS,
    ):
        self._provider = provider
        self._input_budget_tokens = input_budget_tokens
        self._raw_source_normalizer = RawSourceNormalizer()

    def run(
        self,
        document: TrackDocument,
        evidence_map: DocumentEvidenceMap,
    ) -> list[EvidenceItem]:
        summary = self._summarize_map(evidence_map)
        overhead = estimate_tokens(get_catalog_extraction_prompt(
            document_id=document.document_id,
            track=document.track,
            text="",
            catalog=EVIDENCE_FIELD_SPECS,
            evidence_map_summary=summary,
        ))
        chunks = build_block_prompt_chunks(
            document,
            input_budget_tokens=self._input_budget_tokens,
            prompt_overhead_tokens=overhead,
        )
        extracted: list[EvidenceItem] = []
        for chunk in chunks:
            chunk_summary = summary
            if chunk.total > 1:
                chunk_summary = f"{summary}\nCurrent document chunk: {chunk.index}/{chunk.total}"
            prompt = get_catalog_extraction_prompt(
                document_id=document.document_id,
                track=document.track,
                text=chunk.text,
                catalog=EVIDENCE_FIELD_SPECS,
                evidence_map_summary=chunk_summary,
            )
            items = self._provider.invoke_structured(
                prompt=prompt,
                output_schema=list[EvidenceItem],
                tier=EvidenceModelTier.STRONG,
                stage="catalog_extraction" if chunk.total == 1 else f"catalog_extraction/{chunk.index}",
            )
            if isinstance(items, list):
                extracted.extend(self._raw_source_normalizer.normalize_items(items))
        return merge_sparse_evidence_items(extracted)

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
