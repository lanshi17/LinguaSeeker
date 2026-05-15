"""Contracts for evidence extraction."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Track(str, Enum):
    ORIGINAL = "original"
    TRANSLATED = "translated"


class ExternalIds(BaseModel):
    pmid: str | None = None
    doi: str | None = None
    pmcid: str | None = None


class PageSpan(BaseModel):
    span_id: str
    page: int
    start_offset: int
    end_offset: int

    @model_validator(mode="after")
    def validate_offsets(self) -> PageSpan:
        if self.end_offset < self.start_offset:
            raise ValueError("end_offset must be >= start_offset")
        return self


class TrackDocument(BaseModel):
    document_id: str
    track: Track
    formatted_text: str
    page_spans: list[PageSpan]
    external_ids: ExternalIds = Field(default_factory=ExternalIds)
    metadata: dict[str, str] = Field(default_factory=dict)


class SourcePrecision(str, Enum):
    EXACT = "exact"
    CORRECTED = "corrected"
    AMBIGUOUS = "ambiguous"


class SourceLocation(BaseModel):
    span_id: str
    page: int
    start_offset: int
    end_offset: int
    context_type: Literal["text", "table", "figure", "supplementary", "caption"]
    context_ref: str
    text_snippet: str
    source_precision: SourcePrecision = SourcePrecision.EXACT


class EvidenceStatus(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    SOURCE_INVALID = "source_invalid"


class EvidenceItem(BaseModel):
    """Extracted evidence for a single catalog field.

    ``assigned_acmg_codes`` and ``assigned_clingen_modules`` capture the
    LLM's runtime assessment of which codes/modules apply to *this specific
    extraction instance*. They may differ from the canonical catalog values
    (which are retrievable via ``get_field_spec(field_id)``).
    """

    field_id: str
    category: str
    field_name: str
    status: EvidenceStatus
    value: str | int | float | bool | list[str] | None
    assigned_acmg_codes: list[str] = Field(default_factory=list)
    assigned_clingen_modules: list[str] = Field(default_factory=list)
    source: SourceLocation | None = None
    raw_source: SourceLocation | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str = ""


class EvidenceChain(BaseModel):
    chain_id: str
    gene_text: str = ""
    gene_id: str | None = None
    disease_text: str = ""
    disease_id: str | None = None
    variant_text: str = ""
    variant_id: str | None = None
    case_id: str | None = None
    evidence_field_ids: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    quality_warnings: list[str] = Field(default_factory=list)


class DocumentEvidenceMap(BaseModel):
    relevant: bool
    disease_terms: list[str] = Field(default_factory=list)
    gene_terms: list[str] = Field(default_factory=list)
    variant_terms: list[str] = Field(default_factory=list)
    case_references: list[str] = Field(default_factory=list)
    authority_references: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    structure_hints: list[str] = Field(default_factory=list)


class SpecialEvidenceRecord(BaseModel):
    record_type: Literal["functional", "case_control", "authority", "contradiction"]
    description: str
    evidence_field_ids: list[str] = Field(default_factory=list)
    source: SourceLocation | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class QualityIssue(BaseModel):
    issue_type: Literal[
        "missing_source",
        "invalid_source",
        "ambiguous_source",
        "low_confidence",
        "contradiction",
        "missing_required",
    ]
    field_id: str
    description: str
    severity: Literal["warning", "error"] = "warning"


class QualityReport(BaseModel):
    passed: bool
    scorable: bool = True
    issues: list[QualityIssue] = Field(default_factory=list)
    found_count: int = 0
    not_found_count: int = 0
    source_invalid_count: int = 0


class EvidenceExtractionStatus(str, Enum):
    COMPLETED = "completed"
    NOT_RELEVANT = "not_relevant"


class EvidenceExtractionResult(BaseModel):
    status: EvidenceExtractionStatus
    document_id: str
    track: Track
    evidence_map: DocumentEvidenceMap | None = None
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    evidence_chains: list[EvidenceChain] = Field(default_factory=list)
    special_evidence: list[SpecialEvidenceRecord] = Field(default_factory=list)
    quality_report: QualityReport | None = None


class EvidenceExtractionState(BaseModel):
    document: TrackDocument
    evidence_map: DocumentEvidenceMap | None = None
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    evidence_chains: list[EvidenceChain] = Field(default_factory=list)
    special_evidence: list[SpecialEvidenceRecord] = Field(default_factory=list)
    quality_report: QualityReport | None = None
    status: EvidenceExtractionStatus = EvidenceExtractionStatus.COMPLETED
