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
    assert report.scored_events == 31
    assert summary.both_hero == 0
    assert summary.evidence_increment_events == 20
    assert summary.evidence_increment_without_rett_007 == 16
    assert summary.unique_alleles_with_added_codes == 11
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


def test_russian_body_adds_pm1_pp4_when_english_omits_hgvs() -> None:
    """rett_069 English abstract lacks HGVS; native Cyrillic c.468C>G grants PP4+PM1."""
    report = score_allele_class_increment()
    row = next(item for item in report.rows if item.event_id == "rett_069_D156E")
    assert row.english_classification == "not_scorable"
    assert row.english_codes == ()
    assert row.native_codes == ("PP4", "PM1")
    assert row.added_codes == ("PP4", "PM1")
    assert row.native_classification == "insufficient"
    assert row.native_language == "ru"
    assert row.lane == "en_added_evidence"


def test_russian_english_abstract_already_grants_the_same_codes() -> None:
    """rett_071 English abstract already names c.468C>G; native text adds no criterion."""
    report = score_allele_class_increment()
    row = next(item for item in report.rows if item.event_id == "rett_071_D156E")
    assert row.added_codes == ()
    assert row.english_codes == ("PP4", "PM1")
    assert row.native_codes == ("PP4", "PM1")
    assert row.native_language == "ru"
    assert row.lane == "none"


def test_maternal_t170m_adds_pp4_and_blocks_pm6() -> None:
    """rett_081 is the anti-example: mother heterozygous, so PM6 is not granted."""
    report = score_allele_class_increment()
    row = next(item for item in report.rows if item.event_id == "rett_081_T170M_maternal")
    assert "PM6" not in row.native_codes
    assert row.native_codes == ("PP4",)
    assert row.added_codes == ("PP4",)
    assert row.native_classification == "blocked_conflict"
    assert row.class_increment is False


def test_q208x_without_parents_adds_pvs1_pp4_and_stays_insufficient() -> None:
    """rett_079 truncating allele has no parental testing, so PVS1+PP4 is still insufficient."""
    report = score_allele_class_increment()
    row = next(item for item in report.rows if item.event_id == "rett_079_Q208X")
    assert row.english_classification == "not_scorable"
    assert row.native_codes == ("PVS1", "PP4")
    assert row.added_codes == ("PVS1", "PP4")
    assert row.native_classification == "insufficient"
    assert "PM6" not in row.native_codes


def test_korean_figure_legend_already_grants_the_same_codes() -> None:
    """rett_066 English Fig. 1 already supports PM6; native wording adds no criterion."""
    report = score_allele_class_increment()
    row = next(item for item in report.rows if item.event_id == "rett_066_P152R")
    assert row.added_codes == ()
    assert row.english_classification == "insufficient"
    assert row.native_classification == "insufficient"
    assert row.lane == "none"


def test_turkish_body_adds_pm1_pp4_when_english_omits_hgvs() -> None:
    """rett_078 English abstract lacks HGVS; native p.Pro302Leu grants PP4+PM1."""
    report = score_allele_class_increment()
    row = next(item for item in report.rows if item.event_id == "rett_078_P302L")
    assert row.english_classification == "not_scorable"
    assert row.english_codes == ()
    assert row.native_codes == ("PP4", "PM1")
    assert row.added_codes == ("PP4", "PM1")
    assert row.native_classification == "insufficient"
    assert row.native_language == "tr"
    assert row.lane == "en_added_evidence"


def test_chinese_d156e_adds_pm6_on_the_russian_allele() -> None:
    """rett_085 family sequencing supplies PM6 that Russian rett_069 lacked."""
    report = score_allele_class_increment()
    row = next(item for item in report.rows if item.event_id == "rett_085_D156E")
    assert row.english_classification == "not_scorable"
    assert row.native_codes == ("PM6", "PP4", "PM1")
    assert row.added_codes == ("PM6", "PP4", "PM1")
    assert row.native_classification == "insufficient"
    assert "PM6" not in next(
        item.native_codes for item in report.rows if item.event_id == "rett_069_D156E"
    )


def test_spanish_english_abstract_already_grants_pvs1_pp4() -> None:
    """rett_035 English abstract names c.806del; native de novo does not grant PM6."""
    report = score_allele_class_increment()
    row = next(item for item in report.rows if item.event_id == "rett_035_G269fs")
    assert row.added_codes == ()
    assert row.english_codes == ("PVS1", "PP4")
    assert row.native_codes == ("PVS1", "PP4")
    assert row.native_language == "es"
    assert "PM6" not in row.native_codes
    assert row.lane == "none"


def test_french_poster_adds_codes_without_english_pivot() -> None:
    """rett_041 has no English abstract; native hotspots grant PP4+PM1 or PVS1+PP4."""
    report = score_allele_class_increment()
    r106w = next(item for item in report.rows if item.event_id == "rett_041_R106W")
    r168x = next(item for item in report.rows if item.event_id == "rett_041_R168X")
    r255x = next(item for item in report.rows if item.event_id == "rett_041_R255X")
    assert r106w.english_classification == "not_scorable"
    assert r106w.native_codes == ("PP4", "PM1")
    assert r106w.added_codes == ("PP4", "PM1")
    assert r106w.native_language == "fr"
    assert r168x.native_codes == ("PVS1", "PP4")
    assert r255x.native_codes == ("PVS1", "PP4")
    assert "PM6" not in r168x.native_codes
    assert r168x.native_classification == "insufficient"


def test_korean_cohort_table_adds_codes_when_english_omits_hgvs() -> None:
    """rett_067 English abstract omits per-allele HGVS; Table 2 grants extra criteria."""
    report = score_allele_class_increment()
    d156e = next(item for item in report.rows if item.event_id == "rett_067_D156E")
    r168x = next(item for item in report.rows if item.event_id == "rett_067_R168X")
    t158m = next(item for item in report.rows if item.event_id == "rett_067_T158M")
    assert d156e.english_classification == "not_scorable"
    assert d156e.native_codes == ("PP4", "PM1")
    assert d156e.native_language == "ko"
    assert r168x.native_codes == ("PVS1", "PP4")
    assert t158m.native_codes == ("PP4", "PM1")
    assert t158m.native_classification == "insufficient"


def test_japanese_cohort_table_adds_codes_when_english_omits_hgvs() -> None:
    """rett_088 English abstract names protein hotspots; Table 2 still adds criteria."""
    report = score_allele_class_increment()
    d156e = next(item for item in report.rows if item.event_id == "rett_088_D156E")
    r168x = next(item for item in report.rows if item.event_id == "rett_088_R168X")
    t158m = next(item for item in report.rows if item.event_id == "rett_088_T158M")
    assert d156e.english_classification == "not_scorable"
    assert d156e.native_codes == ("PP4", "PM1")
    assert d156e.added_codes == ("PP4", "PM1")
    assert d156e.native_language == "ja"
    assert r168x.native_codes == ("PVS1", "PP4")
    assert t158m.native_codes == ("PP4", "PM1")
    assert "PM6" not in d156e.native_codes
    assert t158m.native_classification == "insufficient"


def test_portuguese_english_abstract_already_grants_pvs1_pp4() -> None:
    """rett_034 English abstract names c.763C>T; family history is not genotyping."""
    report = score_allele_class_increment()
    row = next(item for item in report.rows if item.event_id == "rett_034_R255X")
    assert row.added_codes == ()
    assert row.english_codes == ("PVS1", "PP4")
    assert row.native_codes == ("PVS1", "PP4")
    assert row.native_language == "pt"
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
