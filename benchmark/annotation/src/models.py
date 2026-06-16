"""Pydantic schemas for the Rett benchmark annotation tool.

All field_ids in expected_evidence conform to the main project's
EVIDENCE_FIELD_SPECS catalog (138 fields, categories A–J).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ExpectedEvidenceField(BaseModel):
    """One expected evidence field — field_id must match EVIDENCE_FIELD_SPECS."""

    field_id: str
    value: str
    candidates: list[str] = Field(default_factory=list)
    source: str = "article"
    evaluation_type: str = "precision_recall"


class ArticleVariant(BaseModel):
    """A variant reported in the article."""

    hgvs_c: str = ""
    hgvs_p: str = ""
    variant_type: str = ""
    clinical_significance: str = ""
    exon: str = ""
    domain: str = ""


class RettExpectedJson(BaseModel):
    """Top-level expected.json for a Rett benchmark entry.

    Schema is fully compatible with the fused dataset's expected.json:
    same field_id vocabulary (A–J catalog), same evaluation_type enum,
    same evaluation_config partition keys.
    """

    entry_id: str
    source: str = "rett_literature"

    gene_symbol: str = "MECP2"
    hgnc_id: str = "HGNC:6992"
    disease_label: str = "Rett syndrome"
    mondo_id: str = "MONDO:0010726"
    moi: str = "XD"

    source_pmid: str | None = None
    source_doi: str | None = None
    source_title: str | None = None
    source_journal: str | None = None
    source_year: str | None = None
    source_language: str = "en"
    source_pdf_path: str = ""

    variants: list[ArticleVariant] = Field(default_factory=list)

    expected_evidence: list[ExpectedEvidenceField] = Field(default_factory=list)

    expected_standardization: dict[str, str | list[str]] = Field(default_factory=lambda: {
        "gene": "HGNC:6992",
        "disease": "MONDO:0010726",
    })

    expected_entities: dict = Field(default_factory=dict)

    evaluation_config: dict = Field(default_factory=lambda: {
        "gene_disease_fields": [
            "A.gene_symbol",
            "B.disease_diagnosis",
            "A.gene_disease_relationship",
            "B.mode_of_inheritance_reported",
        ],
        "variant_fields": [
            "A.variant_hgvs_c",
            "A.variant_hgvs_p",
            "A.variant_type",
            "A.functional_domain_or_hotspot",
        ],
        "clinical_fields": [
            "B.hpo_terms",
            "B.clinical_phenotypes",
            "B.sex",
            "B.age_of_onset",
            "C.de_novo_status",
        ],
        "standardization_fields": ["gene", "disease"],
    })

    notes: str = ""


class DraftMeta(BaseModel):
    """Metadata for a draft annotation entry."""

    entry_id: str
    pdf_path: str
    language: str
    parse_status: str = "pending"
    annotation_status: str = "pending"
    review_status: str = "draft"
    reviewer: str | None = None
    review_notes: str = ""
    rejection_reason: str = ""
    generated_at: str | None = None
    reviewed_at: str | None = None
    promoted_at: str | None = None
    llm_model: str = ""
    parse_backend: str = ""
    variant_count: int = 0
    clinical_feature_count: int = 0


class ManifestEntry(BaseModel):
    entry_id: str
    language: str
    status: str = "draft"
    pdf_path: str = ""
    current_dir: str = ""
    created_at: str = ""
    updated_at: str = ""


class Manifest(BaseModel):
    version: str = "1.0"
    entries: list[ManifestEntry] = Field(default_factory=list)
    last_updated: str = ""
