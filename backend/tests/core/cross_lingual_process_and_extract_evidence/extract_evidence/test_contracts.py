import pytest
from pydantic import ValidationError

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    DocumentEvidenceMap,
    DualTrackDocuments,
    EvidenceChain,
    EvidenceExtractionResult,
    EvidenceExtractionState,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceNormalizationIssue,
    EvidenceNormalizationIssueType,
    EvidenceNormalizationSeverity,
    EvidenceRole,
    EvidenceStatus,
    ExternalIds,
    ExtractionTarget,
    PageSpan,
    QualityReport,
    SourceLocation,
    SourcePrecision,
    SpecialEvidenceRecord,
    Track,
    TrackDocument,
)


def test_track_document_accepts_upstream_spans():
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="Patient 1 has BRCA1 c.68_69delAG.",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=36)],
        blocks=[ContentBlock(type="text", page_idx=0, text="Patient 1 has BRCA1 c.68_69delAG.")],
        external_ids=ExternalIds(pmid="123"),
    )

    assert doc.track == Track.ORIGINAL
    assert doc.page_spans[0].span_id == "p1"
    assert doc.blocks[0].type == "text"


def test_dual_track_documents_require_original_and_translated_tracks():
    original = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="源文本",
        page_spans=[PageSpan(span_id="original-p1", page=1, start_offset=0, end_offset=3)],
    )
    translated = TrackDocument(
        document_id="doc-1",
        track=Track.TRANSLATED,
        formatted_text="Translated text",
        page_spans=[PageSpan(span_id="translated-p1", page=1, start_offset=0, end_offset=15)],
    )

    documents = DualTrackDocuments(document_id="doc-1", original=original, translated=translated)

    assert documents.original.track == Track.ORIGINAL
    assert documents.translated.track == Track.TRANSLATED


def test_dual_track_documents_reject_wrong_track_assignment():
    original = TrackDocument(
        document_id="doc-1",
        track=Track.TRANSLATED,
        formatted_text="Translated text",
        page_spans=[PageSpan(span_id="translated-p1", page=1, start_offset=0, end_offset=15)],
    )
    translated = TrackDocument(
        document_id="doc-1",
        track=Track.TRANSLATED,
        formatted_text="Translated text",
        page_spans=[PageSpan(span_id="translated-p1", page=1, start_offset=0, end_offset=15)],
    )

    with pytest.raises(ValidationError):
        DualTrackDocuments(document_id="doc-1", original=original, translated=translated)


def test_evidence_item_found_requires_confidence_in_range():
    source = SourceLocation(
        span_id="p1",
        page=1,
        start_offset=14,
        end_offset=19,
        context_type="text",
        context_ref="Results paragraph 1",
        text_snippet="BRCA1",
        source_precision=SourcePrecision.EXACT,
    )

    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="BRCA1",
        assigned_acmg_codes=[],
        assigned_clingen_modules=["variant_evidence"],
        source=source,
        confidence=0.95,
    )

    assert item.source == source


def test_evidence_item_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        EvidenceItem(
            field_id="A.gene_symbol",
            category="A",
            field_name="Gene symbol",
            status=EvidenceStatus.FOUND,
            value="BRCA1",
            assigned_acmg_codes=[],
            assigned_clingen_modules=[],
            confidence=1.5,
        )


def test_page_span_rejects_invalid_offsets():
    with pytest.raises(ValidationError):
        PageSpan(span_id="p1", page=1, start_offset=100, end_offset=50)


def test_evidence_item_accepts_boundary_confidence():
    item_min = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="BRCA1",
        confidence=0.0,
    )
    item_max = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="BRCA1",
        confidence=1.0,
    )
    assert item_min.confidence == 0.0
    assert item_max.confidence == 1.0


def test_evidence_item_rejects_negative_confidence():
    with pytest.raises(ValidationError):
        EvidenceItem(
            field_id="A.gene_symbol",
            category="A",
            field_name="Gene symbol",
            status=EvidenceStatus.FOUND,
            value="BRCA1",
            confidence=-0.1,
        )


