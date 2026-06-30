"""Contracts for evidence extraction."""
from __future__ import annotations

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ..contracts import TranslationAlignmentChunk
from .channel_contracts import DocumentChannelClassification


class Track(str, Enum):
    ORIGINAL = "original"
    TRANSLATED = "translated"
    RECONCILED = "reconciled"



_SPACE_RE = re.compile(r"\s+")


class ExtractionTarget(BaseModel):
    """Target gene-disease hypothesis for extraction."""

    gene_symbol: str
    disease_name: str
    variant_hgvs_p: str = ""
    clingen_entry_id: str = ""

    @model_validator(mode="after")
    def normalize_target_fields(self) -> ExtractionTarget:
        self.gene_symbol = _SPACE_RE.sub(" ", self.gene_symbol.strip()).upper()
        self.disease_name = _SPACE_RE.sub(" ", self.disease_name.strip())
        self.variant_hgvs_p = _SPACE_RE.sub(" ", self.variant_hgvs_p.strip())
        self.clingen_entry_id = _SPACE_RE.sub(" ", self.clingen_entry_id.strip())
        if not self.gene_symbol:
            raise ValueError("gene_symbol is required")
        if not self.disease_name:
            raise ValueError("disease_name is required")
        return self

    @property
    def scope_key(self) -> str:
        return "|".join(
            [
                f"gene={self.gene_symbol}",
                f"disease={self.disease_name.casefold()}",
                f"variant_p={self.variant_hgvs_p}",
                f"clingen={self.clingen_entry_id}",
            ]
        )


class EvidenceRole(str, Enum):
    PRIMARY = "primary"
    PHENOTYPE = "phenotype"
    COMPARATOR = "comparator"
    CONTEXT = "context"



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


class ContentBlock(BaseModel):
    type: str = "text"
    page_idx: int = 0
    bbox: list[int] = Field(default_factory=list)
    text: str = ""
    content: str = ""
    table_body: str = ""
    img_path: str = ""
    image_caption: list[str] = Field(default_factory=list)
    table_caption: list[str] = Field(default_factory=list)
    chart_caption: list[str] = Field(default_factory=list)
    code_body: str = ""
    list_items: list[str] = Field(default_factory=list)


class TrackDocument(BaseModel):
    document_id: str
    track: Track
    formatted_text: str
    page_spans: list[PageSpan]
    blocks: list[ContentBlock] = Field(default_factory=list)
    external_ids: ExternalIds = Field(default_factory=ExternalIds)
    metadata: dict[str, str] = Field(default_factory=dict)
    translation_alignment: list[TranslationAlignmentChunk] = Field(default_factory=list)
    extraction_target: ExtractionTarget | None = None



class SourcePrecision(str, Enum):
    EXACT = "exact"
    CORRECTED = "corrected"
    AMBIGUOUS = "ambiguous"


class SourceLocation(BaseModel):
    span_id: str = ""
    page: int = 0
    start_offset: int = -1
    end_offset: int = -1
    context_type: Literal[
        "text", "table", "figure", "supplementary", "caption",
        "abstract", "introduction", "methods", "results", "discussion",
        "conclusion", "background", "references", "title", "summary",
        "case_report", "affiliations", "patients",
    ]
    context_ref: str
    text_snippet: str
    block_index: int = -1
    bbox: list[int] = Field(default_factory=list)
    block_type: Literal["text", "table", "figure", "image", "caption", "supplementary"] = "text"
    source_precision: SourcePrecision = SourcePrecision.EXACT

