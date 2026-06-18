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
use empty string or empty array [] if not found. Do NOT fabricate data not \
present in the article. Include ALL keys in the output even if empty.

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
- **hgvs_g**: HGVS genomic notation (e.g. "chrX:g.153296777G>A"). Empty if not reported.
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
- **same_amino_acid_known_variant**: Known pathogenic variant at the same amino acid \
position (e.g. "p.R255X is pathogenic"). Empty if not mentioned.

## 3. Case/Phenotype Information
- **case_id**: Case identifier if labeled (e.g. "Patient 1", "Case 2"). Empty if not labeled.
- **proband_status**: "proband", "family member", or "".
- **case_count**: Number of independent cases reported in this article \
(e.g. "1", "3", "12"). Integer as string.
- **diagnosis_sufficiency**: How well-supported is the diagnosis? \
"definite" (meeting clinical criteria), "probable", "possible", or "".
- **phenotype_specificity**: How specific are the reported phenotypes to Rett? \
"highly_specific" (core Rett features), "partially_specific", "nonspecific", or "".
- **hpo_terms** (REQUIRED when clinical features are described): Map every clinical \
feature mentioned in the article to its HPO code using the table below. \
Include ALL applicable HPO terms as a JSON array. This field must NOT be empty \
if any clinical features are reported.

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

- **clinical_phenotypes**: JSON array of natural language descriptions of clinical features.
- **biochemical_markers**: Any laboratory/biochemical findings \
(e.g. "elevated lactate", "normal karyotype"). Empty if not reported.
- **sex**: "female", "male", or "".
- **age_of_onset**: Age at symptom onset (e.g. "6 months", "2 years", "childhood").
- **age_current_or_last_followup**: Current age or age at last follow-up \
(e.g. "8 years", "15 years").
- **ancestry_or_population**: Ethnic background or population if stated \
(e.g. "Chinese", "Japanese", "European", "Caucasian").
- **consanguinity**: Is consanguinity reported? "yes", "no", or "".
- **testing_method**: Genetic testing method used \
(e.g. "whole exome sequencing", "Sanger sequencing", "gene panel", "MLPA").
- **sequencing_method_quality**: Quality metrics if reported \
(e.g. "mean coverage 100x", "Sanger confirmed"). Empty if not reported.
- **alternative_diagnosis_excluded**: Did the article report excluding other diagnoses? \
"yes", "no", or "".
- **healthy_adult_status**: Are healthy adult controls mentioned? \
"unaffected", "carrier", or "".

## 4. Family/Segregation Information
- **de_novo_status**: Whether the variant is "de novo", "inherited", or "unknown".
- **inheritance_source**: Source of inheritance determination \
(e.g. "de novo (post-zygotic)", "inherited from mother", "unknown"). Empty if not stated.
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
- **obligate_carriers**: Obligate carriers identified (e.g. "mother", "none"). Empty if not discussed.
- **phase_status**: Phase information for compound heterozygotes \
(e.g. "in trans", "in cis", "unknown"). Empty if single variant.
- **in_trans_confirmation**: Were compound heterozygous variants confirmed in trans? \
"yes", "no", "not_applicable".
- **cis_or_trans_context**: Context for phase determination \
(e.g. "confirmed by parental testing", "inferred from allele frequency").

## 5. Population/Frequency Information
- **absent_or_rare_statement**: Statement about variant absence/rarity in population \
(e.g. "not observed in gnomAD", "absent from 1000 Genomes"). Empty if not stated.
- **population_database_name**: Population databases referenced \
(e.g. "gnomAD", "1000 Genomes", "ExAC"). Empty if not stated.
- **population_subgroup**: Population subgroup mentioned \
(e.g. "Indian", "Japanese", "European descent"). Empty if not stated.

## 6. Computational/Prediction Evidence
- **prediction_tools_list**: Computational tools mentioned \
(e.g. "SIFT", "PolyPhen-2", "CADD", "REVEL", "Exomiser"). Empty if not stated.

## 7. Functional Evidence
- **tested_variant**: Variant tested in functional assay (HGVS notation). Empty if no assay.
- **case_level_or_gene_level**: "case-level" or "gene-level". Empty if no functional data.
- **mechanism_consistency**: Is the functional result consistent with disease mechanism? \
(e.g. "loss of function consistent with Rett", "gain of function"). Empty if not discussed.

## 8. Case-Control Evidence
- **study_design**: Study design if case-control data is reported \
(e.g. "case-control", "cohort", "case report"). Empty if not applicable.
- **case_definition**: How cases were defined \
(e.g. "Rett syndrome diagnosis"). Empty if not stated.

## 9. Gene Function/Experimental Evidence
- **gene_function_biochemical**: Biochemical function of the gene \
(e.g. "MeCP2 functions as a transcriptional repressor"). Empty if not discussed.
- **gene_function_protein_interaction**: Protein interactions \
(e.g. "MeCP2 recruits histone deacetylase complex"). Empty if not discussed.

