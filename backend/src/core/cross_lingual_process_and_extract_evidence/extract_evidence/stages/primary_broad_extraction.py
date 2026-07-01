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

# Benchmark-legacy fallback: maps simplified benchmark field IDs to business
# catalog field_ids.  The B8 prompt now uses canonical business field names
# directly, so these aliases are rarely triggered.  Kept as a compatibility
# layer in case the LLM hallucinates benchmark-style field IDs.
_FIELD_ALIAS_MAP: dict[str, str] = {
    # Benchmark "C.segregation" → business segregation evidence count
    "C.segregation": "C.g_plus_p_plus_count",
    # Benchmark "C.functional_assay" → business functional result
    "C.functional_assay": "F.functional_result",
    # Benchmark "C.contradictory_evidence" → business contradiction type
    "C.contradictory_evidence": "H.contradiction_type",
    # Benchmark "C.recurrence" → business independent case count
    "C.recurrence": "B.case_count",
}

_PRIMARY_FIELD_LIST = (
    "Simple factual fields:\n"
    "- A.gene_symbol: the target gene symbol if supported\n"
    "- B.disease_diagnosis: the target disease or phenotype if supported\n"
    "- A.gene_disease_relationship: classify the gene-disease relationship based on the evidence in this document.\n"
    "  Use one of: causative, disputed, refuted, uncertain, or not_found.\n"
    "  Infer from context: if the article states the gene is 'associated with', 'implicated in', 'linked to',\n"
    "  or 'a known cause of' the disease, use 'causative' or 'associated'. If the article reports a variant\n"
    "  in a patient with the disease and no contradicting evidence, default to 'causative'.\n"
    "- A.variant_hgvs_c: the HGVS coding-level variant notation (e.g. c.473C>T)\n"
    "- A.variant_hgvs_p: the HGVS protein-level variant notation (e.g. p.T158M)\n"
    "- A.variant_type: use the benchmark/ClinVar consequence-class label when available.\n"
    "  Allowed examples: missense, nonsense, frameshift, splice-site, deletion, insertion, duplication, tRNA, CNV.\n"
    "  Do NOT use SNV/substitution as A.variant_type. For a point mutation, infer missense/nonsense/splice-site\n"
    "  from protein notation or explicit text when possible; if the consequence is unknown, leave not_found.\n"
    "- A.variant_consequence_class: optional duplicate consequence class (e.g. missense, nonsense, frameshift,\n"
    "  splice-site, tRNA). If you extract this, also put the same consequence value in A.variant_type.\n"
    "- A.functional_domain_or_hotspot: protein domain, functional region, mutational hotspot, or residue/domain\n"
    "  context for the target gene/variant (e.g. MBD, TRD, kinase domain, DNA-binding domain).\n"
    "  Treat this as a document-level scan field: check title, abstract, figure captions, tables, and discussion.\n"
    "Contextual fields:\n"
    "- B.sex: patient sex (male, female, mixed, unknown)\n"
    "- B.age_of_onset: age of onset as reported (e.g. '2 years', 'infancy', 'adult-onset')\n"
    "- B.mode_of_inheritance_reported: inheritance pattern.\n"
    "  Use standard terms: autosomal dominant (AD), autosomal recessive (AR), X-linked (XL),\n"
    "  mitochondrial (MT), maternal, de novo, multifactorial.\n"
    "  If the text says 'maternally inherited' or 'maternal inheritance', use 'MT'.\n"
    "  Scan family history, pedigree notes, inheritance section text, title/abstract disease labels, and case\n"
    "  descriptions. If the quote explicitly supports a standard inheritance phrase but the target anchor is weak,\n"
    "  return a low-confidence found candidate instead of leaving the field blank.\n"
    "- C.inheritance_source: where the inheritance info came from (e.g. explicit in text, ClinGen, OMIM)\n"
    "- B.clinical_phenotypes: clinical features or phenotypes specifically observed in the target case/patient(s)\n"
    "  with the target gene variant. Extract individual phenotypes as a semicolon-separated list.\n"
    "  Only include phenotypes directly attributed to the patient(s) in this article, NOT background disease descriptions.\n"
    "  Example: 'tremor; rigidity; bradykinesia; postural instability'\n"
    "- B.hpo_terms: HPO IDs or HPO-like phenotype terms observed in the target patient(s) or cohort.\n"
    "  Prefer explicit HP: identifiers when present; otherwise extract the natural-language phenotypes that should\n"
    "  map to HPO terms (e.g. seizures, developmental delay, tremor) as a semicolon-separated list.\n"
    "  Treat this as a document-level phenotype scan field; do not require the article to use the word HPO.\n"
    "Evidence strength fields:\n"
    "- C.de_novo_status: whether the variant was confirmed de novo\n"
    "- C.g_plus_p_plus_count: segregation evidence (e.g. '3/4 affected family members carry the variant')\n"
    "- F.assay_type: functional assay type (e.g. 'enzyme activity assay', 'protein expression')\n"
    "- B.case_count: number of independent cases or families with the variant\n"
    "- H.contradiction_type: contradictory evidence type (e.g. 'MAF too high', 'non-replicated')\n"
    "- J.clinvar_assertion: ClinVar assertion or clinical significance classification.\n"
    "  Extract ONLY when the article explicitly mentions ClinVar, expert panel, ACMG classification,\n"
    "  clinical significance, or variant interpretation (e.g. 'Pathogenic', 'Likely pathogenic', 'VUS', 'Benign').\n"
    "  Look for keywords: 'ClinVar', 'classified as', 'clinical significance', 'expert panel',\n"
    "  'pathogenic', 'likely pathogenic', 'variant of uncertain significance', 'VUS', 'ACMG'.\n"
    "  If the quote explicitly reports a classification but the variant anchor is ambiguous, keep a low-confidence\n"
    "  found candidate for downstream review; do not invent classifications that are only inferred.\n"
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
        return _normalize_candidates(response.evidence_items, document.formatted_text)

    async def run_async(self, document: TrackDocument) -> list[EvidenceItem]:
        response = await self._provider.ainvoke_structured(
            prompt=_build_primary_prompt(document),
            output_schema=PrimaryBroadExtractionResponse,
            tier=EvidenceModelTier.STRONG,
            stage="primary_broad_extraction",
        )
        return _normalize_candidates(response.evidence_items, document.formatted_text)


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
        "and source_quote.\n\n"
        "CRITICAL source_quote rules:\n"
        "- source_quote MUST be a verbatim contiguous substring copied EXACTLY from the document text.\n"
        "- Do NOT paraphrase, summarize, rephrase, add punctuation, or trim whitespace.\n"
        "- Copy the text character-for-character including original spacing and line breaks.\n"
        "- If you cannot find a verbatim contiguous substring in the document for this field,\n"
        "  set status to not_found and source_quote to empty string.\n"
        "- A valid test: the source_quote should be locatable with Python's `in` operator on the document text.\n"
        "- Preferably <= 240 characters.\n"
        "- For not_found items, source_quote must be an empty string.\n\n"
        "Return only JSON. Do not add Markdown fences or explanation.\n\n"
        "Document text:\n"
        f"{_truncate_text(document.formatted_text, max_chars=_INPUT_MAX_CHARS)}"
    )


