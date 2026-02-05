import pytest

from src.domain.models.parsing_task import (
    normalize_stage_label,
    TaskStage,
)


@pytest.mark.parametrize(
    ("label", "expected_stage"),
    [
        ("Validation", TaskStage.INGESTION),
        ("Document Validation", TaskStage.INGESTION),
        ("PDF Parsing", TaskStage.LAYOUT),
        ("Evidence Extraction", TaskStage.EVIDENCE),
        ("Finalizing", TaskStage.ARBITRATION),
        ("Completed", TaskStage.COMPLETED),
        ("Failed", TaskStage.COMPLETED),
    ],
)
def test_normalize_stage_label_aliases(label, expected_stage):
    assert normalize_stage_label(label) == expected_stage


def test_normalize_stage_label_defaults_to_ingestion():
    assert normalize_stage_label("unmapped") == TaskStage.INGESTION
    assert normalize_stage_label(None) == TaskStage.INGESTION
