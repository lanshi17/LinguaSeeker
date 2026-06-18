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

Extract the following information from the article text. For each field, \
use empty string/null if not found. Do NOT fabricate data not present in the article.

## 1. Gene & Disease
- **gene_symbol**: Usually MECP2. Some articles discuss CDKL5 or FOXG1 for atypical Rett.
- **disease_diagnosis**: "Rett syndrome", "atypical Rett syndrome", or specific subtype.
- **gene_disease_relationship**: "causative" (most common), "associated", or "susceptibility".
- **mode_of_inheritance**: "XD" (X-linked dominant) for MECP2. May be stated differently.
- **single_genetic_etiology_claim**: Does the article claim a single genetic etiology? \
"yes", "no", or "".

## 2. Variants (repeat for each variant found in the article)
- **hgvs_c**: HGVS coding notation (e.g. "c.808C>T")
- **hgvs_p**: HGVS protein notation (e.g. "p.R270X")
- **variant_type**: "missense", "nonsense", "frameshift", "deletion", "insertion", \
"splice", "duplication", or "other"
- **clinical_significance**: "pathogenic", "likely_pathogenic", "benign", \
"likely_benign", "uncertain", or ""
- **exon**: exon number (e.g. "4")
- **domain**: protein domain — MBD (aa 78-162), TRD (aa 201-310), NCoR/SMRT, NLS
- **protein_effect**: Description of protein-level effect (e.g. "loss of function", \
"impaired DNA binding", "reduced transcriptional repression"). Empty if not discussed.
- **null_variant_detail**: For loss-of-function variants: mechanism (e.g. "premature \
stop codon", "frameshift leading to nonsense-mediated decay"). Empty if not a null variant.
- **protein_length_change**: If the variant causes protein truncation or extension \
(e.g. "truncated at position 270", "57 amino acid extension"). Empty if no length change.

## 3. Case/Phenotype Information
- **case_count**: Number of independent cases reported in this article \
(e.g. "1", "3", "12"). Integer as string.
- **diagnosis_sufficiency**: How well-supported is the diagnosis? \
"definite" (meeting clinical criteria), "probable", "possible", or "".
- **phenotype_specificity**: How specific are the reported phenotypes to Rett? \
"highly_specific" (core Rett features), "partially_specific", "nonspecific", or "".
- **hpo_terms** (REQUIRED when clinical features are described): Map every clinical \
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

- **clinical_phenotypes**: Natural language descriptions of clinical features \
(separate from HPO codes).
- **sex**: "female", "male", or "".
- **age_of_onset**: Age at symptom onset (e.g. "6 months", "2 years", "childhood").
- **age_current_or_last_followup**: Current age or age at last follow-up \
(e.g. "8 years", "15 years").
- **ancestry_or_population**: Ethnic background or population if stated \
(e.g. "Chinese", "Japanese", "European", "Caucasian").
- **testing_method**: Genetic testing method used \
(e.g. "whole exome sequencing", "Sanger sequencing", "gene panel", "MLPA").
- **alternative_diagnosis_excluded**: Did the article report excluding other diagnoses? \
"yes", "no", or "".
- **biochemical_markers**: Any laboratory/biochemical findings \
(e.g. "elevated lactate", "normal karyotype"). Empty if not reported.

## 4. Family/Segregation Information
- **de_novo_status**: Whether the variant is "de novo", "inherited", or "unknown".
- **family_id**: Family identifier if the article labels families \
(e.g. "Family 1", "Family A"). Empty if not labeled.
- **pedigree_available**: Is a pedigree figure provided in the article? \
"yes", "no", or "".
- **parentage_confirmed**: Was parentage confirmed by DNA testing? \
"yes", "no", or "".
- **maternal_genotype**: Mother's genotype if tested \
(e.g. "heterozygous carrier", "wild-type", "not tested").
- **paternal_genotype**: Father's genotype if tested.
- **maternal_phenotype**: Mother's phenotype if described \
(e.g. "unaffected carrier", "mild learning difficulties").
- **paternal_phenotype**: Father's phenotype if described.
- **phase_status**: Phase information for compound heterozygotes \
(e.g. "in trans", "in cis", "unknown"). Empty if single variant.
- **in_trans_confirmation**: Were compound heterozygous variants confirmed in trans? \
"yes", "no", "not_applicable".
- **cis_or_trans_context**: Context for phase determination \
(e.g. "confirmed by parental testing", "inferred from allele frequency").
- **consanguinity**: Is consanguinity reported? "yes", "no", or "".

Respond with a valid JSON object matching the schema below.

