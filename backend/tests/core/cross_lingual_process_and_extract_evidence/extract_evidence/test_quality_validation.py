from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceChain,
    EvidenceItem,
    EvidenceStatus,
    SpecialEvidenceRecord,
    SourceLocation,
    SourcePrecision,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import EvidenceItemNormalizer, QualityValidator


def test_quality_validation_flags_found_item_without_source():
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="BRCA1",
        confidence=0.9,
    )

    report = QualityValidator(required_field_ids=set()).validate([item], contradictions=[])

    assert report.passed is False
    assert report.issues[0].issue_type == "missing_source"


def test_quality_validation_treats_case_count_without_source_as_non_blocking():
    item = EvidenceItem(
        field_id="B.case_count",
        category="B",
        field_name="Independent case count",
        status=EvidenceStatus.FOUND,
        value=1,
        confidence=1.0,
        notes="Single case report; only one patient.",
    )

    report = QualityValidator(required_field_ids=set()).validate(
        [item],
        contradictions=[],
        chains=[EvidenceChain(chain_id="gene=G|variant=V", chain_level="full")],
    )

    assert report.passed is True
    assert report.scorable is True
    assert report.score_gate_passed is True
    assert "B.case_count is inferred from document structure and has no traceable source" in report.human_review_reasons


def test_quality_validation_marks_unscorable_when_required_item_missing():
    item = EvidenceItem(
        field_id="B.disease_diagnosis",
        category="B",
        field_name="Disease diagnosis",
        status=EvidenceStatus.NOT_FOUND,
        value=None,
        confidence=0.0,
    )

    report = QualityValidator(required_field_ids={"B.disease_diagnosis"}).validate([item], contradictions=[])

    assert report.scorable is False


def test_quality_validator_auto_derives_required_from_catalog():
    validator = QualityValidator()
    item = EvidenceItem(
        field_id="B.disease_diagnosis",
        category="B",
        field_name="Disease diagnosis",
        status=EvidenceStatus.NOT_FOUND,
        value=None,
        confidence=0.0,
    )
    report = validator.validate([item], contradictions=[])
    assert report.scorable is False


def test_quality_validation_counts_source_invalid():
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.SOURCE_INVALID,
        value="BRCA1",
        confidence=0.9,
    )
    report = QualityValidator(required_field_ids=set()).validate([item], contradictions=[])
    assert report.source_invalid_count == 1


def test_quality_validation_blocks_score_for_required_source_invalid():
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.SOURCE_INVALID,
        value="GLA",
        confidence=0.9,
    )

    report = QualityValidator(required_field_ids={"A.gene_symbol"}).validate([item], contradictions=[])

    assert report.passed is True
    assert report.scorable is False
    assert report.score_gate_passed is False
    assert report.human_review_required is True
    assert "A.gene_symbol" in report.human_review_reasons[0]


def test_quality_validation_counts_ocr_gap_and_requires_review():
    item = EvidenceItem(
        field_id="A.variant_hgvs_p",
        category="A",
        field_name="HGVS protein variant",
        status=EvidenceStatus.OCR_GAP,
        value="p.R227X",
        confidence=0.7,
    )

    report = QualityValidator(required_field_ids={"A.variant_hgvs_p"}).validate([item], contradictions=[])

    assert report.ocr_gap_count == 1
    assert report.scorable is False
    assert report.human_review_required is True


def test_quality_validation_counts_table_ungrounded_like_ocr_gap_for_review():
    item = EvidenceItem(
        field_id="B.biochemical_markers",
        category="B",
        field_name="Biochemical markers",
        status=EvidenceStatus.TABLE_UNGROUNDED,
        value="Lyso-GL-3 80.23 ng/mL",
        confidence=0.7,
    )

    report = QualityValidator(required_field_ids={"B.biochemical_markers"}).validate([item], contradictions=[])

    assert report.ocr_gap_count == 0
    assert report.human_review_required is True
    assert "B.biochemical_markers" in report.human_review_reasons[0]


def test_quality_validation_counts_ambiguous_sources_and_requires_review():
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="GLA",
        confidence=0.9,
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=3,
            context_type="text",
            context_ref="",
            text_snippet="GLA",
            source_precision=SourcePrecision.AMBIGUOUS,
        ),
    )

    report = QualityValidator(required_field_ids={"A.gene_symbol"}).validate([item], contradictions=[])

    assert report.ambiguous_source_count == 1
    assert report.scorable is False
    assert report.human_review_required is True


def test_quality_validation_requires_chain_for_score_gate():
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="GLA",
        confidence=0.9,
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=3,
            context_type="text",
            context_ref="",
            text_snippet="GLA",
        ),
    )

    report = QualityValidator(required_field_ids={"A.gene_symbol"}).validate(
        [item],
        contradictions=[],
        chains=[],
    )

    assert report.passed is True
    assert report.scorable is False
    assert report.score_gate_passed is False
    assert report.human_review_required is True


