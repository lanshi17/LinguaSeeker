"""Stage-0c: extra ACMG criterion evidence on one allele versus English-visible facts.

The endpoint is the granted criterion set (PM6, PVS1, PP4, PM1), not catalog
field counts and not a required Pathogenic flip. Combining class is reported
as a stronger subset. Product ``assigned_acmg_codes`` stay empty.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .direct_inference import (
    Classification,
    DirectInferenceEvent,
    DirectInferenceResult,
    DirectInferenceTable,
    GrantedCode,
    Mecp2VcepSlice,
    infer_event,
    load_direct_inference_table,
)
from .evidence_item_coverage import (
    EvidenceItemCoverageTable,
    EvidenceItemSource,
    load_evidence_item_coverage_table,
)

EnglishLayerClass = Literal[
    "not_scorable",
    "pathogenic",
    "likely_pathogenic",
    "insufficient",
    "blocked_conflict",
    "excluded",
]
IncrementLane = Literal["both", "en_added_evidence", "clinvar_gap", "none"]

_CLASS_RANK: dict[str, int] = {
    "not_scorable": 0,
    "excluded": 0,
    "insufficient": 1,
    "likely_pathogenic": 2,
    "pathogenic": 3,
    "blocked_conflict": -1,
}
_PATHOGENIC_CLASSES = frozenset({"pathogenic", "likely_pathogenic"})
_CLINVAR_GAP_MATCHES = frozenset({"unmatched", "coordinate_near"})
_PARENT_FIELDS = frozenset(
    {"C.de_novo_status", "C.maternal_genotype", "C.paternal_genotype"}
)


class EnglishLayerScore(BaseModel):
    """Engine output from facts attested only in the English-visible layer."""

    model_config = ConfigDict(frozen=True)

    classification: EnglishLayerClass
    codes: tuple[GrantedCode, ...]


class AlleleClassRow(BaseModel):
    """One on-disk event: English-visible codes versus native codes."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    case_id: str
    source_cluster_id: str
    paper_hgvs_c: str
    canonical_allele_id: str
    native_language: str
    english_classification: EnglishLayerClass
    native_classification: Classification
    english_codes: tuple[GrantedCode, ...]
    native_codes: tuple[GrantedCode, ...]
    added_codes: tuple[GrantedCode, ...]
    class_increment: bool
    clinvar_match: str
    clinvar_gap: bool
    lane: IncrementLane


class AlleleClassIncrementReport(BaseModel):
    """Derived join of field coverage, granted ACMG codes, and ClinVar match."""

    model_config = ConfigDict(frozen=True)

    study_id: str
    scored_events: int
    evidence_increment_events: int
    evidence_increment_without_rett_007: int
    unique_alleles_with_added_codes: int
    class_increment_events: int
    english_not_scorable_to_pathogenic: int
    unique_pathogenic_alleles_en_missing: int
    clinvar_gap_pathogenic: int
    both_hero: int
    rows: tuple[AlleleClassRow, ...]


@dataclass(frozen=True)
class AlleleClassIncrementSummary:
    """CLI-facing counts: extra criterion evidence first, class flip second."""

    scored_events: int
    evidence_increment_events: int
    evidence_increment_without_rett_007: int
    unique_alleles_with_added_codes: int
    both_hero: int
    en_missing_to_pathogenic: int
    clinvar_gap_pathogenic: int
    unique_en_missing_pathogenic_alleles: int


def _visible_field_ids(source: EvidenceItemSource) -> set[str]:
    return {item.field_id for item in source.english_visible}


def _english_layer_score(
    event: DirectInferenceEvent,
    visible_ids: set[str],
    vcep: Mecp2VcepSlice,
) -> EnglishLayerScore:
    """Score the allele using only facts attested in the English-visible layer.

    Allele identity requires ``A.variant_hgvs_c``. Variant class and VCEP residue
    stay on the frozen event: they are properties of that allele, not of language.
    Parental testing and diagnosis are masked unless the English layer has them.
    """
    if "A.variant_hgvs_c" not in visible_ids:
        return EnglishLayerScore(classification="not_scorable", codes=())
    has_parents = bool(visible_ids & _PARENT_FIELDS)
    has_diagnosis = "B.disease_diagnosis" in visible_ids
    updates: dict[str, object] = {}
    if not has_parents:
        updates["both_parents_tested"] = False
        updates["parents_negative_at_target"] = False
        updates["inheritance"] = "unknown"
    if not has_diagnosis:
        updates["phenotype_class"] = "other"
    masked = event.model_copy(update=updates) if updates else event
    result = infer_event(masked, vcep)
    return EnglishLayerScore(
        classification=result.classification,
        codes=result.granted_codes,
    )


