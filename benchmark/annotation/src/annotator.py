"""LLM-driven annotation generation for Rett syndrome articles."""
from __future__ import annotations

import json
import re
from pathlib import Path

from loguru import logger

from .config import Config
from .models import ArticleVariant, ExpectedEvidenceField, RettExpectedJson
from .utils import RETT_HPO_TERMS, classify_variant_type, infer_domain, normalize_hgvs

_SYSTEM_PROMPT = """\
You are a medical genetics expert extracting structured evidence from a \
Rett syndrome case report article. The gene of interest is MECP2 (HGNC:6992), \
associated with Rett syndrome (MONDO:0010726, X-linked dominant).

Extract the following information from the article text:

1. **Gene**: Usually MECP2. Some articles discuss CDKL5 or FOXG1 for atypical Rett.
2. **Disease diagnosis**: "Rett syndrome", "atypical Rett syndrome", or specific subtype.
3. **Gene-disease relationship**: "causative" (most common), "associated", or "susceptibility".
4. **Mode of inheritance**: "XD" (X-linked dominant) for MECP2. May be stated differently.
5. **Variants**: HGVS coding (c.) and protein (p.) notation, variant type, exon, protein domain.
   - Only extract variants explicitly stated in the article text.
   - Common MECP2 mutations: p.R255X, p.R270X, p.R306C, p.T158M, p.R168X, p.R133C.
6. **HPO terms** (REQUIRED when clinical features are described): Map every clinical \
feature mentioned in the article to its HPO code using the table below. \
Include ALL applicable HPO terms. This field must NOT be empty if any clinical \
features are reported.

   Common Rett HPO mappings:
   - Seizures / epilepsy → HP:0001250
   - Global developmental delay → HP:0001263
   - Intellectual disability → HP:0001249
   - Hand stereotypies / hand-wringing → HP:0002072
   - Developmental regression → HP:0002376
   - Microcephaly → HP:0000252
   - Progressive microcephaly → HP:0000253
   - Hypotonia → HP:0001252
   - Generalized hypotonia → HP:0001290
   - Spasticity → HP:0001257
   - Ataxia / gait ataxia → HP:0001251
   - Breathing abnormalities / hyperventilation / apnea → HP:0012759
   - Autistic behavior → HP:0000756
   - Scoliosis → HP:0002650
   - Short stature / growth failure → HP:0004322
   - Strabismus → HP:0000568
   - Sleep disturbance → HP:0002360
   - Bruxism → HP:0003763
   - Feeding difficulties → HP:0011968
   - Constipation → HP:0002019
   - Cold extremities → HP:0012171
   - Delayed motor development → HP:0002194
   - Absent speech → HP:0001344
   - Flexion contracture → HP:0001371
   - Visual impairment → HP:0000505
   - Hearing impairment → HP:0000365
   - Atrial septal defect → HP:0001631

7. **Clinical phenotypes**: Natural language descriptions of the clinical features \
(separate from HPO codes).
8. **Patient demographics**: Sex, age of onset.
9. **De novo status**: Whether the variant is de novo, inherited, or unknown.
10. **Functional domain**: MBD (aa 78-162), TRD (aa 201-310), or other MECP2 domain.

Respond with a valid JSON object matching the schema below. If information is not \
found, use empty strings or null. Do NOT fabricate data not present in the article.

JSON schema:
{
  "gene_symbol": "string",
  "disease_diagnosis": "string",
  "gene_disease_relationship": "string",
  "mode_of_inheritance": "string",
  "variants": [
    {
      "hgvs_c": "string",
      "hgvs_p": "string",
      "variant_type": "string",
      "clinical_significance": "string",
      "exon": "string",
      "domain": "string"
    }
  ],
  "hpo_terms": ["HP:0001250", "HP:0001263", ...],
  "clinical_phenotypes": ["seizures", "developmental delay", ...],
  "sex": "string",
  "age_of_onset": "string",
  "de_novo_status": "string",
  "functional_domain": "string",
  "source_pmid": "string or null",
  "source_doi": "string or null",
  "source_title": "string or null",
  "source_year": "string or null",
  "source_journal": "string or null"
}
"""