def test_quality_validation_keeps_structural_and_scoring_review_reasons_grouped():
    item = EvidenceItem(
        field_id="B.disease_diagnosis",
        category="B",
        field_name="Disease diagnosis",
        status=EvidenceStatus.FOUND,
        value="Fabry disease",
        confidence=0.95,
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=13,
            context_type="text",
            context_ref="title",
            text_snippet="Fabry disease",
            source_precision=SourcePrecision.AMBIGUOUS,
        ),
    )

    report = QualityValidator(required_field_ids={"B.disease_diagnosis"}).validate(
        [item],
        contradictions=["Conflict in diagnosis wording"],
        chains=[],
    )

    assert report.human_review_required is True
    assert report.human_review_reasons
    assert report.human_review_by_category["source_grounding"] == [
        "B.disease_diagnosis has ambiguous source grounding",
    ]
    assert report.human_review_by_category["scoring_gate"] == [
        "B.disease_diagnosis is required for scoring but is not grounded",
    ]
    assert report.human_review_by_category["contradictions"] == [
        "Contradiction requires review: Conflict in diagnosis wording",
    ]
    assert report.human_review_by_category["workflow"] == [
        "No full evidence chain was produced",
    ]


def test_quality_validation_marks_special_record_with_only_raw_source_for_review():
    record = SpecialEvidenceRecord(
        record_type="functional",
        description="Assay evidence",
        group_id="gene=BRCA1|variant=c.5266dupC",
        raw_source=SourceLocation(
            block_index=1,
            context_type="figure",
            context_ref="Figure 1",
            text_snippet="assay evidence",
        ),
    )

    report = QualityValidator(required_field_ids=set()).validate(
        [],
        contradictions=[],
        chains=[],
        special_records=[record],
    )

    assert report.human_review_required is True
    assert report.human_review_by_category["source_grounding"] == [
        "Special evidence functional requires source grounding review",
    ]


def test_normalizer_expands_sparse_llm_output_to_full_catalog():
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value="GLA",
        confidence=0.9,
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=3,
            context_type="text",
            context_ref="",
            text_snippet="GLA",
        ),
    )

    normalized = EvidenceItemNormalizer().normalize([item])

    field_ids = {i.field_id for i in normalized}
    assert "A.gene_symbol" in field_ids
    assert "D.allele_frequency" in field_ids
    assert next(i for i in normalized if i.field_id == "D.allele_frequency").status == EvidenceStatus.NOT_FOUND


def test_normalizer_clears_scoring_assignments_for_non_found_items():
    item = EvidenceItem(
        field_id="D.allele_frequency",
        category="D",
        field_name="Allele frequency",
        status=EvidenceStatus.NOT_FOUND,
        value=None,
        assigned_acmg_codes=["PM2"],
        assigned_clingen_modules=["variant_evidence"],
        confidence=0.0,
    )

    normalized = EvidenceItemNormalizer().normalize([item])
    allele_frequency = next(i for i in normalized if i.field_id == "D.allele_frequency")

    assert allele_frequency.assigned_acmg_codes == []
    assert allele_frequency.assigned_clingen_modules == []
    assert allele_frequency.requires_external_completion is True


def test_normalizer_routes_model_source_invalid_with_source_back_to_grounding():
    item = EvidenceItem(
        field_id="B.diagnosis_sufficiency",
        category="B",
        field_name="Diagnosis sufficiency",
        status=EvidenceStatus.SOURCE_INVALID,
        value="Diagnosis confirmed by genetic testing and clinical features",
        confidence=0.8,
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=10,
            end_offset=30,
            context_type="text",
            context_ref="",
            text_snippet="diagnosed by sequencing",
        ),
    )

    normalized = EvidenceItemNormalizer().normalize([item])
    diagnosis = next(i for i in normalized if i.field_id == "B.diagnosis_sufficiency")

    assert diagnosis.status == EvidenceStatus.FOUND


def test_normalizer_keeps_source_invalid_without_source_invalid():
    item = EvidenceItem(
        field_id="B.diagnosis_sufficiency",
        category="B",
        field_name="Diagnosis sufficiency",
        status=EvidenceStatus.SOURCE_INVALID,
        value="Diagnosis confirmed by genetic testing and clinical features",
        confidence=0.8,
    )

    normalized = EvidenceItemNormalizer().normalize([item])
    diagnosis = next(i for i in normalized if i.field_id == "B.diagnosis_sufficiency")

    assert diagnosis.status == EvidenceStatus.SOURCE_INVALID
    assert diagnosis.value == "Diagnosis confirmed by genetic testing and clinical features"

def test_quality_validation_counts_context_contamination():
    item = EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.CONTEXT_CONTAMINATION,
        value="CFTR",
        confidence=0.8,
    )

    report = QualityValidator(required_field_ids={"A.gene_symbol"}).validate([item], contradictions=[])

    assert report.context_contamination_count == 1
    assert report.scorable is False