def _resolve_field_alias(field_id: str) -> str:
    """Resolve a benchmark alias to a business catalog field_id.

    Returns the original ``field_id`` if it already exists in the catalog or
    if no alias is defined.  Raises ``KeyError`` only when the id is neither
    a valid catalog field nor a known alias.
    """
    from ..catalog import _FIELD_BY_ID  # noqa: F811

    if field_id in _FIELD_BY_ID:
        return field_id
    mapped = _FIELD_ALIAS_MAP.get(field_id)
    if mapped is not None:
        logger.info("primary_broad_extraction: alias {} -> {}", field_id, mapped)
        return mapped
    return field_id  # will fail get_field_spec below


def _normalize_candidates(
    candidates: list[PrimaryBroadEvidenceCandidate],
    document_text: str = "",
) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for candidate in candidates:
        resolved_id = _resolve_field_alias(candidate.field_id)
        try:
            spec = get_field_spec(resolved_id)
        except KeyError:
            logger.warning("primary_broad_extraction ignored unknown field_id={}", candidate.field_id)
            continue
        source_quote = candidate.source_quote.strip()
        raw_source = None
        if candidate.status == EvidenceStatus.FOUND and source_quote:
            # Verbatim check: warn if source_quote is not a substring of the document.
            # This catches LLM paraphrasing early; the downstream SourceGroundingStage
            # will still attempt grounding but may fall back to SOURCE_INVALID.
            if document_text and source_quote not in document_text:
                logger.warning(
                    "primary_broad_extraction: field_id={} source_quote is NOT verbatim "
                    "(not found via `in` check). Len={} snippet='{}'",
                    candidate.field_id,
                    len(source_quote),
                    source_quote[:80],
                )
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
    items = _project_consequence_class_to_variant_type(items)
    return FieldValueNormalizer.normalize_items(merge_sparse_evidence_items(items))


_CONSEQUENCE_VARIANT_TYPES = frozenset({
    "missense",
    "nonsense",
    "frameshift",
    "splice-site",
    "splice site",
    "splicing",
    "deletion",
    "insertion",
    "duplication",
    "tRNA",
    "trna",
    "CNV",
    "cnv",
})

_STRUCTURAL_VARIANT_TYPE_VALUES = frozenset({
    "snv",
    "snv/substitution",
    "single nucleotide variant",
    "single nucleotide substitution",
    "substitution",
    "point mutation",
})


def _project_consequence_class_to_variant_type(items: list[EvidenceItem]) -> list[EvidenceItem]:
    """Project consequence-class values into A.variant_type for benchmark scoring."""
    consequence_item = next(
        (
            item
            for item in items
            if item.field_id == "A.variant_consequence_class"
            and item.status == EvidenceStatus.FOUND
            and _normalized_variant_type_value(item.value) in _CONSEQUENCE_VARIANT_TYPES
        ),
        None,
    )
    if consequence_item is None:
        return items

    existing_variant_type = next(
        (
            item
            for item in items
            if item.field_id == "A.variant_type"
            and item.status == EvidenceStatus.FOUND
            and _normalized_variant_type_value(item.value) in _CONSEQUENCE_VARIANT_TYPES
        ),
        None,
    )
    if existing_variant_type is not None:
        return items

    spec = get_field_spec("A.variant_type")
    projected = consequence_item.model_copy(update={
        "field_id": spec.field_id,
        "category": spec.category_id,
        "field_name": spec.field_name,
        "notes": _append_note(
            consequence_item.notes,
            "projected from A.variant_consequence_class for benchmark-compatible variant_type",
        ),
    })
    kept = [
        item
        for item in items
        if not (
            item.field_id == "A.variant_type"
            and _normalized_variant_type_value(item.value) in _STRUCTURAL_VARIANT_TYPE_VALUES
        )
    ]
    kept.append(projected)
    return kept


def _normalized_variant_type_value(value: object) -> str:
    return str(value or "").strip().casefold()


def _append_note(existing: str, addition: str) -> str:
    if not existing:
        return addition
    if addition in existing:
        return existing
    return f"{existing}; {addition}"


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-max_chars // 2 :]
    return f"{head}\n\n[...TRUNCATED...]\n\n{tail}"
