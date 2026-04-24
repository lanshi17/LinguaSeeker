import json
from pathlib import Path

from src.domain.evidence.gold_standard_converter import convert_gold_standard_payload
from src.domain.models import EvidenceOutput, ExtractedEvidenceFields


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _load_gold_standard_payload() -> dict:
    fixture_path = FIXTURES_DIR / "gold_standard_source_minimal.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


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
