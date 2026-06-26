"""B8 primary broad extraction stage."""
from __future__ import annotations

from loguru import logger

from ..catalog import get_field_spec
from ..chunking import merge_sparse_evidence_items
from ..contracts import (
    EvidenceItem,
    EvidenceStatus,
    PrimaryBroadEvidenceCandidate,
    PrimaryBroadExtractionResponse,
    SourceLocation,
    TrackDocument,
)
from ..core import FieldValueNormalizer
from ..providers import EvidenceModelTier, LangChainEvidenceProvider

_INPUT_MAX_CHARS = 50_000

_PRIMARY_FIELD_LIST = (
    "Simple factual fields:\n"
    "- A.gene_symbol: the target gene symbol if supported\n"
    "- B.disease_diagnosis: the target disease or phenotype if supported\n"
    "- A.gene_disease_relationship: one of causative, disputed, refuted, uncertain, or not_found\n"
    "- A.variant_hgvs_c: the HGVS coding-level variant notation (e.g. c.473C>T)\n"
    "- A.variant_hgvs_p: the HGVS protein-level variant notation (e.g. p.T158M)\n"
    "- A.variant_type: the variant type (e.g. SNV, deletion, insertion, CNV, frameshift)\n"
    "- A.variant_consequence_class: the consequence class (e.g. missense, nonsense, frameshift, splice-site)\n"
    "Contextual fields:\n"
    "- B.sex: patient sex (male, female, mixed, unknown)\n"
    "- B.age_of_onset: age of onset as reported (e.g. '2 years', 'infancy', 'adult-onset')\n"
    "- B.mode_of_inheritance_reported: inheritance pattern (e.g. autosomal dominant, autosomal recessive)\n"
    "- C.inheritance_source: where the inheritance info came from (e.g. explicit in text, ClinGen, OMIM)\n"
    "- B.clinical_phenotypes: clinical features or phenotypes mentioned\n"
    "Evidence strength fields:\n"
    "- C.de_novo_status: whether the variant was confirmed de novo\n"
    "- C.segregation: segregation evidence\n"
    "- C.functional_assay: functional assay evidence\n"
    "- C.recurrence: recurrence or independent family evidence\n"
    "- C.contradictory_evidence: contradictory evidence mentioned, or none\n"
    "- J.clinvar_assertion: ClinVar assertion if the article reports it\n"
)


class PrimaryBroadExtractionStage:
    """Run the B8 high-recall primary extraction pass."""

    def __init__(self, provider: LangChainEvidenceProvider):
        self._provider = provider

    def run(self, document: TrackDocument) -> list[EvidenceItem]:
        response = self._provider.invoke_structured(
            prompt=_build_primary_prompt(document),
            output_schema=PrimaryBroadExtractionResponse,
            tier=EvidenceModelTier.STRONG,
            stage="primary_broad_extraction",
        )
        return _normalize_candidates(response.evidence_items)

    async def run_async(self, document: TrackDocument) -> list[EvidenceItem]:
        response = await self._provider.ainvoke_structured(
            prompt=_build_primary_prompt(document),
            output_schema=PrimaryBroadExtractionResponse,
            tier=EvidenceModelTier.STRONG,
            stage="primary_broad_extraction",
        )
        return _normalize_candidates(response.evidence_items)


def _build_primary_prompt(document: TrackDocument) -> str:
    target = document.extraction_target
    target_text = (
        "Target hypothesis:\n- Gene: not provided\n- Disease: not provided\n"
        if target is None
        else (
            "Target hypothesis:\n"
            f"- Gene: {target.gene_symbol}\n"
            f"- Disease: {target.disease_name}\n"
            f"- Variant protein: {target.variant_hgvs_p or 'not specified'}\n"
        )
    )
    return (
        "You are evaluating ACMG/ClinGen evidence extraction for the business pipeline.\n"
        "Use a single high-recall primary extraction pass. Do not validate or reconcile internally; "
        "prefer returning plausible field candidates when the document contains direct support.\n\n"
        f"{target_text}\n"
        "Return a JSON object with an evidence_items array. Include these field IDs when supported:\n"
        f"{_PRIMARY_FIELD_LIST}\n"
        "Each evidence item must have field_id, status (found or not_found), value, confidence, "
        "and source_quote. For found items, source_quote must be a verbatim contiguous excerpt "
        "from the document text, preferably <= 240 characters. For not_found items, source_quote "
        "must be an empty string.\n"
        "Return only JSON. Do not add Markdown fences or explanation.\n\n"
        "Document text:\n"
        f"{_truncate_text(document.formatted_text, max_chars=_INPUT_MAX_CHARS)}"
    )


def _normalize_candidates(candidates: list[PrimaryBroadEvidenceCandidate]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for candidate in candidates:
        try:
            spec = get_field_spec(candidate.field_id)
        except KeyError:
            logger.warning("primary_broad_extraction ignored unknown field_id={}", candidate.field_id)
            continue
        source_quote = candidate.source_quote.strip()
        raw_source = None
        if candidate.status == EvidenceStatus.FOUND and source_quote:
            raw_source = SourceLocation(
                context_type="text",
                context_ref="primary_broad_extraction",
                text_snippet=source_quote,
                block_index=-1,
            )
        items.append(
            EvidenceItem(
                field_id=spec.field_id,
                category=spec.category_id,
                field_name=spec.field_name,
                status=candidate.status,
                value=candidate.value if candidate.status == EvidenceStatus.FOUND else None,
                assigned_acmg_codes=list(spec.acmg_codes) if candidate.status == EvidenceStatus.FOUND else [],
                assigned_clingen_modules=list(spec.clingen_modules) if candidate.status == EvidenceStatus.FOUND else [],
                raw_source=raw_source,
                confidence=candidate.confidence,
                notes=candidate.notes,
            )
        )
    return FieldValueNormalizer.normalize_items(merge_sparse_evidence_items(items))


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-max_chars // 2 :]
    return f"{head}\n\n[...TRUNCATED...]\n\n{tail}"
