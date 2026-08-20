"""Tests for live extraction-probe classification. No live LLM calls."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from benchmark.experiments.acmg_multilingual.cli import _parse_args
from benchmark.experiments.acmg_multilingual.direct_inference import (
    DirectInferenceEvent,
    DirectInferenceTable,
    load_direct_inference_table,
)
from benchmark.experiments.acmg_multilingual.field_bridge import (
    FieldBridgeEvent,
    FieldFact,
    load_field_bridge_table,
)
from benchmark.experiments.acmg_multilingual.live_extraction_probe import (
    FieldOrigin,
    build_probe_document,
    classify_field_origin,
    compare_live_gates_to_engine,
    found_field_values,
    gate_matches_gold,
    observe_gates,
    on_disk_probe_event_ids,
)


def test_cli_probe_extraction_parses_event_ids() -> None:
    """The live probe CLI keeps cases, facts, sources, and event ids separate."""
    args = _parse_args(
        (
            "probe-extraction",
            "--cases",
            "cases.json",
            "--facts",
            "facts.json",
            "--reviewed-root",
            "reviewed",
            "--report",
            "report.json",
            "--event-id",
            "rett_007_case2_R180X",
            "--event-id",
            "rett_011_P237R",
        )
    )
    assert args.cases == Path("cases.json")
    assert args.facts == Path("facts.json")
    assert args.reviewed_root == Path("reviewed")
    assert args.report == Path("report.json")
    assert args.event_ids == ["rett_007_case2_R180X", "rett_011_P237R"]
    assert args.all_on_disk is False


def test_cli_probe_extraction_parses_all_on_disk() -> None:
    """--all-on-disk is a separate switch from repeating --event-id."""
    args = _parse_args(
        (
            "probe-extraction",
            "--cases",
            "cases.json",
            "--facts",
            "facts.json",
            "--reviewed-root",
            "reviewed",
            "--report",
            "report.json",
            "--all-on-disk",
        )
    )
    assert args.all_on_disk is True
    assert args.event_ids is None


def test_found_field_values_keeps_first_found() -> None:
    """A later not_found or empty value must not overwrite the first FOUND value."""
    items = (
        SimpleNamespace(field_id="C.de_novo_status", status="found", value="de_novo"),
        SimpleNamespace(field_id="C.de_novo_status", status="found", value="not_de_novo"),
        SimpleNamespace(field_id="C.maternal_genotype", status="not_found", value="target_absent"),
    )
    assert found_field_values(items) == {"C.de_novo_status": "de_novo"}


def test_classify_and_gold_match_recovery_fills_pm6_chain() -> None:
    """Joint parental recovery should count as recovered and match the frozen gates."""
    facts = (
        FieldFact(
            field_id="C.de_novo_status",
            presence="present",
            expected_value="de_novo_unconfirmed",
            spans=(
                {
                    "line": 51,
                    "quote": "患儿父母均未检测到突变",
                    "language": "zh",
                },
            ),
        ),
        FieldFact(
            field_id="C.maternal_genotype",
            presence="present",
            expected_value="target_absent",
            spans=(
                {
                    "line": 51,
                    "quote": "患儿父母均未检测到突变",
                    "language": "zh",
                },
            ),
        ),
        FieldFact(
            field_id="C.parentage_confirmed",
            presence="absent",
        ),
    )
    observations = observe_gates(
        facts,
        llm_values={"C.de_novo_status": "de_novo"},
        final_values={
            "C.de_novo_status": "de_novo",
            "C.maternal_genotype": "target_absent",
            "C.parentage_confirmed": "not_confirmed",
        },
    )
    by_id = {item.field_id: item for item in observations}
    assert by_id["C.de_novo_status"].origin is FieldOrigin.LLM
    assert by_id["C.de_novo_status"].matches_gold is True
    assert by_id["C.maternal_genotype"].origin is FieldOrigin.RECOVERED
    assert by_id["C.maternal_genotype"].matches_gold is True
    assert by_id["C.parentage_confirmed"].origin is FieldOrigin.RECOVERED
    assert by_id["C.parentage_confirmed"].matches_gold is True


def test_normalized_parentage_and_hgvs_alias_match() -> None:
    """Normalizer corrections and HTML HGVS aliases still count as gold matches."""
    assert classify_field_origin("confirmed", "not_confirmed") is FieldOrigin.NORMALIZED
    assert gate_matches_gold(
        FieldFact(
            field_id="A.variant_hgvs_c",
            presence="present",
            expected_value="c.538C>T",
            spans=({"line": 55, "quote": "c.538C&gt;T", "language": "zh"},),
        ),
        "NM_001110792.2:c.538C&gt;T",
    )
    assert gate_matches_gold(
        FieldFact(field_id="C.parentage_confirmed", presence="absent"),
        "confirmed",
    ) is False


def _case2_and_bridge() -> tuple[DirectInferenceTable, DirectInferenceEvent, FieldBridgeEvent]:
    table = load_direct_inference_table()
    bridge = load_field_bridge_table()
    event = next(item for item in table.events if item.event_id == "rett_007_case2_R180X")
    facts = next(item for item in bridge.events if item.event_id == event.event_id)
    return table, event, facts


def test_on_disk_probe_event_ids_are_the_fourteen_reviewed_events() -> None:
    table = load_direct_inference_table()
    assert len(on_disk_probe_event_ids(table)) == 14
    assert "rett_007_case2_R180X" in on_disk_probe_event_ids(table)
    assert "rett_081_T170M_maternal" not in on_disk_probe_event_ids(table)


def test_probe_document_unescapes_markdown_tilde() -> None:
    _, event, _ = _case2_and_bridge()
    document = build_probe_document(event, "病例 1\\~4 诊断为经典型 RTT")
    assert "病例 1~4" in document.formatted_text
    assert "\\~" not in document.formatted_text


def test_live_diagnosis_miss_demotes_pathogenic_to_likely_pathogenic() -> None:
    """Dropping PP4 leaves PVS1+PM6, which the Rett combiner calls likely pathogenic."""
    table, event, facts = _case2_and_bridge()
    values = {
        "A.variant_hgvs_c": "c.538C>T",
        "A.variant_hgvs_p": "p.R180*",
        "A.variant_type": "nonsense",
        "C.de_novo_status": "de_novo",
        "C.maternal_genotype": "target_absent",
        "C.paternal_genotype": "target_absent",
        "C.parentage_confirmed": "not_confirmed",
    }
    gates = observe_gates(facts.fields, values, values)
    comparison = compare_live_gates_to_engine(event, gates, table.vcep)
    assert comparison.frozen_classification == "pathogenic"
    assert comparison.frozen_codes == ("PM6", "PVS1", "PP4")
    assert comparison.live_codes == ("PM6", "PVS1")
    assert comparison.live_classification == "likely_pathogenic"
    assert comparison.classification_changed is True
    assert "B.disease_diagnosis" in comparison.degraded_field_ids


def test_live_matching_gates_keep_frozen_pathogenic() -> None:
    table, event, facts = _case2_and_bridge()
    values = {
        "A.variant_hgvs_c": "c.538C>T",
        "A.variant_hgvs_p": "p.Arg180Ter",
        "A.variant_type": "nonsense",
        "C.de_novo_status": "de_novo",
        "C.maternal_genotype": "target_absent",
        "C.paternal_genotype": "target_absent",
        "C.parentage_confirmed": "not_confirmed",
        "B.disease_diagnosis": "Rett syndrome",
    }
    gates = observe_gates(facts.fields, values, values)
    comparison = compare_live_gates_to_engine(event, gates, table.vcep)
    assert comparison.live_codes == comparison.frozen_codes == ("PM6", "PVS1", "PP4")
    assert comparison.live_classification == "pathogenic"
    assert comparison.classification_changed is False


def test_live_missing_variant_type_drops_pvs1() -> None:
    table, event, facts = _case2_and_bridge()
    values = {
        "A.variant_hgvs_c": "c.538C>T",
        "C.de_novo_status": "de_novo",
        "C.maternal_genotype": "target_absent",
        "C.paternal_genotype": "target_absent",
        "C.parentage_confirmed": "not_confirmed",
        "B.disease_diagnosis": "Rett syndrome",
    }
    gates = observe_gates(facts.fields, values, values)
    comparison = compare_live_gates_to_engine(event, gates, table.vcep)
    assert "PVS1" not in comparison.live_codes
    assert "PM6" in comparison.live_codes
    assert "PP4" in comparison.live_codes