def _added_codes(
    english_codes: tuple[GrantedCode, ...],
    native_result: DirectInferenceResult,
) -> tuple[GrantedCode, ...]:
    """Codes the native layer grants that the English-visible layer does not."""
    extra = [code for code in native_result.granted_codes if code not in english_codes]
    return tuple(extra)


def _class_increment(english: EnglishLayerClass, native: Classification) -> bool:
    """True when native combining class is strictly stronger than English-visible."""
    if native not in _PATHOGENIC_CLASSES and native != "insufficient":
        return False
    return _CLASS_RANK[native] > _CLASS_RANK[english]


def _lane(
    *,
    added_codes: tuple[GrantedCode, ...],
    native: Classification,
    clinvar_gap: bool,
) -> IncrementLane:
    """``both`` is extra criterion evidence plus a ClinVar gap on a Pathogenic allele."""
    if added_codes and clinvar_gap and native == "pathogenic":
        return "both"
    if added_codes:
        return "en_added_evidence"
    if clinvar_gap and native == "pathogenic":
        return "clinvar_gap"
    return "none"


def score_allele_class_increment(
    inference: DirectInferenceTable | None = None,
    coverage: EvidenceItemCoverageTable | None = None,
) -> AlleleClassIncrementReport:
    """Join reviewed on-disk events to English-visible codes and ClinVar match."""
    inference_table = inference or load_direct_inference_table()
    coverage_table = coverage or load_evidence_item_coverage_table()
    by_case = {source.case_id: source for source in coverage_table.sources}
    rows: list[AlleleClassRow] = []
    for event in inference_table.events:
        if event.materialization_status != "on_disk":
            continue
        source = by_case.get(event.case_id)
        if source is None:
            continue
        visible_ids = _visible_field_ids(source)
        english = _english_layer_score(event, visible_ids, inference_table.vcep)
        native_result = infer_event(event, inference_table.vcep)
        native = native_result.classification
        added = _added_codes(english.codes, native_result)
        class_increment = _class_increment(english.classification, native)
        clinvar_gap = event.clinvar_match in _CLINVAR_GAP_MATCHES
        rows.append(
            AlleleClassRow(
                event_id=event.event_id,
                case_id=event.case_id,
                source_cluster_id=event.source_cluster_id,
                paper_hgvs_c=event.paper_hgvs_c,
                canonical_allele_id=event.canonical_allele_id,
                native_language=source.native_language,
                english_classification=english.classification,
                native_classification=native,
                english_codes=english.codes,
                native_codes=native_result.granted_codes,
                added_codes=added,
                class_increment=class_increment,
                clinvar_match=event.clinvar_match,
                clinvar_gap=clinvar_gap,
                lane=_lane(
                    added_codes=added,
                    native=native,
                    clinvar_gap=clinvar_gap,
                ),
            )
        )
    evidence_rows = [row for row in rows if row.added_codes]
    en_path = [
        row
        for row in rows
        if row.added_codes and row.native_classification == "pathogenic"
    ]
    return AlleleClassIncrementReport(
        study_id="acmg-multilingual-allele-class-increment",
        scored_events=len(rows),
        evidence_increment_events=len(evidence_rows),
        evidence_increment_without_rett_007=sum(
            1 for row in evidence_rows if row.source_cluster_id != "rett_007"
        ),
        unique_alleles_with_added_codes=len({row.canonical_allele_id for row in evidence_rows}),
        class_increment_events=sum(row.class_increment for row in rows),
        english_not_scorable_to_pathogenic=len(en_path),
        unique_pathogenic_alleles_en_missing=len({row.canonical_allele_id for row in en_path}),
        clinvar_gap_pathogenic=sum(row.lane == "clinvar_gap" for row in rows),
        both_hero=sum(row.lane == "both" for row in rows),
        rows=tuple(rows),
    )


def summarize_allele_class_increment(
    report: AlleleClassIncrementReport,
) -> AlleleClassIncrementSummary:
    """Compact counts: extra ACMG evidence first."""
    return AlleleClassIncrementSummary(
        scored_events=report.scored_events,
        evidence_increment_events=report.evidence_increment_events,
        evidence_increment_without_rett_007=report.evidence_increment_without_rett_007,
        unique_alleles_with_added_codes=report.unique_alleles_with_added_codes,
        both_hero=report.both_hero,
        en_missing_to_pathogenic=report.english_not_scorable_to_pathogenic,
        clinvar_gap_pathogenic=report.clinvar_gap_pathogenic,
        unique_en_missing_pathogenic_alleles=report.unique_pathogenic_alleles_en_missing,
    )
