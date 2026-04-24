from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.domain.enums import ProcessingState
from src.domain.models import (
    DocumentParsingResult,
    EvidenceOutput,
    ExtractedEvidenceFields,
    PipelineResult,
)
from src.services.enum import PROCESSING_STEP_ORDER

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_json_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text())


def _json_value(value: Any) -> Any:
    return getattr(value, "value", value)


def validate_evidence_output_equivalence(
    actual: dict[str, Any],
    expected: dict[str, Any],
    *,
    ignore_fields: set[str] | None = None,
) -> list[str]:
    ignore = ignore_fields or set()
    differences: list[str] = []

    def kind(value: Any) -> str:
        if isinstance(value, dict):
            return "object"
        if isinstance(value, list):
            return "array"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)):
            return "number"
        if isinstance(value, str):
            return "string"
        if value is None:
            return "null"
        return type(value).__name__

    def walk(actual_value: Any, expected_value: Any, path: str) -> None:
        if path and path in ignore:
            return

        if isinstance(actual_value, dict) and isinstance(expected_value, dict):
            all_keys = sorted(set(actual_value) | set(expected_value))
            for key in all_keys:
                next_path = f"{path}.{key}" if path else key
                if next_path in ignore:
                    continue
                if key not in actual_value:
                    differences.append(f"Missing in actual: {next_path}")
                    continue
                if key not in expected_value:
                    differences.append(f"Extra in actual: {next_path}")
                    continue
                walk(actual_value[key], expected_value[key], next_path)
            return

        if isinstance(actual_value, list) and isinstance(expected_value, list):
            if not expected_value:
                if actual_value:
                    differences.append(
                        f"Expected empty array at {path or '<root>'}, got {len(actual_value)!r} item(s)"
                    )
                return
            if not actual_value:
                differences.append(f"Expected array items at {path or '<root>'}, got empty array")
                return
            exemplar = expected_value[0]
            for index, actual_item in enumerate(actual_value):
                walk(actual_item, exemplar, f"{path}[{index}]")
            return

        if kind(actual_value) != kind(expected_value):
            differences.append(
                f"Type mismatch at {path or '<root>'}: {kind(actual_value)!r} != {kind(expected_value)!r}"
            )

    walk(actual, expected, "")
    return differences


class TestGoldenFixtures:
    def test_fixture_inventory(self) -> None:
        fixture_names = sorted(path.name for path in FIXTURES_DIR.glob("golden_*.json"))
        assert fixture_names == [
            "golden_evidence_output.json",
            "golden_parsing_result.json",
            "golden_pipeline_result.json",
            "golden_processing_state.json",
        ]

    def test_evidence_output_validates(self) -> None:
        data = _load_json_fixture("golden_evidence_output.json")

        result = EvidenceOutput.model_validate(data)

        assert result.ps3_evidence["overall_assessment"]["total_score"] == pytest.approx(88.0)
        assert _json_value(result.final_evidence_strength) == "PS3"
        assert result.arbitration_confidence == pytest.approx(0.91)
        assert result.extracted_fields is not None
        structured_fields = ExtractedEvidenceFields.model_validate(result.extracted_fields)
        assert structured_fields.compute_overall_confidence() == pytest.approx(92.0)
        assert result.overall_confidence == pytest.approx(92.0)
        assert _json_value(result.evidence_classification) == "Pathogenic"
        assert [_json_value(level) for level in (result.acmg_evidence_levels or [])] == ["PS3"]
        assert result.evidence_sources == ["Figure 1", "Table 2"]
        assert validate_evidence_output_equivalence(result.model_dump(mode="json"), data) == []

    def test_processing_state_structure(self) -> None:
        data = _load_json_fixture("golden_processing_state.json")

        required_keys = set(getattr(ProcessingState, "__required_keys__", set()))
        assert required_keys.issubset(data)
        assert data["status"] == "approved"
        assert data["needs_manual_review"] is False
        assert data["document_id"] == "doc-golden-001"
        assert data["paper_task_id"] == "paper-golden-001"
        assert data["request_id"] == "request-golden-001"
        assert set(data["processing_steps"]) == set(PROCESSING_STEP_ORDER)
        assert "reasoning" not in data["processing_steps"]
        assert data["processing_steps"]["acquisition"]["status"] == "SKIPPED"
        assert data["processing_steps"]["adjudication"]["status"] == "COMPLETED"
        assert data["node_trace"]["translation"] == "skipped_english"
        assert data["node_trace"]["acmg"] == "success"

    def test_equivalence_helper_ignores_value_changes(self) -> None:
        expected = _load_json_fixture("golden_evidence_output.json")
        actual = _load_json_fixture("golden_evidence_output.json")
        actual["overall_confidence"] = 12.5
        actual["ps3_evidence"]["overall_assessment"]["total_score"] = 42.0
        actual["image_descriptions"] = ["Different descriptive text"]

        assert validate_evidence_output_equivalence(actual, expected) == []

    def test_equivalence_helper_reports_missing_fields(self) -> None:
        expected = _load_json_fixture("golden_evidence_output.json")
        actual = _load_json_fixture("golden_evidence_output.json")
        del actual["overall_confidence"]

        differences = validate_evidence_output_equivalence(actual, expected)

        assert any("overall_confidence" in difference for difference in differences)

    def test_pipeline_result_validates(self) -> None:
        data = _load_json_fixture("golden_pipeline_result.json")

        result = PipelineResult.model_validate(data)

        assert result.document_id == "doc-golden-001"
        assert result.output_dir.endswith("/doc-golden-001")
        assert result.files.image_dir.endswith("/images")
        assert result.evidence is not None
        assert _json_value(result.evidence.final_evidence_strength) == "PS3"
        assert result.warning_codes == ["HGVS_AUTOCORRECT_FAILED"]
        assert result.alignment_count == 2
        assert (
            validate_evidence_output_equivalence(
                result.evidence.model_dump(mode="json"),
                _load_json_fixture("golden_evidence_output.json"),
            )
            == []
        )

    def test_parsing_result_validates(self) -> None:
        data = _load_json_fixture("golden_parsing_result.json")

        result = DocumentParsingResult.model_validate(data)

        assert result.parser_backend == "mineru"
        assert result.image_count == 2
        assert len(result.image_paths) == 2
        assert result.artifacts is not None
        assert len(result.artifacts.image_object_keys) == 2
        assert result.artifacts.markdown_object_key is not None
        assert result.artifacts.markdown_object_key.endswith("parsed_markdown.md")