JSON schema:
{
  "gene_symbol": "string",
  "disease_diagnosis": "string",
  "gene_disease_relationship": "string",
  "mode_of_inheritance": "string",
  "single_genetic_etiology_claim": "string",
  "variants": [
    {
      "hgvs_c": "string",
      "hgvs_p": "string",
      "variant_type": "string",
      "clinical_significance": "string",
      "exon": "string",
      "domain": "string",
      "protein_effect": "string",
      "null_variant_detail": "string",
      "protein_length_change": "string"
    }
  ],
  "case_count": "string",
  "diagnosis_sufficiency": "string",
  "phenotype_specificity": "string",
  "hpo_terms": ["HP:0001250", "HP:0001263"],
  "clinical_phenotypes": ["seizures", "developmental delay"],
  "sex": "string",
  "age_of_onset": "string",
  "age_current_or_last_followup": "string",
  "ancestry_or_population": "string",
  "testing_method": "string",
  "alternative_diagnosis_excluded": "string",
  "biochemical_markers": "string",
  "de_novo_status": "string",
  "family_id": "string",
  "pedigree_available": "string",
  "parentage_confirmed": "string",
  "maternal_genotype": "string",
  "paternal_genotype": "string",
  "maternal_phenotype": "string",
  "paternal_phenotype": "string",
  "phase_status": "string",
  "in_trans_confirmation": "string",
  "cis_or_trans_context": "string",
  "consanguinity": "string",
  "source_pmid": "string or null",
  "source_doi": "string or null",
  "source_title": "string or null",
  "source_year": "string or null",
  "source_journal": "string or null"
}
"""


def _build_expected_evidence(parsed: dict) -> list[ExpectedEvidenceField]:
    """Convert LLM output into catalog-compatible expected_evidence fields.

    Maps 35 field_ids across categories A, B, C.
    Variant-related fields use precision_only with candidates.
    All other fields use precision_recall.
    """
    fields: list[ExpectedEvidenceField] = []

    # --- Scalar helper: add a single-value field if non-empty ---
    def _add(field_id: str, value: str | None, eval_type: str = "precision_recall") -> None:
        if value and str(value).strip():
            fields.append(ExpectedEvidenceField(
                field_id=field_id,
                value=str(value).strip(),
                source="article",
                evaluation_type=eval_type,
            ))

    # --- Multi-value helper: add a list field joined by semicolons ---
    def _add_list(field_id: str, values: list[str], eval_type: str = "precision_recall") -> None:
        cleaned = [v.strip() for v in values if v and str(v).strip()]
        if cleaned:
            fields.append(ExpectedEvidenceField(
                field_id=field_id,
                value="; ".join(cleaned),
                source="article",
                evaluation_type=eval_type,
            ))

    # --- Variant multi-value helper: extract per-variant field with candidates ---
    def _add_variant_field(
        field_id: str,
        key: str,
        variants: list[dict],
    ) -> None:
        values = [str(v.get(key, "")).strip() for v in variants if v.get(key)]
        if values:
            fields.append(ExpectedEvidenceField(
                field_id=field_id,
                value=values[0],
                candidates=values if len(values) > 1 else [],
                source="article",
                evaluation_type="precision_only",
            ))

    # === Category A: Gene & Disease ===
    _add("A.gene_symbol", parsed.get("gene_symbol"))
    _add("A.gene_disease_relationship", parsed.get("gene_disease_relationship"))

    # === Category A: Variant fields ===
    variants = parsed.get("variants", [])
    if variants:
        _add_variant_field("A.variant_hgvs_c", "hgvs_c", variants)
        _add_variant_field("A.variant_hgvs_p", "hgvs_p", variants)
        _add_variant_field("A.variant_type", "variant_type", variants)
        _add_variant_field("A.functional_domain_or_hotspot", "domain", variants)
        _add_variant_field("A.protein_effect", "protein_effect", variants)
        _add_variant_field("A.null_variant_detail", "null_variant_detail", variants)
        _add_variant_field("A.protein_length_change", "protein_length_change", variants)

    # === Category B: Disease & Case Information ===
    _add("B.disease_diagnosis", parsed.get("disease_diagnosis"))
    _add("B.mode_of_inheritance_reported", parsed.get("mode_of_inheritance"))
    _add("B.single_genetic_etiology_claim", parsed.get("single_genetic_etiology_claim"))
    _add("B.case_count", parsed.get("case_count"))
    _add("B.diagnosis_sufficiency", parsed.get("diagnosis_sufficiency"))
    _add("B.phenotype_specificity", parsed.get("phenotype_specificity"))
    _add_list("B.hpo_terms", parsed.get("hpo_terms", []))
    _add_list("B.clinical_phenotypes", parsed.get("clinical_phenotypes", []))
    _add("B.sex", parsed.get("sex"))
    _add("B.age_of_onset", parsed.get("age_of_onset"))
    _add("B.age_current_or_last_followup", parsed.get("age_current_or_last_followup"))
    _add("B.ancestry_or_population", parsed.get("ancestry_or_population"))
    _add("B.testing_method", parsed.get("testing_method"))
    _add("B.alternative_diagnosis_excluded", parsed.get("alternative_diagnosis_excluded"))
    _add("B.biochemical_markers", parsed.get("biochemical_markers"))

    # === Category C: Segregation / Family ===
    _add("C.de_novo_status", parsed.get("de_novo_status"))
    _add("C.family_id", parsed.get("family_id"))
    _add("C.pedigree_available", parsed.get("pedigree_available"))
    _add("C.parentage_confirmed", parsed.get("parentage_confirmed"))
    _add("C.maternal_genotype", parsed.get("maternal_genotype"))
    _add("C.paternal_genotype", parsed.get("paternal_genotype"))
    _add("C.maternal_phenotype", parsed.get("maternal_phenotype"))
    _add("C.paternal_phenotype", parsed.get("paternal_phenotype"))
    _add("C.phase_status", parsed.get("phase_status"))
    _add("C.in_trans_confirmation", parsed.get("in_trans_confirmation"))
    _add("C.cis_or_trans_context", parsed.get("cis_or_trans_context"))
    _add("C.consanguinity", parsed.get("consanguinity"))

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
            protein_effect=v.get("protein_effect", ""),
            null_variant_detail=v.get("null_variant_detail", ""),
            protein_length_change=v.get("protein_length_change", ""),
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