def test_enum_values():
    assert Track.ORIGINAL.value == "original"
    assert Track.TRANSLATED.value == "translated"
    assert EvidenceStatus.FOUND.value == "found"
    assert EvidenceStatus.NOT_FOUND.value == "not_found"
    assert EvidenceStatus.OCR_GAP.value == "ocr_gap"
    assert SourcePrecision.EXACT.value == "exact"
    assert SourcePrecision.CORRECTED.value == "corrected"
    assert EvidenceExtractionStatus.COMPLETED.value == "completed"
    assert EvidenceExtractionStatus.NOT_RELEVANT.value == "not_relevant"


def test_source_location_carries_block_type_for_image_and_table_review():
    source = SourceLocation(
        span_id="img-1",
        page=2,
        start_offset=100,
        end_offset=125,
        context_type="figure",
        context_ref="Figure 1",
        text_snippet="Sequencing trace image",
        block_type="image",
        source_precision=SourcePrecision.EXACT,
    )

    assert source.block_type == "image"


def test_evidence_item_carries_inference_and_external_completion_metadata():
    item = EvidenceItem(
        field_id="D.allele_frequency",
        category="D",
        field_name="Allele frequency",
        status=EvidenceStatus.NOT_FOUND,
        value=None,
        confidence=0.0,
        inference_basis=["document does not mention gnomAD or population frequency"],
        requires_external_completion=True,
        external_completion_note="Population frequency must be completed by an external annotation provider.",
    )

    assert item.inference_basis == ["document does not mention gnomAD or population frequency"]
    assert item.requires_external_completion is True
    assert "external annotation" in item.external_completion_note


def test_evidence_chain_defaults():
    chain = EvidenceChain(chain_id="chain-1")
    assert chain.chain_level == "singleton"
    assert chain.gene_text == ""
    assert chain.gene_id is None
    assert chain.case_ids == []
    assert chain.special_evidence_ids == []
    assert chain.evidence_field_ids == []
    assert chain.contradictions == []


def test_document_evidence_map_defaults():
    emap = DocumentEvidenceMap(relevant=True)
    assert emap.relevant is True
    assert emap.disease_terms == []
    assert emap.gene_terms == []


def test_special_evidence_record_defaults():
    rec = SpecialEvidenceRecord(
        record_type="functional",
        description="Western blot showed loss of function",
    )
    assert rec.confidence == 0.5
    assert rec.group_id == ""
    assert rec.source is None
    assert rec.raw_source is None
    assert rec.evidence_field_ids == []


def test_special_evidence_record_rejects_invalid_record_type():
    with pytest.raises(ValidationError):
        SpecialEvidenceRecord(record_type="invalid", description="test")


def test_quality_report_defaults():
    report = QualityReport(passed=True)
    assert report.scorable is True
    assert report.score_gate_passed is False
    assert report.human_review_required is False
    assert report.human_review_reasons == []
    assert report.issues == []
    assert report.found_count == 0
    assert report.not_found_count == 0
    assert report.source_invalid_count == 0
    assert report.ocr_gap_count == 0
    assert report.ambiguous_source_count == 0


def test_evidence_extraction_result_with_not_relevant():
    result = EvidenceExtractionResult(
        status=EvidenceExtractionStatus.NOT_RELEVANT,
        document_id="doc-1",
        track=Track.ORIGINAL,
    )
    assert result.evidence_items == []
    assert result.quality_report is None


def test_evidence_extraction_state_roundtrip():
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="BRCA1 variant",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=13)],
    )
    state = EvidenceExtractionState(document=doc)
    data = state.model_dump()
    restored = EvidenceExtractionState(**data)
    assert restored.document.document_id == "doc-1"
    assert restored.status == EvidenceExtractionStatus.COMPLETED


def test_evidence_normalization_issue_contract() -> None:
    issue = EvidenceNormalizationIssue(
        issue_type=EvidenceNormalizationIssueType.INVALID_HGVS,
        severity=EvidenceNormalizationSeverity.ERROR,
        field_id="A.variant_hgvs_g",
        message="Coordinate-only value is not valid HGVS.",
        original_value="chr6_44270253",
    )

    assert issue.issue_type == EvidenceNormalizationIssueType.INVALID_HGVS
    assert issue.severity == EvidenceNormalizationSeverity.ERROR
    assert issue.field_id == "A.variant_hgvs_g"