## 10. Authority/Time Validity
- **clinvar_assertion**: ClinVar accession if cited \
(e.g. "SCV001447189.1"). Empty if not cited.
- **authority_classification**: ACMG/AMP classification if stated \
(e.g. "pathogenic", "likely pathogenic", "VUS"). Empty if not stated.
- **known_pathogenic_variant_reference**: Reference to known pathogenic variant \
(e.g. "ClinVar SCV000123456", "HGMD CM001234"). Empty if not cited.
- **independent_publications_time_span**: Time span of cited independent publications \
(e.g. "2000-2019"). Empty if not determinable.

Respond with a valid JSON object. Include ALL keys listed above.

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
      "hgvs_g": "string",
      "variant_type": "string",
      "clinical_significance": "string",
      "exon": "string",
      "domain": "string",
      "protein_effect": "string",
      "null_variant_detail": "string",
      "protein_length_change": "string",
      "same_amino_acid_known_variant": "string"
    }
  ],
  "case_id": "string",
  "proband_status": "string",
  "case_count": "string",
  "diagnosis_sufficiency": "string",
  "phenotype_specificity": "string",
  "hpo_terms": ["HP:0001250", "HP:0001263"],
  "clinical_phenotypes": ["seizures", "developmental delay"],
  "biochemical_markers": "string",
  "sex": "string",
  "age_of_onset": "string",
  "age_current_or_last_followup": "string",
  "ancestry_or_population": "string",
  "consanguinity": "string",
  "testing_method": "string",
  "sequencing_method_quality": "string",
  "alternative_diagnosis_excluded": "string",
  "healthy_adult_status": "string",
  "de_novo_status": "string",
  "inheritance_source": "string",
  "family_id": "string",
  "pedigree_available": "string",
  "parentage_confirmed": "string",
  "maternal_genotype": "string",
  "paternal_genotype": "string",
  "maternal_phenotype": "string",
  "paternal_phenotype": "string",
  "obligate_carriers": "string",
  "phase_status": "string",
  "in_trans_confirmation": "string",
  "cis_or_trans_context": "string",
  "absent_or_rare_statement": "string",
  "population_database_name": "string",
  "population_subgroup": "string",
  "prediction_tools_list": "string",
  "tested_variant": "string",
  "case_level_or_gene_level": "string",
  "mechanism_consistency": "string",
  "study_design": "string",
  "case_definition": "string",
  "gene_function_biochemical": "string",
  "gene_function_protein_interaction": "string",
  "clinvar_assertion": "string",
  "authority_classification": "string",
  "known_pathogenic_variant_reference": "string",
  "independent_publications_time_span": "string",
  "source_pmid": "string or null",
  "source_doi": "string or null",
  "source_title": "string or null",
  "source_year": "string or null",
  "source_journal": "string or null"
}
"""


def _build_expected_evidence(parsed: dict) -> list[ExpectedEvidenceField]:
    """Convert LLM output into catalog-compatible expected_evidence fields.

    Maps 55 field_ids across categories A-J.
    Variant-related fields use precision_only with candidates.
    All other fields use precision_recall.
    """
    fields: list[ExpectedEvidenceField] = []

    # --- Scalar helper ---
    def _add(field_id: str, value: str | None, eval_type: str = "precision_recall") -> None:
        if value and str(value).strip():
            fields.append(ExpectedEvidenceField(
                field_id=field_id, value=str(value).strip(),
                source="article", evaluation_type=eval_type,
            ))

    # --- Multi-value helper ---
    def _add_list(field_id: str, values: list[str], eval_type: str = "precision_recall") -> None:
        cleaned = [v.strip() for v in values if v and str(v).strip()]
        if cleaned:
            fields.append(ExpectedEvidenceField(
                field_id=field_id, value="; ".join(cleaned),
                source="article", evaluation_type=eval_type,
            ))

    # --- Variant multi-value helper ---
    def _add_variant_field(field_id: str, key: str, variants: list[dict]) -> None:
        values = [str(v.get(key, "")).strip() for v in variants if v.get(key)]
        if values:
            fields.append(ExpectedEvidenceField(
                field_id=field_id, value=values[0],
                candidates=values if len(values) > 1 else [],
                source="article", evaluation_type="precision_only",
            ))

    # === Category A: Gene & Disease ===
    _add("A.gene_symbol", parsed.get("gene_symbol"))
    _add("A.gene_disease_relationship", parsed.get("gene_disease_relationship"))

    # === Category A: Variant fields ===
    variants = parsed.get("variants", [])
    if variants:
        _add_variant_field("A.variant_hgvs_c", "hgvs_c", variants)
        _add_variant_field("A.variant_hgvs_p", "hgvs_p", variants)
        _add_variant_field("A.variant_hgvs_g", "hgvs_g", variants)
        _add_variant_field("A.variant_type", "variant_type", variants)
        _add_variant_field("A.functional_domain_or_hotspot", "domain", variants)
        _add_variant_field("A.protein_effect", "protein_effect", variants)
        _add_variant_field("A.null_variant_detail", "null_variant_detail", variants)
        _add_variant_field("A.protein_length_change", "protein_length_change", variants)
        _add_variant_field("A.same_amino_acid_known_variant", "same_amino_acid_known_variant", variants)

    # === Category B: Case/Phenotype Information ===
    _add("B.case_id", parsed.get("case_id"))
    _add("B.proband_status", parsed.get("proband_status"))
    _add("B.disease_diagnosis", parsed.get("disease_diagnosis"))
    _add("B.mode_of_inheritance_reported", parsed.get("mode_of_inheritance"))
    _add("B.single_genetic_etiology_claim", parsed.get("single_genetic_etiology_claim"))
    _add("B.case_count", parsed.get("case_count"))
    _add("B.diagnosis_sufficiency", parsed.get("diagnosis_sufficiency"))
    _add("B.phenotype_specificity", parsed.get("phenotype_specificity"))
    _add_list("B.hpo_terms", parsed.get("hpo_terms", []))
    _add_list("B.clinical_phenotypes", parsed.get("clinical_phenotypes", []))
    _add("B.biochemical_markers", parsed.get("biochemical_markers"))
    _add("B.sex", parsed.get("sex"))
    _add("B.age_of_onset", parsed.get("age_of_onset"))
    _add("B.age_current_or_last_followup", parsed.get("age_current_or_last_followup"))
    _add("B.ancestry_or_population", parsed.get("ancestry_or_population"))
    _add("B.consanguinity", parsed.get("consanguinity"))
    _add("B.testing_method", parsed.get("testing_method"))
    _add("B.sequencing_method_quality", parsed.get("sequencing_method_quality"))
    _add("B.alternative_diagnosis_excluded", parsed.get("alternative_diagnosis_excluded"))
    _add("B.healthy_adult_status", parsed.get("healthy_adult_status"))

    # === Category C: Segregation / Family ===
    _add("C.de_novo_status", parsed.get("de_novo_status"))
    _add("C.inheritance_source", parsed.get("inheritance_source"))
    _add("C.family_id", parsed.get("family_id"))
    _add("C.pedigree_available", parsed.get("pedigree_available"))
    _add("C.parentage_confirmed", parsed.get("parentage_confirmed"))
    _add("C.maternal_genotype", parsed.get("maternal_genotype"))
    _add("C.paternal_genotype", parsed.get("paternal_genotype"))
    _add("C.maternal_phenotype", parsed.get("maternal_phenotype"))
    _add("C.paternal_phenotype", parsed.get("paternal_phenotype"))
    _add("C.obligate_carriers", parsed.get("obligate_carriers"))
    _add("C.phase_status", parsed.get("phase_status"))
    _add("C.in_trans_confirmation", parsed.get("in_trans_confirmation"))
    _add("C.cis_or_trans_context", parsed.get("cis_or_trans_context"))
    _add("C.consanguinity", parsed.get("consanguinity"))

    # === Category D: Population/Frequency ===
    _add("D.absent_or_rare_statement", parsed.get("absent_or_rare_statement"))
    _add("D.population_database_name", parsed.get("population_database_name"))
    _add("D.population_subgroup", parsed.get("population_subgroup"))

    # === Category E: Computational/Prediction ===
    _add("E.prediction_tools_list", parsed.get("prediction_tools_list"))

    # === Category F: Functional Evidence ===
    _add("F.tested_variant", parsed.get("tested_variant"))
    _add("F.case_level_or_gene_level", parsed.get("case_level_or_gene_level"))
    _add("F.mechanism_consistency", parsed.get("mechanism_consistency"))

    # === Category G: Case-Control ===
    _add("G.study_design", parsed.get("study_design"))
    _add("G.case_definition", parsed.get("case_definition"))

    # === Category I: Gene Function ===
    _add("I.gene_function_biochemical", parsed.get("gene_function_biochemical"))
    _add("I.gene_function_protein_interaction", parsed.get("gene_function_protein_interaction"))

    # === Category J: Authority/Time ===
    _add("J.clinvar_assertion", parsed.get("clinvar_assertion"))
    _add("J.authority_classification", parsed.get("authority_classification"))
    _add("J.known_pathogenic_variant_reference", parsed.get("known_pathogenic_variant_reference"))
    _add("J.independent_publications_time_span", parsed.get("independent_publications_time_span"))

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
            hgvs_g=normalize_hgvs(v.get("hgvs_g", "")),
            variant_type=v.get("variant_type", "") or classify_variant_type(v.get("hgvs_c", ""), v.get("hgvs_p", "")),
            clinical_significance=v.get("clinical_significance", ""),
            exon=v.get("exon", ""),
            domain=v.get("domain", "") or infer_domain(v.get("hgvs_p", "")),
            protein_effect=v.get("protein_effect", ""),
            null_variant_detail=v.get("null_variant_detail", ""),
            protein_length_change=v.get("protein_length_change", ""),
            same_amino_acid_known_variant=v.get("same_amino_acid_known_variant", ""),
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