def _build_expected_evidence(parsed: dict) -> list[ExpectedEvidenceField]:
    """Convert LLM output into catalog-compatible expected_evidence fields."""
    fields: list[ExpectedEvidenceField] = []

    if parsed.get("gene_symbol"):
        fields.append(ExpectedEvidenceField(
            field_id="A.gene_symbol",
            value=parsed["gene_symbol"],
            source="article",
            evaluation_type="precision_recall",
        ))

    if parsed.get("disease_diagnosis"):
        fields.append(ExpectedEvidenceField(
            field_id="B.disease_diagnosis",
            value=parsed["disease_diagnosis"],
            source="article",
            evaluation_type="precision_recall",
        ))

    if parsed.get("gene_disease_relationship"):
        fields.append(ExpectedEvidenceField(
            field_id="A.gene_disease_relationship",
            value=parsed["gene_disease_relationship"],
            source="article",
            evaluation_type="precision_recall",
        ))

    if parsed.get("mode_of_inheritance"):
        fields.append(ExpectedEvidenceField(
            field_id="B.mode_of_inheritance_reported",
            value=parsed["mode_of_inheritance"],
            source="article",
            evaluation_type="precision_recall",
        ))

    variants = parsed.get("variants", [])
    if variants:
        hgvs_c_values = [v.get("hgvs_c", "") for v in variants if v.get("hgvs_c")]
        hgvs_p_values = [v.get("hgvs_p", "") for v in variants if v.get("hgvs_p")]
        vtype_values = [v.get("variant_type", "") for v in variants if v.get("variant_type")]
        domain_values = [v.get("domain", "") for v in variants if v.get("domain")]

        if hgvs_c_values:
            fields.append(ExpectedEvidenceField(
                field_id="A.variant_hgvs_c",
                value=hgvs_c_values[0],
                candidates=hgvs_c_values if len(hgvs_c_values) > 1 else [],
                source="article",
                evaluation_type="precision_only",
            ))

        if hgvs_p_values:
            fields.append(ExpectedEvidenceField(
                field_id="A.variant_hgvs_p",
                value=hgvs_p_values[0],
                candidates=hgvs_p_values if len(hgvs_p_values) > 1 else [],
                source="article",
                evaluation_type="precision_only",
            ))

        if vtype_values:
            fields.append(ExpectedEvidenceField(
                field_id="A.variant_type",
                value=vtype_values[0],
                candidates=vtype_values if len(vtype_values) > 1 else [],
                source="article",
                evaluation_type="precision_only",
            ))

        if domain_values:
            fields.append(ExpectedEvidenceField(
                field_id="A.functional_domain_or_hotspot",
                value=domain_values[0],
                candidates=domain_values if len(domain_values) > 1 else [],
                source="article",
                evaluation_type="precision_only",
            ))

    hpo_terms = parsed.get("hpo_terms", [])
    if hpo_terms:
        fields.append(ExpectedEvidenceField(
            field_id="B.hpo_terms",
            value="; ".join(hpo_terms),
            source="article",
            evaluation_type="precision_recall",
        ))

    phenotypes = parsed.get("clinical_phenotypes", [])
    if phenotypes:
        fields.append(ExpectedEvidenceField(
            field_id="B.clinical_phenotypes",
            value="; ".join(phenotypes),
            source="article",
            evaluation_type="precision_recall",
        ))

    if parsed.get("sex"):
        fields.append(ExpectedEvidenceField(
            field_id="B.sex",
            value=parsed["sex"],
            source="article",
            evaluation_type="precision_recall",
        ))

    if parsed.get("age_of_onset"):
        fields.append(ExpectedEvidenceField(
            field_id="B.age_of_onset",
            value=parsed["age_of_onset"],
            source="article",
            evaluation_type="precision_recall",
        ))

    if parsed.get("de_novo_status"):
        fields.append(ExpectedEvidenceField(
            field_id="C.de_novo_status",
            value=parsed["de_novo_status"],
            source="article",
            evaluation_type="precision_recall",
        ))

    return fields


def _split_into_sections(text: str, chunk_size: int = 12000) -> list[str]:
    """Split markdown text into sections by headings, merging small sections."""
    sections = re.split(r"(?=^#{1,3}\s)", text, flags=re.MULTILINE)
    chunks: list[str] = []
    current = ""
    for section in sections:
        if len(current) + len(section) > chunk_size and current:
            chunks.append(current)
            current = section
        else:
            current += section
    if current:
        chunks.append(current)
    return chunks


async def annotate_article(
    source_md: str,
    entry_id: str,
    language: str,
    config: Config,
) -> RettExpectedJson:
    """Generate annotation for a single article using LLM."""
    from langchain_core.messages import HumanMessage, SystemMessage

    client = config.build_llm_client()
    fallback = config.build_fallback_client()

    chunks = _split_into_sections(source_md, config.annotation.chunk_size)
    combined_text = source_md if len(source_md) <= config.annotation.chunk_size * 2 else "\n\n---\n\n".join(chunks[:3])

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f"Article language: {language}\n\nArticle text:\n\n{combined_text}"),
    ]

    parsed: dict | None = None
    for llm in [client, fallback]:
        if llm is None:
            continue
        try:
            response = await llm.ainvoke(messages)
            content = response.content
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                parsed = json.loads(json_match.group())
                break
        except Exception as e:
            logger.warning("LLM call failed with {}: {}", type(llm).__name__, e)

    if parsed is None:
        logger.error("All LLM providers failed for {}", entry_id)
        return RettExpectedJson(entry_id=entry_id, source_language=language)

    expected_evidence = _build_expected_evidence(parsed)

    variants = [
        ArticleVariant(
            hgvs_c=normalize_hgvs(v.get("hgvs_c", "")),
            hgvs_p=normalize_hgvs(v.get("hgvs_p", "")),
            variant_type=v.get("variant_type", "") or classify_variant_type(v.get("hgvs_c", ""), v.get("hgvs_p", "")),
            clinical_significance=v.get("clinical_significance", ""),
            exon=v.get("exon", ""),
            domain=v.get("domain", "") or infer_domain(v.get("hgvs_p", "")),
        )
        for v in parsed.get("variants", [])
    ]

    return RettExpectedJson(
        entry_id=entry_id,
        gene_symbol=parsed.get("gene_symbol", "MECP2"),
        disease_label=parsed.get("disease_diagnosis", "Rett syndrome"),
        moi=parsed.get("mode_of_inheritance", "XD"),
        source_pmid=parsed.get("source_pmid"),
        source_doi=parsed.get("source_doi"),
        source_title=parsed.get("source_title"),
        source_journal=parsed.get("source_journal"),
        source_year=parsed.get("source_year"),
        source_language=language,
        variants=variants,
        expected_evidence=expected_evidence,
    )