def test_extraction_result_and_state_carry_normalization_issues() -> None:
    issue = EvidenceNormalizationIssue(
        issue_type=EvidenceNormalizationIssueType.INVALID_HGVS,
        severity=EvidenceNormalizationSeverity.ERROR,
        field_id="A.variant_hgvs_g",
        message="Coordinate-only value is not valid HGVS.",
        original_value="chr6_44270253",
    )

    result = EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id="doc",
        track=Track.ORIGINAL,
        normalization_issues=[issue],
    )
    state = EvidenceExtractionState(
        document=TrackDocument(
            document_id="doc",
            track=Track.ORIGINAL,
            formatted_text="",
            page_spans=[],
        ),
        normalization_issues=[issue],
    )

    assert result.normalization_issues == [issue]
    assert state.normalization_issues == [issue]

def test_extraction_target_contract_normalizes_scope_identity() -> None:
    target = ExtractionTarget(
        gene_symbol=" abca3 ",
        disease_name=" Interstitial lung disease due to ABCA3 deficiency ",
        variant_hgvs_p=" p.Q215* ",
        clingen_entry_id="CGGV:0001",
    )

    assert target.gene_symbol == "ABCA3"
    assert target.disease_name == "Interstitial lung disease due to ABCA3 deficiency"
    assert target.scope_key == (
        "gene=ABCA3|disease=interstitial lung disease due to abca3 deficiency|"
        "variant_p=p.Q215*|clingen=CGGV:0001"
    )


def test_extraction_target_rejects_blank_gene_or_disease() -> None:
    with pytest.raises(ValidationError):
        ExtractionTarget(gene_symbol="  ", disease_name="x")
    with pytest.raises(ValidationError):
        ExtractionTarget(gene_symbol="ABCA3", disease_name="  ")


def test_track_document_and_result_carry_extraction_target() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")
    doc = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="ABCA3 case",
        page_spans=[],
        extraction_target=target,
    )
    result = EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id="doc-1",
        track=Track.ORIGINAL,
        extraction_target=target,
    )

    assert doc.extraction_target == target
    assert result.extraction_target == target


def test_evidence_item_defaults_to_primary_role() -> None:
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="ABCA3",
        confidence=0.9,
    )

    assert item.evidence_role == EvidenceRole.PRIMARY
    assert EvidenceRole.PHENOTYPE.value == "phenotype"


def test_evidence_status_includes_context_contamination() -> None:
    assert EvidenceStatus.CONTEXT_CONTAMINATION.value == "context_contamination"


def test_quality_report_has_context_contamination_count() -> None:
    report = QualityReport(passed=True)
    assert report.context_contamination_count == 0


def test_evidence_extraction_result_separates_phenotype_and_discarded() -> None:
    target = ExtractionTarget(gene_symbol="AARS2", disease_name="AARS2-related leukodystrophy")
    primary = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="AARS2",
        confidence=0.9,
    )
    phenotype = EvidenceItem(
        field_id="B.disease_diagnosis",
        category="B",
        field_name="Disease diagnosis",
        status=EvidenceStatus.FOUND,
        value="COXPD8",
        confidence=0.9,
        evidence_role=EvidenceRole.PHENOTYPE,
    )
    discarded = EvidenceItem(
        field_id="B.disease_diagnosis",
        category="B",
        field_name="Disease diagnosis",
        status=EvidenceStatus.FOUND,
        value="Anti-NF155 autoimmune nodopathy",
        confidence=0.9,
        evidence_role=EvidenceRole.COMPARATOR,
    )
    result = EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id="doc-1",
        track=Track.ORIGINAL,
        extraction_target=target,
        evidence_items=[primary],
        phenotype_evidence=[phenotype],
        discarded_evidence=[discarded],
    )

    assert result.phenotype_evidence == [phenotype]
    assert result.discarded_evidence == [discarded]
    assert result.evidence_items == [primary]