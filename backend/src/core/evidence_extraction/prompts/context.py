"""Prompt builders for evidence extraction stages."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from ..contracts import ExtractionTarget, Track

def get_clinical_context_prompt(
    document_id: str,
    track: Track,
    text: str,
    current_items_summary: str,
) -> str:
    return f"""You are extracting clinical context from a biomedical document.

FOCUS: Extract ONLY the following fields. Do NOT extract any other fields.

FIELDS:
- B.clinical_phenotypes: Patient's clinical presentation, symptoms, neurological features,
  developmental regression, seizures, movement abnormalities, tremor, rigidity, bradykinesia,
  ataxia, intellectual disability, motor delay, speech delay, hypotonia, spasticity.
  Multiple phenotypes: separate with semicolons (e.g. "seizures; developmental regression; ataxia").
  Do NOT copy the disease diagnosis as a phenotype. Extract actual observed symptoms and signs.
- B.sex: Explicit sex or gender of the patient (e.g. "male", "female"). Only extract if clearly stated.
- B.age_of_onset: Age at first symptoms, diagnosis, or presentation. Only extract explicit ages
  (e.g. "3 years", "onset at age 2", "neonatal"). Do NOT use developmental milestones
  (sitting, walking, talking) unless they are explicitly described as symptom onset.
- B.mode_of_inheritance_reported: Inheritance pattern stated in the document
  (e.g. "autosomal recessive", "autosomal dominant", "X-linked", "AD", "AR", "XL").
  Only extract if explicitly stated.
- C.inheritance_source: Whether the variant was inherited or arose de novo
  (e.g. "inherited from mother", "paternal", "maternal", "de novo"). Must have family/
  parental/genotyping evidence.
- C.de_novo_status: Whether the variant was confirmed as de novo
  (e.g. "confirmed de novo", "likely de novo", "inherited"). Requires parental testing
  or family study evidence.

RULES:
1. Each found item MUST include a source with text_snippet that is a verbatim substring of the document.
2. Set status="found" with extracted value, or status="not_found" if the document does not contain the information.
3. Do not invent information not present in the document.
4. Confidence should reflect extraction certainty (0.0-1.0).
5. For B.clinical_phenotypes, look in case descriptions, clinical findings, patient presentations,
   results sections, tables with clinical features. Do NOT use disease names as phenotypes.

Document ID: {document_id}
Track: {track.value}

CURRENT EXTRACTION SUMMARY (what has already been extracted):
{current_items_summary}

DOCUMENT TEXT:
{text}
"""


def get_core_identity_retry_prompt(
    document_id: str,
    track: Track,
    text: str,
    extraction_target: ExtractionTarget,
) -> str:
    """Compact retry prompt targeting only core identity fields.

    Used when the normal catalog extraction fails to produce FOUND items
    for ``A.gene_symbol`` or ``B.disease_diagnosis``.  The prompt is
    deliberately small (4 fields, no full catalog) to maximise extraction
    reliability on these critical fields.
    """
    return f"""You are extracting core identity fields from a biomedical document.

TARGET GENE: {extraction_target.gene_symbol}
TARGET DISEASE: {extraction_target.disease_name}

Extract ONLY these four fields. For each, set status="found" with the
extracted value, or status="not_found" if the document does not support it.

FIELDS:
- A.gene_symbol: Extract the target gene symbol ({extraction_target.gene_symbol}) ONLY if it
  appears in the document text, title, abstract, or is unambiguously stated as the gene under study.
  Do NOT extract other genes mentioned for comparison or background.
- B.disease_diagnosis: Extract the target disease ({extraction_target.disease_name}) ONLY if the
  document discusses this disease (or a close named synonym) in relation to the target gene/variant.
  Do NOT extract unrelated diseases.
- A.variant_hgvs_c: Extract an exact HGVS coding-level variant string (e.g. "c.880C>T") ONLY if
  it appears verbatim in the document. Do NOT infer or construct variant strings.
- A.variant_hgvs_p: Extract an exact HGVS protein-level variant string (e.g. "p.R294X") ONLY if
  it appears verbatim in the document. Do NOT infer or construct variant strings.

RULES:
1. Do not infer values that are not explicitly stated in the document.
2. For found items, provide source with context_type, context_ref, and text_snippet (verbatim substring).
3. Confidence should reflect certainty (0.0-1.0).

Document ID: {document_id}
Track: {track.value}

DOCUMENT TEXT:
{text}
"""