class EvidenceStatus(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    NOT_APPLICABLE = "not_applicable"
    NOT_ATTEMPTED = "not_attempted"
    SOURCE_INVALID = "source_invalid"
    OCR_GAP = "ocr_gap"
    TABLE_UNGROUNDED = "table_ungrounded"
    CONTEXT_CONTAMINATION = "context_contamination"


class EvidenceAlignmentLabel(str, Enum):
    """Original-vs-translation alignment decision for one evidence field."""

    ALIGNED = "aligned"
    PARTIAL = "partial"
    DRIFTED = "drifted"
    CONFLICT = "conflict"
    MISSING = "missing"


class EvidenceSupportLabel(str, Enum):
    """Whether the compared tracks support the same evidence claim."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    INSUFFICIENT = "insufficient"



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
    group_id: str = ""
    notes: str = ""
    inference_basis: list[str] = Field(default_factory=list)
    requires_external_completion: bool = False
    external_completion_note: str = ""
    evidence_role: EvidenceRole = EvidenceRole.PRIMARY
    article_language: str = ""
    source_database: str = ""
    is_english: bool | None = None
    requires_translation: bool | None = None
    target_gene: str = ""
    target_disease: str = ""
    target_variant: str = ""
    evidence_source_language: str = ""

    @model_validator(mode="after")
    def normalize_language_metadata(self) -> EvidenceItem:
        language = self.article_language.strip().lower()
        if language and self.is_english is None:
            self.is_english = language in {"en", "eng", "english"}
        if self.requires_translation is None and self.is_english is not None:
            self.requires_translation = not self.is_english
        if not self.evidence_source_language and language:
            self.evidence_source_language = language
        return self


class EvidenceAlignmentRecord(BaseModel):
    """Source-grounded alignment between original-track and translated-track evidence."""

    entry_id: str = ""
    field_id: str
    original_value: str | None = None
    translated_value: str | None = None
    normalized_value: str = ""
    original_span_id: str = ""
    translated_span_id: str = ""
    alignment_label: EvidenceAlignmentLabel
    support_label: EvidenceSupportLabel
    drift_reason: str = ""
    confidence: float = Field(ge=0.0, le=1.0)

class EvidenceChain(BaseModel):
    chain_id: str
    chain_level: Literal["full", "partial", "singleton"] = "singleton"
    gene_text: str = ""
    gene_id: str | None = None
    disease_text: str = ""
    disease_id: str | None = None
    variant_text: str = ""
    variant_id: str | None = None
    case_ids: list[str] = Field(default_factory=list)
    special_evidence_ids: list[str] = Field(default_factory=list)
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


class RelevanceScanOutput(DocumentEvidenceMap):
    """Combined LLM output for the relevance scan.

    Extends :class:`DocumentEvidenceMap` with document-channel classification
    fields.  The LLM returns a single JSON object carrying both the evidence
    map and the channel labels; this model captures all of it so the stage
    can split the result into a ``DocumentEvidenceMap`` and a
    ``DocumentChannelClassification``.

    ``selected_channels`` are raw strings (e.g. ``"case_report"``) because the
    LLM cannot produce enum values directly; :func:`parse_channel_classification`
    converts them to :class:`DocumentEvidenceChannel` with validation.
    """

    selected_channels: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    rationale: str = ""
    supporting_block_ids: list[str] = Field(default_factory=list)


class SpecialEvidenceRecord(BaseModel):
    record_type: Literal["functional", "case_control", "authority", "contradiction"]
    description: str
    group_id: str = ""
    evidence_field_ids: list[str] = Field(default_factory=list)
    source: SourceLocation | None = None
    raw_source: SourceLocation | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class SpecialEvidenceResponse(BaseModel):
    records: list[SpecialEvidenceRecord] = Field(default_factory=list)


class PrimaryBroadEvidenceCandidate(BaseModel):
    """High-recall primary-track candidate before review validation."""

    field_id: str
    status: EvidenceStatus
    value: str | int | float | bool | list[str] | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_quote: str = ""
    notes: str = ""


class PrimaryBroadExtractionResponse(BaseModel):
    """Structured response for the B8 primary broad extraction pass."""

    evidence_items: list[PrimaryBroadEvidenceCandidate] = Field(default_factory=list)


class EvidenceReviewDecision(BaseModel):
    """Review-track decision for one primary extraction candidate."""

    candidate_index: int | None = None
    field_id: str
    action: Literal["approve", "reject", "correct"]
    value: str | int | float | bool | list[str] | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_quote: str = ""
    reason: str = ""


class EvidenceReviewResponse(BaseModel):
    """Structured review-track output.

    The review track may only decide over primary extraction candidates that
    already exist. It must not add new field IDs or new candidates.
    """

    decisions: list[EvidenceReviewDecision] = Field(default_factory=list)


class EvidenceTriStateReviewDecision(EvidenceReviewDecision):
    """Tri-state review decision for evidence-calibration experiments."""

    action: Literal["approve", "uncertain_keep_for_review", "reject", "correct"]


class EvidenceTriStateReviewResponse(BaseModel):
    """Tri-state review-track output for calibration runs."""

    decisions: list[EvidenceTriStateReviewDecision] = Field(default_factory=list)


class QualityIssue(BaseModel):
    issue_type: Literal[
        "missing_source",
        "invalid_source",
        "ambiguous_source",
        "low_confidence",
        "contradiction",
        "missing_required",
        "context_contamination",
    ]
    field_id: str
    description: str
    severity: Literal["warning", "error"] = "warning"



class QualityReport(BaseModel):
    passed: bool
    scorable: bool = True
    score_gate_passed: bool = False
    issues: list[QualityIssue] = Field(default_factory=list)
    found_count: int = 0
    not_found_count: int = 0
    source_invalid_count: int = 0
    ocr_gap_count: int = 0
    table_ungrounded_count: int = 0
    ambiguous_source_count: int = 0
    context_contamination_count: int = 0
    human_review_required: bool = False
    human_review_reasons: list[str] = Field(default_factory=list)
    human_review_by_category: dict[str, list[str]] = Field(default_factory=dict)



class EvidenceExtractionStatus(str, Enum):
    COMPLETED = "completed"
    NOT_RELEVANT = "not_relevant"


class EvidenceNormalizationIssueType(str, Enum):
    INVALID_HGVS = "invalid_hgvs"
    MISSING_VARIANT_DETAIL = "missing_variant_detail"
    SEMANTIC_CONFLICT = "semantic_conflict"
    GENERIC_PREDICTION_TOOL = "generic_prediction_tool"
    VALUE_NORMALIZED = "value_normalized"
    DUPLICATE_MERGED = "duplicate_merged"


class EvidenceNormalizationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class EvidenceNormalizationIssue(BaseModel):
    issue_type: EvidenceNormalizationIssueType
    severity: EvidenceNormalizationSeverity = EvidenceNormalizationSeverity.WARNING
    field_id: str
    message: str
    original_value: str | int | float | bool | list[str] | None = None
    normalized_value: str | int | float | bool | list[str] | None = None


class FieldEligibilitySummary(BaseModel):
    """Summary of field eligibility decisions for an extraction pass."""

    eligible_field_count: int = 0
    channel_excluded_field_count: int = 0
    target_excluded_field_count: int = 0
    not_applicable_count: int = 0
    not_attempted_count: int = 0



class EvidenceExtractionResult(BaseModel):
    status: EvidenceExtractionStatus
    document_id: str
    track: Track
    evidence_map: DocumentEvidenceMap | None = None
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    evidence_chains: list[EvidenceChain] = Field(default_factory=list)
    special_evidence: list[SpecialEvidenceRecord] = Field(default_factory=list)
    quality_report: QualityReport | None = None
    normalization_issues: list[EvidenceNormalizationIssue] = Field(default_factory=list)
    extraction_target: ExtractionTarget | None = None
    phenotype_evidence: list[EvidenceItem] = Field(default_factory=list)
    discarded_evidence: list[EvidenceItem] = Field(default_factory=list)
    channel_classification: DocumentChannelClassification | None = None
    field_eligibility_summary: FieldEligibilitySummary | None = None



class DualTrackDocuments(BaseModel):
    document_id: str
    original: TrackDocument
    translated: TrackDocument

    @model_validator(mode="after")
    def validate_tracks(self) -> DualTrackDocuments:
        if self.original.track != Track.ORIGINAL:
            raise ValueError("original document must use track=original")
        if self.translated.track != Track.TRANSLATED:
            raise ValueError("translated document must use track=translated")
        if self.original.document_id != self.document_id:
            raise ValueError("original document_id must match dual document_id")
        if self.translated.document_id != self.document_id:
            raise ValueError("translated document_id must match dual document_id")
        return self


class DualEvidenceExtractionResult(BaseModel):
    document_id: str
    original_result: EvidenceExtractionResult
    translated_result: EvidenceExtractionResult
    reconciled_result: EvidenceExtractionResult | None = None
    alignment_records: list[EvidenceAlignmentRecord] = Field(default_factory=list)


class EvidenceExtractionState(BaseModel):
    document: TrackDocument
    evidence_map: DocumentEvidenceMap | None = None
    channel_classification: DocumentChannelClassification | None = None
    channel_excluded_field_ids: frozenset[str] = Field(default_factory=frozenset)
    target_excluded_field_ids: frozenset[str] = Field(default_factory=frozenset)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    evidence_chains: list[EvidenceChain] = Field(default_factory=list)
    special_evidence: list[SpecialEvidenceRecord] = Field(default_factory=list)
    quality_report: QualityReport | None = None
    normalization_issues: list[EvidenceNormalizationIssue] = Field(default_factory=list)
    status: EvidenceExtractionStatus = EvidenceExtractionStatus.COMPLETED
    phenotype_evidence: list[EvidenceItem] = Field(default_factory=list)
    discarded_evidence: list[EvidenceItem] = Field(default_factory=list)
