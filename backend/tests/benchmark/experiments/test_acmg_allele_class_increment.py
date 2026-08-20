"""Tests for extra ACMG criterion evidence versus English-visible facts and ClinVar."""

from __future__ import annotations

from pathlib import Path

from benchmark.experiments.acmg_multilingual.allele_class_increment import (
    score_allele_class_increment,
    summarize_allele_class_increment,
)
from benchmark.experiments.acmg_multilingual.cli import _parse_args


def test_frozen_join_counts_added_codes_not_only_class_flips() -> None:
    """Native text can add PM6 without flipping Pathogenic; both-hero stays empty."""
    report = score_allele_class_increment()
    summary = summarize_allele_class_increment(report)
    assert report.scored_events == 14
    assert summary.both_hero == 0
    assert summary.evidence_increment_events == 6
    assert summary.evidence_increment_without_rett_007 == 2
    assert summary.unique_alleles_with_added_codes == 5
    assert {row.event_id for row in report.rows if row.lane == "clinvar_gap"} == {
        "rett_006_G_913insT",
        "rett_084_194delC",
    }
    assert {
        row.event_id
        for row in report.rows
        if row.added_codes and row.native_classification == "pathogenic"
    } == {
        "rett_007_case2_R180X",
        "rett_007_case3_G281fs",
        "rett_007_case4_R282fs",
        "rett_004_R168X",
    }
    assert summary.unique_en_missing_pathogenic_alleles == 3
    assert summary.clinvar_gap_pathogenic == 2
    assert summary.en_missing_to_pathogenic == 4


def test_rett_011_adds_pm6_without_class_flip() -> None:
    """Chinese parental negativity is extra ACMG evidence even if class stays insufficient."""
    report = score_allele_class_increment()
    rett_011 = next(row for row in report.rows if row.event_id == "rett_011_P237R")
    assert rett_011.english_codes == ("PP4",)
    assert rett_011.native_codes == ("PM6", "PP4")
    assert rett_011.added_codes == ("PM6",)
    assert rett_011.english_classification == "insufficient"
    assert rett_011.native_classification == "insufficient"
    assert rett_011.class_increment is False
    assert rett_011.lane == "en_added_evidence"


def test_korean_figure_legend_already_grants_the_same_codes() -> None:
    """rett_066 English Fig. 1 already supports PM6; native wording adds no criterion."""
    report = score_allele_class_increment()
    row = next(item for item in report.rows if item.event_id == "rett_066_P152R")
    assert row.added_codes == ()
    assert row.english_classification == "insufficient"
    assert row.native_classification == "insufficient"
    assert row.lane == "none"


def test_cli_check_allele_class_increment_parses() -> None:
    """The allele-class CLI keeps inference cases and field coverage separate."""
    args = _parse_args(
        (
            "check-allele-class-increment",
            "--cases",
            "cases.json",
            "--facts",
            "facts.json",
        )
    )
    assert args.cases == Path("cases.json")
    assert args.facts == Path("facts.json")
