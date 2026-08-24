"""Tests for the frozen MECP2/Rett direct-inference protocol."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from benchmark.experiments.acmg_multilingual.cli import _parse_args
from benchmark.experiments.acmg_multilingual.direct_inference import (
    DirectInferenceEvent,
    Mecp2VcepSlice,
    infer_event,
    infer_table,
    load_direct_inference_table,
    summarize_direct_inference,
    verify_direct_inference,
)


def _repository_root() -> Path:
    """Return the monorepo root that contains benchmark/ and backend/."""
    return Path(__file__).resolve().parents[4]


def _event(**overrides: object) -> DirectInferenceEvent:
    """Build one latent event; callers override the fields under test."""
    payload: dict[str, object] = {
        "event_id": "synthetic",
        "case_id": "synthetic",
        "source_cluster_id": "synthetic",
        "paper_hgvs_c": "c.502C>T",
        "canonical_allele_id": "synthetic_allele",
        "vcep_protein_position": 168,
        "vcep_protein_change": "p.Arg168Ter",
        "variant_class": "nonsense",
        "clinvar_match": "unmatched",
        "affected_proband": True,
        "sex": "female",
        "zygosity": "heterozygous",
        "both_parents_tested": True,
        "parents_negative_at_target": True,
        "parentage_confirmed": False,
        "inheritance": "de_novo_unconfirmed",
        "phenotype_class": "rett_diagnosed",
        "visibility": "native_body_only",
        "materialization_status": "needs_external_corpus",
        "source_root_kind": "external_rett",
        "expected_codes": ("PM6", "PVS1", "PP4"),
        "expected_classification": "pathogenic",
    }
    payload.update(overrides)
    return DirectInferenceEvent.model_validate(payload)


def test_frozen_table_matches_engine_and_on_disk_sources() -> None:
    """The committed table is self-consistent and matches reviewed source.md hashes."""
    repository_root = _repository_root()
    table = load_direct_inference_table()
    summary = summarize_direct_inference(table)
    report = verify_direct_inference(
        table,
        reviewed_root=repository_root / "benchmark/experiments/acmg_multilingual/reviewed",
    )
    assert report.engine_mismatches == 0
    assert report.verified_on_disk_events == report.on_disk_events == 31
    assert summary.total_events == 32
    assert summary.bilingual_increment == 13
    assert summary.bilingual_increment_without_rett_007 == 9
    assert summary.pathogenic == 8
    assert summary.unique_pathogenic_alleles == 6
    assert summary.pathogenic_clinvar_gap == 2
    assert summary.blocked_conflict == 2
    assert summary.excluded == 2


def test_truncating_with_parents_and_rett_is_pathogenic() -> None:
    """PVS1 + PM6 + PP4 is Pathogenic under the frozen Rett combining slice."""
    vcep = Mecp2VcepSlice()
    result = infer_event(_event(), vcep)
    assert result.granted_codes == ("PM6", "PVS1", "PP4")
    assert result.classification == "pathogenic"
    assert "PS2" in result.refused_codes


def test_truncating_without_pp4_is_likely_pathogenic() -> None:
    """One Very Strong plus one Moderate is LP, not Pathogenic, until a Supporting code is added."""
    result = infer_event(_event(phenotype_class="other", expected_codes=("PM6", "PVS1")), Mecp2VcepSlice())
    assert result.granted_codes == ("PM6", "PVS1")
    assert result.classification == "likely_pathogenic"


def test_never_grants_ps2_or_author_self_codes() -> None:
    """Parentage-unconfirmed de novo stays PM6; paper PS2+PM2+PP3 is refused."""
    result = infer_event(
        _event(
            variant_class="missense",
            vcep_protein_position=225,
            author_self_codes=("PS2", "PM2", "PP3"),
            expected_codes=("PM6", "PP4"),
            expected_classification="insufficient",
        ),
        Mecp2VcepSlice(),
    )
    assert "PS2" not in result.granted_codes
    assert "PM2" not in result.granted_codes
    assert "PP3" not in result.granted_codes
    assert result.refused_codes == ("PS2", "author_self_code", "PM2", "PP3")
    assert result.classification == "insufficient"


def test_p376s_conflict_blocks_classification() -> None:
    """ClinVar expert-panel Benign blocks pathogenic inference even if PM6 facts exist."""
    result = infer_event(
        _event(
            variant_class="missense",
            vcep_protein_position=376,
            conflict_flags=("clinvar_benign_expert_panel",),
            expected_codes=("PM6", "PP4"),
            expected_classification="blocked_conflict",
        ),
        Mecp2VcepSlice(),
    )
    assert result.granted_codes == ("PM6", "PP4")
    assert result.classification == "blocked_conflict"


def test_maternal_inheritance_does_not_grant_pm6() -> None:
    """The same T170M nucleotide can be maternal; that fact blocks de novo inference."""
    result = infer_event(
        _event(
            variant_class="missense",
            vcep_protein_position=170,
            parents_negative_at_target=False,
            inheritance="maternal",
            conflict_flags=("maternal_inheritance",),
            expected_codes=("PP4",),
            expected_classification="blocked_conflict",
        ),
        Mecp2VcepSlice(),
    )
    assert "PM6" not in result.granted_codes
    assert result.classification == "blocked_conflict"


def test_mbd_missense_stays_insufficient_without_second_supporting() -> None:
    """PM1+PM6+PP4 is 2 Moderate + 1 Supporting, below the LP 2-Moderate+2-Supporting bar."""
    result = infer_event(
        _event(
            variant_class="missense",
            vcep_protein_position=106,
            expected_codes=("PM6", "PP4", "PM1"),
            expected_classification="insufficient",
        ),
        Mecp2VcepSlice(),
    )
    assert result.granted_codes == ("PM6", "PP4", "PM1")
    assert result.classification == "insufficient"


def test_distal_truncating_is_pvs1_moderate_not_very_strong() -> None:
    """A stop after p.E472 is Moderate LoF; with PM6+PP4 that is still not Pathogenic."""
    result = infer_event(
        _event(
            vcep_protein_position=480,
            expected_codes=("PM6", "PVS1_Moderate", "PP4"),
            expected_classification="insufficient",
        ),
        Mecp2VcepSlice(),
    )
    assert result.granted_codes == ("PM6", "PVS1_Moderate", "PP4")
    assert result.classification == "insufficient"


def test_r168x_aliases_collapse_to_one_allele() -> None:
    """c.502C>T and c.538C>T are one ClinVar allele counted once among Pathogenic events."""
    table = load_direct_inference_table()
    results = infer_table(table)
    pathogenic_r168x = [
        result
        for result in results
        if result.classification == "pathogenic" and result.canonical_allele_id == "VCV000011828"
    ]
    assert len(pathogenic_r168x) == 3
    summary = summarize_direct_inference(table, results)
    assert summary.unique_pathogenic_alleles == 6


def test_c844delc_maps_to_vcv143702_not_nonsense() -> None:
    """The 2026-08-18 correction: frameshift c.844del is VCV143702, not c.844C>T VCV11815."""
    table = load_direct_inference_table()
    event = next(item for item in table.events if item.event_id == "rett_007_case4_R282fs")
    assert event.clinvar_vcv == "VCV000143702"
    assert event.canonical_allele_id == "VCV000143702"
    nonsense = next(item for item in table.events if item.event_id == "rett_006_D_R270X")
    assert nonsense.clinvar_vcv == "VCV000011815"
    assert event.canonical_allele_id != nonsense.canonical_allele_id


def test_on_disk_event_rejects_missing_hash() -> None:
    """On-disk rows cannot pose as content-addressed without a SHA-256 digest."""
    with pytest.raises(ValidationError, match="SHA-256"):
        _event(
            materialization_status="on_disk",
            source_root_kind="reviewed",
            source_relative_path="rett_007/source.md",
            source_sha256="",
            spans=({"line": 51, "quote": "患儿父母均未检测到突变", "language": "zh"},),
        )


def test_cli_check_direct_inference_parses_roots() -> None:
    """The direct-inference CLI keeps the case table and reviewed root separate."""
    args = _parse_args(
        (
            "check-direct-inference",
            "--cases",
            "cases.json",
            "--reviewed-root",
            "reviewed",
            "--report",
            "report.json",
        )
    )
    assert args.cases == Path("cases.json")
    assert args.reviewed_root == Path("reviewed")
    assert args.report == Path("report.json")
