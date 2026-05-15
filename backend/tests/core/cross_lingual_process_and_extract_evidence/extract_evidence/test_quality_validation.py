from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import QualityValidator


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
