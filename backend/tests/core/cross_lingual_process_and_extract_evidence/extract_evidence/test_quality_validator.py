from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceChain,
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SpecialEvidenceRecord,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import QualityValidator


def _found(field_id: str, group_id: str) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id.split(".")[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value="value",
        confidence=0.9,
        group_id=group_id,
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=5,
            context_type="text",
            context_ref="",
            text_snippet="value",
        ),
    )


def test_quality_gate_passes_with_one_full_chain_even_when_partial_exists():
    full = "gene=BRCA1|variant=c.5266dupC"
    partial = "gene=GLA|variant=__missing__"
    chains = [
        EvidenceChain(chain_id=full, chain_level="full"),
        EvidenceChain(chain_id=partial, chain_level="singleton"),
    ]

    report = QualityValidator(required_field_ids=set()).validate(
        items=[_found("A.gene_symbol", full), _found("A.gene_symbol", partial)],
        contradictions=[],
        chains=chains,
        special_records=[],
    )

    assert report.scorable is True
    assert report.score_gate_passed is True
    assert report.human_review_required is True
    assert "Incomplete evidence chain requires review" in " ".join(report.human_review_reasons)


def test_quality_gate_requires_review_without_full_chain():
    chain = EvidenceChain(chain_id="gene=GLA|variant=__missing__", chain_level="singleton")

    report = QualityValidator(required_field_ids=set()).validate(
        items=[_found("A.gene_symbol", chain.chain_id)],
        contradictions=[],
        chains=[chain],
        special_records=[],
    )

    assert report.scorable is False
    assert report.score_gate_passed is False
    assert report.human_review_required is True


def test_quality_gate_marks_special_record_without_source_for_review():
    group_id = "gene=BRCA1|variant=c.5266dupC"
    record = SpecialEvidenceRecord(
        record_type="functional",
        description="Assay evidence",
        group_id=group_id,
        source=None,
        raw_source=SourceLocation(block_index=1, context_type="figure", context_ref="Figure 1", text_snippet="assay evidence"),
    )

    report = QualityValidator(required_field_ids=set()).validate(
        items=[],
        contradictions=[],
        chains=[],
        special_records=[record],
    )

    assert report.human_review_required is True
    assert report.human_review_by_category["source_grounding"]


def test_quality_gate_keeps_scorable_when_non_full_chain_group_has_ocr_gap():
    full = "gene=BRCA1|variant=c.5266dupC"
    other = "gene=GLA|variant=__missing__"
    items = [
        _found("A.gene_symbol", full),
        _found("A.gene_symbol", other).model_copy(update={"status": EvidenceStatus.OCR_GAP, "source": None}),
    ]
    chains = [
        EvidenceChain(chain_id=full, chain_level="full"),
        EvidenceChain(chain_id=other, chain_level="singleton"),
    ]

    report = QualityValidator(required_field_ids=set()).validate(
        items=items,
        contradictions=[],
        chains=chains,
        special_records=[],
    )

    assert report.scorable is True
    assert report.score_gate_passed is True
    assert report.human_review_required is True
