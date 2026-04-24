import importlib.util
import json
from pathlib import Path
from typing import Callable

from src.domain.evidence.gold_standard_converter import convert_gold_standard_payload
from src.domain.models import EvidenceOutput, ExtractedEvidenceFields


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
BACKEND_DIR = Path(__file__).resolve().parents[2]


def _load_convert_file() -> Callable[[Path, Path, str | None], int]:
    try:
        from apps.backend.scripts.convert_gold_standard_json import convert_file
    except ModuleNotFoundError:
        script_path = BACKEND_DIR / "scripts" / "convert_gold_standard_json.py"
        spec = importlib.util.spec_from_file_location("convert_gold_standard_json", script_path)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.convert_file
    else:
        return convert_file


def _load_gold_standard_payload() -> dict:
    fixture_path = FIXTURES_DIR / "gold_standard_source_minimal.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_convert_gold_standard_file_writes_evidence_json(tmp_path: Path) -> None:
    source = FIXTURES_DIR / "gold_standard_source_minimal.json"
    target = tmp_path / "14749723.evidence.json"
    convert_file = _load_convert_file()

    count = convert_file(source, target, source_id="14749723")

    assert count == 1
    data = json.loads(target.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) == 1
    EvidenceOutput.model_validate(data[0])


def test_convert_gold_standard_payload_emits_valid_evidence_output() -> None:
    payload = _load_gold_standard_payload()

    records = convert_gold_standard_payload(payload, source_id="14749723")

    assert len(records) == 1
    output = EvidenceOutput.model_validate(records[0])
    fields = ExtractedEvidenceFields.model_validate(output.extracted_fields)

    assert output.status == "success"
    assert output.evidence_sources == ["PMID:14749723"]
    assert output.final_evidence_strength == "PS3"
    assert output.acmg_evidence_levels == ["PS3"]
    assert output.evidence_classification == "Pathogenic"

    assert fields.gene is not None
    assert fields.gene.symbol == "PRKN"
    assert fields.transcript_id is not None
    assert fields.transcript_id.transcript_id == "NM_004562.3"
    assert fields.variant is not None
    assert fields.variant.hgvs_c == "NM_004562.3:c.1252T>C"
    assert fields.variant.hgvs_p == "p.Cys418Arg"
    assert fields.variant.ref_allele == "T"
    assert fields.variant.alt_allele == "C"
    assert fields.experiment_data is not None
    assert fields.experiment_data.assay_type == "Caspase-3 activity measurements"
    assert fields.experiment_data.cell_line == "TSM1 neurons, SH-SY5Y cells"
    assert fields.negative_positive_control is not None
    assert fields.negative_positive_control.has_positive_control is True
    assert fields.negative_positive_control.has_negative_control is False


def test_convert_gold_standard_payload_populates_ps3_scoring() -> None:
    payload = _load_gold_standard_payload()

    records = convert_gold_standard_payload(payload, source_id="14749723")
    output = EvidenceOutput.model_validate(records[0])
    ps3_evidence = output.ps3_evidence

    assert ps3_evidence["ps3_step_1"]["score"] == 20
    assert ps3_evidence["ps3_step_2"]["score"] == 20
    assert ps3_evidence["ps3_step_3"]["score"] == 15
    assert ps3_evidence["ps3_step_4"]["score"] == 20
    assert ps3_evidence["overall_assessment"]["total_score"] == 75

    checkpoint_3a = ps3_evidence["ps3_step_3"]["checkpoint_3a"]
    assert checkpoint_3a["replicates_used"] is True
    assert checkpoint_3a["positive_control_present"] is True
    assert checkpoint_3a["negative_control_present"] is False

    assert ps3_evidence["ps3_step_4"]["oddspath_data"]["computable"] is False
    assert ps3_evidence["functional_evidence_aim"] == "pathogenic"


def test_convert_gold_standard_payload_matches_parenthetical_variant_suffix() -> None:
    payload = {
        "Variants Include": [
            {
                "Gene": "DJ-1",
                "variants": [
                    {
                        "HGVS": "NM_007262.5:c.497T>C",
                        "cDNA Change": {
                            "transcript": "NM_007262.5",
                            "ref": "T",
                            "alt": "C",
                            "position": "497",
                        },
                        "Protein Change": {"ref": "L", "alt": "P", "position": "166"},
                        "Description in input context": "L166P",
                    }
                ],
            }
        ],
        "Described Disease": {"Described Disease": "Parkinson's disease"},
        "Experiment Method": [
            {
                "Assay Method": "Flow Cytometry",
                "Material used": {
                    "Material Source": "Cell line",
                    "Material Name": "DJ-1 expressing cells",
                    "Description": "Cells were measured by flow cytometry.",
                },
                "Readout type": "Quantitative",
                "Readout description": [
                    {
                        "Variant": "NM_007262.5:c.497T>C (L166P)",
                        "Conclusion": "Abnormal",
                        "Molecular Effect": "loss of function",
                        "Result Description": "Reduced DJ-1 expression was observed.",
                    }
                ],
                "Biological replicates": {"Biological replicates": "Yes"},
                "Technical replicates": {"Technical replicates": "N.D."},
                "Basic positive control": {
                    "Basic positive control": "Yes",
                    "Description": "Wild-type DJ-1 expressing cells.",
                },
                "Basic negative control": {
                    "Basic negative control": "Yes",
                    "Description": {
                        "Control vector-transfected cells": "Negative control for DJ-1 expression."
                    },
                },
                "Approved assay": {"Approved assay": "Yes"},
            }
        ],
    }

    records = convert_gold_standard_payload(payload, source_id="19801972")
    output = EvidenceOutput.model_validate(records[0])
    fields = ExtractedEvidenceFields.model_validate(output.extracted_fields)

    assert fields.variant is not None
    assert fields.variant.hgvs_c == "NM_007262.5:c.497T>C"
    assert fields.variant.hgvs_p == "p.Leu166Pro"
    assert fields.negative_positive_control is not None
    assert fields.negative_positive_control.has_negative_control is True
    assert (
        fields.negative_positive_control.negative_control_description
        == "Control vector-transfected cells: Negative control for DJ-1 expression."
    )


def test_convert_gold_standard_payload_emits_partial_variant_when_missing_from_variant_list() -> None:
    payload = _load_gold_standard_payload()
    payload["Experiment Method"][0]["Readout description"][0]["Variant"] = "NM_007262.5:c.155G>C (C53A)"

    records = convert_gold_standard_payload(payload, source_id="19801972")
    output = EvidenceOutput.model_validate(records[0])
    fields = ExtractedEvidenceFields.model_validate(output.extracted_fields)

    assert fields.variant is not None
    assert fields.variant.hgvs_c == "NM_007262.5:c.155G>C"
    assert fields.transcript_id is not None
    assert fields.transcript_id.transcript_id == "NM_007262.5"
    assert fields.variant.hgvs_p is None
